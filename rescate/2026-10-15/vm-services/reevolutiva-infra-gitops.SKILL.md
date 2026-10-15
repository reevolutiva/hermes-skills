---
name: reevolutiva-infra-gitops
category: infrastructure
version: 1.0.0
description: "Use when operating the reevolutiva-infra GitOps repo."
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [gitops, flux, k3s, kubernetes, reevolutiva]
    related_skills: [wordpress-bedrock-migration, infrastructure-bootstrap, llm-infra-normalization]
---

# reevolutiva-infra — operación del repo GitOps (Flux + K3s)

## When to Use
Cualquier tarea sobre el monorepo `reevolutiva-infra` (Flux CD + K3s de
Reevolutiva): migrar cargas legacy, agregar un proyecto, tocar manifiestos,
diagnosticar el clúster, documentar deuda técnica.

**Topología activa:** no mantengas direcciones, roles ni nodos como hechos estáticos en esta skill. Al comenzar una tarea de clúster, consulta el endpoint del kubeconfig seleccionado y `kubectl get nodes -o wide`; para decisiones de scheduling, consulta arquitectura, labels y taints en runtime. Un instalador/config local puede apuntar a un servidor retirado o describir un clúster distinto. Si el endpoint o la identidad del clúster no coincide con el objetivo, detente antes de ejecutar acciones mutantes.

**La arquitectura decide qué imagen puede correr dónde.** Antes de mover una carga, verifica las arquitecturas actuales con `kubectl get nodes -o custom-columns='N:.metadata.name,A:.status.nodeInfo.architecture'` y confirma las plataformas de la imagen. Obtén el endpoint API del kubeconfig activo; no lo deduzcas del nombre o la IP de un host.

**Regla de guardarraíl (si NO es multi-arch): declarar `nodeSelector` por `kubernetes.io/arch`.**
- Imagen amd64-only ⇒ `nodeSelector: kubernetes.io/arch: amd64`
- Imagen arm64-only ⇒ `nodeSelector: kubernetes.io/arch: arm64`

Porque el scheduler no sabe qué arquitectura soporta la imagen: el síntoma final
puede ser `ImagePullBackOff` (si el registry no tiene manifiesto para la arch)
o `exec format error` (si el manifiesto existe pero falla en runtime).

Usa `tailscale status` solo cuando la conectividad o identidad tailnet sea relevante; un host ausente de `kubectl get nodes` no es elegible para scheduling, aunque aparezca en Tailscale.

**Acceso a la VM de Azure sin manejar contraseñas:** `az vm run-command invoke -g REEVOLUTIVA -n produccion --command-id RunShellScript --scripts '<cmd>' -o json` ejecuta como root por el plano de control de Azure. Es la vía preferida para inventariar/provisionar un host que todavía no tiene SSH con clave.

**Secretos en AKV:** los nombres son `<namespace>-<service>-<key>` — p. ej. `monitoring-grafana-admin-user`, `monitoring-grafana-admin-password`, `litellm-masterkey`, `databases-postgresql-password`. Para que el dueño los lea, verificar primero `command -v az`: el comando `az keyvault secret show --vault-name ${VAULT_NAME} --name <n> --query value -o tsv` requiere **Azure CLI (`az`)**, no Azure Developer CLI (`azd`). Si falta `az`, instalar Azure CLI según la documentación oficial de Microsoft; luego autenticar con `az login` y seleccionar la suscripción correcta antes de consultar AKV. **Nunca imprimir el valor en el chat**: entregar el comando para ejecutarlo localmente. Si el secreto solo se necesita para probar un servicio, guardarlo en una variable de shell y usarlo directamente sin mostrarlo.

**Auth de lo expuesto:** Grafana pide login (AKV); Headlamp pide **token** (`kubectl -n flux-system create token headlamp --duration=24h`; el mínimo son 10 min, con menos la API rechaza); LiteLLM pide masterkey y su URL vigente usa **`https://`** con TLS del Ingress Tailscale. **Prometheus, Longhorn y Traefik no tienen auth** — el perímetro es el tailnet, y Longhorn permite borrar volúmenes desde la UI. Además el SA de Headlamp está atado a **`cluster-admin`** aunque el HelmRelease declare `clusterReadOnlyAccess: true`: el render del chart no coincide con lo declarado.


**Checkouts:** dev en `/data/workspace/projects/reevolutiva-infra`; despliegue en
`/data/workspace/workloads/reevolutiva-infra`. No existe `/opt/workspaces`.

**Acceso:**
```bash
# Selecciona el kubeconfig vigente para el clúster objetivo; confirma su server
# con `kubectl config view --minify` antes de consultar nodos o ejecutar cambios.
ssh -o StrictHostKeyChecking=no giolapietra@frontdoor
ssh -o StrictHostKeyChecking=no giolapietra@hosting
```
Los hosts legacy cargan mucho (load >40 por agentes): los comandos tardan. Subir
`timeout` en vez de repetir.

## Procedure

1. Confirma el repo, kubecontext, host y manifiestos actuales antes de actuar; no uses topología histórica como estado vivo.
2. Selecciona el runbook de esta skill que corresponda al cambio o incidente y sigue sus gates específicos.
3. Para incidentes de WordPress con error de subida de archivos (`Could not create directory structure` o similares), diagnostica primero dentro del pod: valida existencia de la ruta completa bajo `web/app/uploads`, dueño/grupo y bit de escritura del directorio padre, y prueba una escritura real en la ruta objetivo.
4. Si el incidente exige recuperación inmediata y el fix no puede esperar el ciclo GitOps, aplica un hotfix mínimo en runtime (crear ruta faltante y permisos exactos), verifica que la escritura funciona, y en el mismo flujo abre el cambio declarativo equivalente en Git para evitar drift.
5. Mantén el estado duradero en Git mediante PR y Flux; verifica el runtime y una prueba funcional antes de cerrar.

## Limpieza de recursos efímeros y jobs históricos

Secuencia obligatoria para limpiar basura operativa sin reintroducir drift:

1. Inventario primero (solo lectura):
   - `kubectl get jobs -A -o json` para listar jobs terminales (`Succeeded`/`Failed`) y antigüedad.
   - `kubectl get pods -A -o json` para detectar pods huérfanos sin `ownerReferences`.
   - Antes de borrar, confirma que el nombre del recurso no esté declarado en Git (`git grep`).
2. Corrige la causa en manifiestos antes de la poda puntual:
   - En CronJobs, declara `ttlSecondsAfterFinished` dentro de `jobTemplate.spec`.
   - Mantén `successfulJobsHistoryLimit` y `failedJobsHistoryLimit` explícitos.
   - Valida con `make lint`, abre PR y deja explícito que la poda runtime es backfill, no el fix principal.
3. Poda puntual (una vez) para sacar acumulado legacy:
   - Borra jobs terminales viejos: `kubectl delete job -n <ns> <name>`.
   - Borra pods huérfanos terminales: `kubectl delete pod -n <ns> <name>`.
   - No borres CronJobs ni controladores para “limpiar historial”; solo objetos terminales.
4. Cierre y evidencia:
   - Recuenta jobs terminales viejos y pods huérfanos para demostrar que quedaron en cero o en el umbral esperado.
   - No declares la limpieza completa hasta que el cambio declarativo esté mergeado en `main` y Flux muestre la revisión aplicada.

Pitfall:
- Nunca uses `kubectl delete` como solución principal en GitOps, porque Flux recrea todo lo que siga declarado. Primero corrige manifiestos; la poda manual solo quita deuda acumulada previa.

## Repos de servicio separados de la fuente Flux

Cuando un cambio parte de un repo de servicio y Flux consume otro repo:
1. Confirma en runtime el `GitRepository` activo (`spec.url`, `spec.ref`, revisión del artifact) y la `Kustomization` correspondiente (`spec.path`, `lastAppliedRevision`); no deduzcas la fuente live por el nombre del repo ni por el README.
2. Verifica el merge del cambio en el repo de servicio y compara su manifiesto con el path que Flux reconcilia. No supongas que mergear el repo espejo dispara un despliegue: comprueba si existe un workflow de sincronización y qué destino actualiza.
3. Trabaja en una rama/worktree desde `origin/main` del repo GitOps activo. Porta el cambio al path reconciliado y revisa el diff completo para conservar ajustes propios del manifiesto GitOps; no cambies la fuente de Flux como atajo. Confirma que claves/credenciales sigan como referencias a env/ExternalSecrets, nunca como valores literales.
4. Valida el build Kustomize, el lint del repo, `git diff --check` y `kubectl apply --dry-run=server -k <path>` cuando el cluster objetivo esté accesible. Abre el PR contra el `main` del repo que Flux consume y verifica su estado, archivos y checks; un PR abierto no equivale a despliegue.
5. Después del merge, confirma que el artifact de Flux avanzó, que la Kustomization aplicó esa revisión y que el workload pasó rollout y una prueba funcional. Si el alcance solicitado es preparar el PR, déjalo abierto y reporta claramente que falta el merge para desplegar.

## Verification — gates obligatorios antes de declarar algo terminado

```bash
make lint        # kustomize build de los 11 dirs + parseo YAML. Falla de verdad
make health      # nodos + Kustomizations + sources + HelmReleases
flux get ks -A   # criterio de aceptación del repo: todo verde, misma revisión
```

**Correr `make lint` con el intérprete del sistema: `PATH=/usr/bin:/bin:/usr/local/bin:$PATH make lint`.**
La receta de parseo YAML importa `yaml` (PyYAML), que está en `/usr/bin/python3` (6.0.1)
pero **no** en el `python3` que un runtime de agente suele poner primero en el PATH: ahí
muere con `ModuleNotFoundError: No module named 'yaml'` y `make` sale 1 **con los
`kustomize build` todos OK**. Es un falso rojo que se lee al revés (parece que el lint
está roto); no lo es.

**`make lint` también valida el borde (`borde-validar`): `terraform init -backend=false` + `fmt -check` + `validate` sobre `infra/cloudflare`.** Correr `terraform fmt` en ese directorio **antes** de commitear HCL, o el gate sale rojo por indentación (los `=` de un mapa se alinean por columnas y `fmt -check -diff` lo detecta). Y el build de kustomize recorre `clusters/*/*/`: un `clusters/<nodo>/flux-system/kustomization.yaml` que liste el `gotk-components.yaml` (que el `.gitignore` descarta) deja el lint en rojo con el clúster sano — el entrypoint declara `flux-system/gotk-sync.yaml` **como archivo**, no el directorio.

**No alcanza con pods `Running`.** Prueba funcional real:
```bash
curl -sS -o /dev/null -w '%{http_code} ssl=%{ssl_verify_result}\n' \
  https://litellm.coyote-paridae.ts.net/health/liveliness     # → 200 ssl=0
# Debe dar 200 con ssl_verify_result=0 (certificado válido). La exposición es el
# Ingress `tailscale` con `tls:`, así que es HTTPS de punta a punta: `http://`
# sobre el 443 responde "Client sent an HTTP request to an HTTPS server".
# (Estuvo al revés un tiempo: era un Service LoadBalancer con `loadBalancerClass:
# tailscale`, que es un proxy TCP crudo y habla HTTP plano en el 443. Si el
# síntoma es "wrong version number", estás mirando la exposición vieja.)
```

## Kustomizations suspendidas, fallidas o parcialmente operativas

No confundas `spec.suspend`, las condiciones Ready/Healthy, `wait` y la operación funcional de la app. Antes de cambiar una suspensión, contrasta intención de diseño, manifiesto Git y runtime real. Si el servicio debe operar, declara `spec.suspend: false` en el overlay y aplica el cambio por PR; si la pausa es intencional, declara `true` con motivo y criterio de reanudación. Antes de reanudar, revisa qué recursos/PVCs se crearán y si hay datos o una ruta legacy que preservar. Sigue `references/kustomization-operational-status.md` para la clasificación, reconciliación por dependencias y pruebas funcionales.

## Incidente P1 (sitios públicos caídos): runbook de triage

### Trigger
- Uno o más dominios públicos dan **timeout** (cero respuesta) o errores 5xx simultáneos durante migraciones/cutovers.
- Sospecha de que el camino de exposición (Cloudflare tunnel → cloudflared → Traefik/Ingress → Service → Pod) o el scheduling de pods está roto.

### Orden de acciones (siempre en este orden)
1. **Valida scheduling real del clúster** (gating duro) — y validá que estés mirando el clúster correcto:
   - `kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'`, y después `kubectl get nodes -o wide`.
   - **Puede haber varios clústeres con nombres de nodos coincidentes y estados distintos.** Confirma el `server` del kubeconfig y consulta los nodos en ese mismo contexto antes de interpretar `NotReady` o actuar; no fijes endpoints ni rutas de kubeconfig en el diagnóstico.
   - Si el/los nodos destino están `NotReady` **en el clúster correcto** y tus workloads usan `nodeSelector/env=prod`, los pods quedan `Pending`/`ContainerCreating` hasta que el nodo vuelva.
2. **Valida el estado declarativo (Flux)** solo para acotar si hay una regresión GitOps:
   - `flux get ks -A | egrep 'wordpress|familey|reevolutiva'`
   - Si healthcheck está en `timeout waiting ... InProgress`, vuelve a mirar pods (no cortes el túnel con pods sin endpoints).
3. **Valida pods/endpoint health por namespace**:
   - `kubectl -n wordpress get pods -o wide | egrep 'familey|dbrun3'`
   - `kubectl -n reevolutiva get pods -o wide | egrep 'wordpress|reevolutiva'`
4. **Valida que el ruteo público apunte al origen correcto**:
   - No asumas que porque existe un Ingress K8s “será” el tráfico público: Cloudflare tunnel puede aplicar reglas remotas y el archivo local puede no coincidir.
   - Usa el rastro del conector: `kubectl -n flux-system logs deploy/cloudflared --tail=200 | egrep -i 'configuration|Registered tunnel connection|Updated to new configuration'`.
   - Gate: el cutover solo se considera listo cuando el **nuevo origen** muestra tráfico en sus logs (y/o health real) y el origen viejo deja de recibirlo.
5. **Contención con fallback temporal**:
   - Si el nodo destino sigue `NotReady`, restaura el dominio **temporalmente desde el origen legacy** (p.ej. `hosting`) en vez de intentar forzar el corte a producción.
   - Mantén rollback listo: el switch del origen debe ser reversible por el mismo mecanismo (API remota del tunnel / reglas del proveedor).

### Pitfalls (costosos)
- **No cambies el túnel antes de endpoints**: si los pods están `Pending/ContainerCreating` por scheduling/volúmenes, el dominio seguirá caído aunque “el ruteo esté bien”.
- **No confíes en “hay un Ingress en el repo”** cuando el conector usa configuración remota: el manifiesto local puede no coincidir con lo aplicado.
- **No cierres el incidente sin evidencia**: siempre adjunta en el issue al menos `kubectl get nodes -o wide`, estado de pods relevantes y el resultado de `curl` (HTTP 200 o timeout/5xx).
- **Un puerto de `ClusterIP` que el Service no expone es un agujero negro, y el síntoma es timeout, no error.** Una regla de túnel apuntando a `http://wordpress-<sitio>.<ns>.svc.cluster.local:80` con el Service publicando **8088** no da `connection refused`: no hay listener, el paquete se descarta en silencio (sin RST) y el conector cuelga (`dial tcp 10.43.x.x:80: i/o timeout`) hasta que el borde corta. Antes de culpar a la app, comparar el puerto de cada regla con `kubectl get svc -n <ns> <svc>`. El destino declarado es `http://traefik.flux-system.svc.cluster.local:80` + `httpHostHeader` por hostname (Traefik rutea por `Host` al Ingress público del sitio).
- **Con el ruteo arreglado puede aparecer un bucle de 301 a https.** El borde termina el TLS y el salto conector→Traefik es HTTP plano: con `forwardedHeaders.insecure: false` (default) Traefik **pisa** el `X-Forwarded-Proto: https` del conector, WP (`is_ssl()`) ve `http` y redirige a https sobre una petición que ya venía por https. Síntoma: `curl -L` corta con `Maximum (N) redirects followed`. Se arregla declarando `ports.web.forwardedHeaders.insecure: true` en el HelmRelease de Traefik (lo aplica Flux). Prueba directa al pod y detalle: `references/cloudflare-tunnel.md`.
- **Qué túnel sirve un conector se lee en sus logs, no en el nombre del secreto.** El `Updated to new configuration … version=N` del pod tiene que coincidir con la `version` que devuelve `GET /accounts/<acct>/cfd_tunnel/<id>/configurations`; el nombre del secreto de AKV puede no corresponder al túnel (un secreto llamado `…-cluster-token` autenticaba el túnel `front`). Ver `references/cloudflare-tunnel.md`.
- **Un `connection refused` a Traefik desde un namespace cualquiera NO significa que Traefik esté caído.** En `flux-system` hay NetworkPolicies (`allow-egress`, `allow-egress-cloudflare-wordpress`, `allow-scraping`) que sólo admiten ingress de los pods del propio `flux-system`, de los namespaces `cloudflare`/`reevolutiva`, y al puerto `8080` para el scraping: cualquier otra fuente (el nodo, otro namespace) recibe RST. Para probar el ruteo sin el borde, correr el `curl`/`php` desde un pod de `cloudflare` o `reevolutiva`.

## Alertas en Prometheus: las reglas viven en el HelmRelease, y hay trampas

No hay `PrometheusRule` (el CRD no está instalado) ni Alertmanager: las reglas van en
`serverFiles.alerts` del HelmRelease de `apps/monitoring/prometheus.yaml`, que el chart renderiza como
la clave `alerts` del ConfigMap (`rule_files`) y un reloader aplica **caliente**. Tres trampas que ya
costaron tres PRs (reglas que renderizan vacías por el `toYaml`, un `up == 0` que es falso positivo
permanente detrás de una NetworkPolicy, y una serie ausente que no dispara): en
`references/alertas-prometheus.md`. Regla corta: **el valor va directo, la alerta no puede depender de
un canal que el diseño cierra, y `absent()` va primero.**

## Pitfalls (aprendidas a golpes)

### Restaurar una DB por pipe remoto: verificar el conteo de tablas, no el exit code

`gunzip -c dump.sql.gz | mariadb ...` puede terminar “bien” pero dejar la DB incompleta si el pipe se corta a mitad de streaming (RTT/timeout). El exit code no es una prueba de integridad.

**Regla:** después de cualquier restore: `SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='<db>'` y comparar contra el dump (`grep -c '^CREATE TABLE' dump.sql`). Además, un healthcheck que solo pide un asset estático no detecta tablas faltantes.

### Tailscale SSH: la API retorna HuJSON; la regla usa tags, no FQDN

La API de Tailscale retorna **HuJSON** (JSON con `//` comentarios), que jq no parsea.
Limpiar con regex o Python antes de procesar. El endpoint POST `/tailnet/{tailnet}/acl`
**reemplaza** toda la ACL (no merge). Leer la ACL completa primero.

Para permitir SSH: el `dst` de una regla **no puede ser FQDN** — usar tag o IP.
`vm-services` no tenía tag asignado hasta 2026-10-06, por eso `ssh-copy-id` fallaba incluso
con `tailscale up --ssh` activo. Para asignar tag: POST a `/api/v2/device/{id}/tags`.
La referencia completa: `references/tailscale-acl.md`.

**`tailscale ssh <host>` también falla si ese host no anuncia Tailscale SSH.** El ACL y el tag
pueden estar correctos y el dispositivo seguir sin `sshHostKeys` (Tailscale SSH deshabilitado en el
host): la conexión se rechaza igual que si faltara el ACL, y el SSH plano tampoco entra si no hay
clave autorizada. Mirar el `sshHostKeys` del peer en `tailscale status --json` **antes** de tocar el
ACL, y pedirle al dueño que habilite Tailscale SSH en ese host.

### UI de LiteLLM lenta en tailnet: separar cliente, estáticos, API y pod

Ante una UI lenta, no tomes el `200` de `/ui/` como tiempo de carga completa: la SPA puede esperar por bundles JS/CSS o por llamadas API. Mide el mismo recurso desde el cliente y dentro del clúster; identifica el peer/ruta Tailscale y contrasta logs y presión del nodo solo después de localizar la capa lenta. El procedimiento reproducible, criterios de atribución y comandos están en `references/http-performance-tailnet.md`.

**Regla:** una respuesta rápida dentro del clúster y lenta desde la URL acota el problema al camino cliente/Ingress/tailnet, pero no identifica por sí sola cuál de esos saltos falla. Mide bytes/tiempo de al menos un estático grande y revisa `Relay` en el peer de `tailscale status --json`; `tailscale ping` mide RTT, no throughput. Si la fuente de diagnóstico no es el navegador reportado, valida también desde ese navegador o pide un HAR antes de atribuirle el mismo camino.

**Cuando pidas un HAR, no indiques marcar «Disable cache».** Contamina la captura: todas las subresources salen con `no-cache` y `cache: {}`, y después no se puede decir nada sobre caché. El HAR sí habilita una prueba que ningún `curl` del host de diagnóstico da: comparar el header `date` de la respuesta con `startedDateTime + … + wait` demuestra si el retraso es **posterior al servidor** y descarta el origen. Receta, fórmulas y trampas: `references/http-performance-tailnet.md` → *Triage del HAR del cliente*.

**Corolario operativo:** solo investiga requests/resources/scheduling del pod como causa principal cuando las pruebas internas también sean lentas, o los logs/estado aporten evidencia. Compara `kubectl top` (uso observado) con requests asignados y estado del scheduler; no deduzcas presión a partir de un `Running` ni de un único endpoint health.

**Flujo de hardening LiteLLM:**
1. Verifica kubeconfig activo, labels/taints, nodo de PostgreSQL/Redis, arquitectura de la imagen y presión de nodo antes de editar.
2. Declara CPU, memoria y `ephemeral-storage` requests/limits en el workload. Si se fija una clase de nodo, declara selector y toleration en `clusters/<cluster>/apps.yaml` (no en el manifest genérico de la app), y agrega `dependsOn: infra-nodos`.
3. Si el cambio toca `clusters/<cluster>/apps.yaml`, reconcilia primero la Kustomization raíz `flux-system`; luego avanza por dependencias (`infra-controllers` → `infra-configs`/`infra-storage` → `apps-databases` → `apps-litellm`). Una revisión raíz aplicada no significa que sus Kustomizations hijas ya estén al día.
4. Mide 12–20 muestras externas de `/ui/` antes y después (DNS, connect, TLS, TTFB, total), resume p50/p95 e informa el tamaño de muestra. Una muestra pequeña sin picos no demuestra que una cola histórica desapareció.
5. Tras merge/reconcile, verifica en orden el artifact del `GitRepository`, `lastAppliedRevision` de la Kustomization, `Ready=True` del HelmRelease, rollout/Pod y prueba funcional. `Kustomization Ready=True` o un `flux reconcile` exitoso solo confirma que se aplicó el manifiesto; no garantiza que Helm terminó ni que el nuevo pod arrancó.

**Rollout de Helm con una réplica:** inspecciona el campo de estrategia en `helm show values` y confirma el render con `helm template`; no inventes una clave del chart. Si el pod nuevo queda `Pending`, lee `PodScheduled`/`FailedScheduling` y compara sus requests con `status.allocatable` y `Allocated resources` del nodo selector; `kubectl top` muestra uso actual, no capacidad de scheduling. Al informar el bloqueo, identifica explícitamente el cluster/API, namespace, `nodeSelector` y nodo elegible: el namespace no identifica el cluster, y otros nodos libres no ayudan si el selector excluye esos nodos. Antes de purgar, cuenta solo pods programados no terminados y contrasta su suma con `Allocated resources`; pods `Succeeded`/`Failed`, pods sin nodo y ReplicaSets con cero réplicas no reservan capacidad para el scheduler. No los borres como supuesto remedio de CPU. El default de un RollingUpdate con una réplica puede pedir un pod de surge adicional. `maxSurge: 0` + `maxUnavailable: 1` termina primero la réplica vieja y permite el reemplazo, pero causa una interrupción breve: requiere autorización explícita. Después del ajuste, reconcilia y espera `HelmRelease Ready=True` y rollout completo antes de declarar despliegue.

**Redis con PVC `ReadWriteOnce`:** al reemplazar un Deployment singleton, usa `RollingUpdate` con `maxSurge: 0` y `maxUnavailable: 1` para evitar un segundo pod intentando montar el mismo volumen. `Recreate` puede ser rechazado si el objeto conserva `rollingUpdate` por merge declarativo; valida con `kubectl apply --dry-run=server -f <manifest>` antes del PR. El reinicio implica una interrupción breve y debe estar autorizado.

**Recuperación de UI Admin:** sigue la documentación vigente de LiteLLM; configura `UI_USERNAME`/`UI_PASSWORD` por el canal existente de AKV → ExternalSecret, fuerza refresh con timestamp y reinicia mediante Flux. Valida el endpoint de login (en esta instalación `POST /v2/login`) con credenciales leídas en variables de shell; descarta el body y muestra solo el código HTTP. No intentes diagnosticar contraseñas imprimiendo respuestas administrativas.

**No exponer tokens al inspeccionar LiteLLM:** `/user/info` puede incluir valores completos en `keys[].token`. No imprimas ni guardes el body; proyecta solo campos no secretos como alias/rol, o envía la respuesta a `/dev/null` cuando solo necesitas el status. Una filtración de herramienta requiere informar qué tipo de token y dónde apareció, sin repetir valores, y dejar su revocación/rotación para una decisión explícita si puede cortar clientes.

### La imagen de LiteLLM importa: `litellm-database` carga guardrails de DB, `litellm` solo de config.yaml

La imagen `docker.litellm.ai/berriai/litellm-database:latest` (frontdoor) **carga** los guardrails
de `LiteLLM_GuardrailsTable` al arrancar. La imagen `ghcr.io/berriai/litellm:v1.103.0-rc.1` (clúster)
**no lo hace**: los guardrails built-in como `headroom` solo se cargan del `config.yaml` que el chart
renderiza desde `proxy_config`. La fila migrada en la DB es un artefacto que la imagen Community ignora.

El endpoint `/guardrails/register` de Community **rechaza** todo lo que no sea
`generic_guardrail_api`: `"Only guardrails with litellm_params.guardrail='generic_guardrail_api'
are accepted for registration"`. El único camino funcional para guardrails built-in es declararlos en
`proxy_config.guardrails` del HelmRelease.

Si alguna vez se migra a la imagen `-database`, los guardrails se pueden mover a DB y quitar del YAML.

### Las métricas de Headroom no se pueden scrapear desde Prometheus

- **`force: true` convierte un error de validación en un borrado.** Con un manifiesto
  **parcial** (un Deployment con solo `replicas`/`strategy`/`tolerations`) el apply falla
  — un Deployment exige `spec.selector` y `spec.template.spec.containers` — y `force: true`
  hace que Flux **borre el recurso para recrearlo**; la recreación falla igual. Así se borró
  el Deployment de CoreDNS (PR #46) y el sitio quedó en **502 durante ~15-20 min**: los pods
  seguían corriendo, pero WordPress no resolvía su MariaDB. Restauración:
  `sudo systemctl restart k3s` — re-aplica los addons embebidos (el ServiceAccount,
  ConfigMap, Service y ClusterRole nunca se borraron).
  **Para parchear un objeto que k3s posee: `spec.patches` de la Kustomization (patch
  estratégico), nunca un manifiesto parcial como recurso, y nunca con `force: true`.**
- **Un manifiesto parcial no es un manifiesto.** Si le faltan campos obligatorios del kind,
  no se puede aplicar como recurso — y el error se ve recién en el dry-run del controlador.
  Validar con `kubectl apply --dry-run=server -f <archivo>` **antes** de declararlo en una
  Kustomization, sobre todo si va con `force`.
- **Un cambio bien escrito puede estar equivocado.** El manifiesto de CoreDNS de #46 tenía
  comentarios excelentes, explicaba la dispersión, el taint y por qué `maxSurge: 0` — y era
  fatal: el razonamiento era correcto y el mecanismo, imposible. Revisar **si el mecanismo
  puede funcionar** (¿el kind acepta un objeto parcial? ¿qué hace `force` realmente?), no
  solo si el texto convence. `make lint` fue un no-op durante todo el
- **Un gate que no falla no es un gate.** `make lint` fue un no-op durante todo el
  proyecto: `yamllint` y `kustomize` no estaban instalados y ambas recetas
  terminaban en `|| true` (corría en 5 ms, exit 0). Antes de confiar en un
  verificador, **probarlo en negativo**: introducir un error y confirmar que falla.
- **Al escribir un verificador en bash, tres trampas que dan falso verde o falso rojo:**
  (1) `grep -c` sale **1 cuando cuenta 0**, así que con `set -e` aborta el script y con
  `|| echo "0"` concatena un segundo valor (`0\n0`) que rompe el `[[ -eq ]]` — usar `|| true`
  y un default `${VAR:-0}`; (2) el filtro regex de `jsonpath` (`[?(@.name =~ "^ts-")]`)
  **no está soportado** y devuelve vacío sin error — usar `--no-headers | awk` o un label
  selector; (3) contra un sistema **intermitente**, una sola muestra da PASS o FAIL al azar
  — muestrear N veces y reportar la **tasa** (`N/10`), con el parcial como FAIL, porque un
  `PASS` cómodo esconde justo el drift que el verificador existe para detectar.
- **Dar de baja una carga o un plano no termina en suspender la Kustomization.** El namespace
  sigue declarado en `infrastructure/configs/namespaces.yaml`, así que `infra-configs` lo
  **recrea** aunque los workloads ya no estén; y quedan residuos fuera de K8s (dispositivo
  del tailnet, volúmenes/PVs de Longhorn, `ExternalSecret`, y las filas del servicio en
  `docs/auditoria-servicios.md`). Barrer los seis y dejarlo escrito: ver
  `references/kustomization-operational-status.md`.
- **Si `kubectl delete` no mata el recurso, no era huérfano: está declarado en
  Git.** Flux lo recrea. La limpieza correcta pasa por un PR, no por kubectl.
  Corolario: antes de borrar "huérfanos", grep el nombre del recurso en el repo.
- **`infra-controllers` tiene `wait: true` ⇒ un `HelmRepository` roto bloquea TODO
  el árbol de Flux.** Ya pasó con `headlamp` (URL 404). Los HelmRepository viven
  **solo** en `infrastructure/controllers/helm-repositories.yaml` (única fuente de
  verdad). Al agregar uno: `curl -sSf -o /dev/null <url>/index.yaml` primero.
- **Nunca extraigas `.data` ni `.stringData` de un Secret para inspección.** `jsonpath` puede mostrar valores base64 y la redacción automática no basta. Usa `-o name` o proyecta solo los nombres de claves. La misma regla aplica a scripts y configs: no imprimas líneas crudas que puedan contener tokens; proyecta una allowlist de campos no secretos y, si solo necesitas comparar secretos, emite un booleano sin valores ni hashes.
- **El `.gitignore` ignora `**/secrets/*.yaml` (SOPS) y `**/flux-system/gotk-*.yaml`.**
  No pongas manifiestos en texto plano bajo una carpeta `secrets/`: git los
  descarta en silencio y Flux falla con `kustomization path not found`. Usar
  `infrastructure/external-secrets/`. `make lint` ahora lo detecta (comprueba
  trazabilidad en Git, no solo el árbol de trabajo).
- **Longhorn NO corre en `longhorn-system` en este clúster: sus pods y los CRD
  (`volumes.longhorn.io`, `replicas.longhorn.io`) viven en `flux-system`.** El namespace
  `longhorn-system` existe y está **vacío**. Un `kubectl get … -n longhorn-system | grep`
  devuelve vacío y parece "todo limpio" por la razón equivocada. Al inventariar o buscar
  residuos de volúmenes, la fuente confiable es la lista de PVs (`kubectl get pv`) más
  `kubectl get volumes.longhorn.io -n flux-system`, no el namespace del nombre del chart.
- **Longhorn: `defaultReplicaCount: 2` y `persistence.defaultClassReplicaCount: 2`.**
  El setting solo **no alcanza**: un PVC sin `numberOfReplicas` explícito hereda el de la
  **StorageClass**, que el chart crea con su propio default (3). Con dos nodos esa tercera
  réplica no tiene dónde ir y **todo volumen nuevo nace `degraded`** — inicializar una
  MariaDB tardó 8 minutos contra ~30 s de un volumen sano. Una réplica por nodo es la
  redundancia real que este clúster puede cumplir. Ojo: con 2 réplicas una vive en el otro
  nodo, así que cada fsync cruza el túnel de Tailscale (restore completo de MariaDB: >7 min).
- **Otros repos tienen su propio `AGENTS.md` y su propio working tree.** El de
  ITC (`ReevolutivaTI/itc`) declara los archivos de infra fuera de scope App, y en
  `frontdoor` tiene una rama con cambios sin commitear: reportar por issue/PR, no
  editar el árbol ajeno.
- **Al reconciliar a mano, el grafo cascada a `False`.** Forzar una Kustomization
  deja a sus dependientes en `dependency not ready` hasta el ciclo siguiente.
  Forzar en orden de dependencia (`apps-databases` antes que `apps-litellm`) y
  esperar; no es una regresión.
- **No cierres un PR por "está CLEAN/MERGEABLE"** sin ver que `main` no tenga una
  referencia colgante (se mergeó una doc después de que `AGENTS.md` ya la citaba).
- **Para errores de subida en WordPress, verifica la ruta exacta antes de tocar recursos globales.** Si el nombre de archivo reporta una subcarpeta (`story_content/...`) y esa carpeta no existe bajo `uploads`, crear esa ruta con owner `www-data:www-data` y modo de grupo escribible corrige el incidente; cambiar `fsGroup`, PVC o DB no arregla una ruta inexistente.
- **El archivo de config de un túnel puede no ser el que manda.** En `frontdoor`,
  `cloudflared` **lee** `/workspace/litellm/cloudflared/config.yml` pero aplica la
  **configuración remota** de Cloudflare — lo dice en los logs (`Updated to new
  configuration … version=N`) con un contenido que **no coincide** con el archivo.
  Editarlo no cambia el ruteo: comprobado, el tráfico siguió yendo al host legacy.
  Leer el runtime (`docker logs`, la API), y nunca asumir que editar ese archivo
  equivale a cambiar algo. El caso completo, en `references/cloudflare-tunnel.md`.
- **Una `200` detrás de Cloudflare NO prueba que el origen esté vivo.** `familey.cl`
  devolvía `200` mientras su origen estaba **caído**: el túnel apuntaba a
  `127.0.0.1:8080` (donde no escucha nada; el WP publica en `8088`) y Cloudflare
  servía **caché**. Verificar con URL **no cacheable** (`?cb=$RANDOM`) **y** contra el
  origen directo (`curl -H "Host: <dominio>" http://127.0.0.1:<puerto>/`).
- **No leer logs truncados.** Concluí que el túnel servía `8088` desde un log cortado
  (`originService=http://127.0.0.1:8…`): decía lo que yo esperaba, no lo que había.
  Si un valor decide un diagnóstico, leerlo entero (`cut -c1-200`, no `-120`).
- **Antes de editar la config de un túnel/proxy, verificar el **origen** con su
  `Host`.** `docker port` + `curl -H "Host: …"` dice cuál es el puerto real; el
  archivo de config puede estar desactualizado respecto del proceso (y el proceso
  respecto del archivo).
- **Backups que no respaldan:** revisar tamaño/cantidad (13 dumps byte-idénticos =
  base congelada). Un `set -euo pipefail` + `docker exec` a un contenedor detenido
  aborta el script entero: no genera dump **ni corre la retención**.
- **No medir el disco con `/`.** En `hosting` reporté "85 % lleno, no caben los
  7,6 GB" y era falso: `/` es de 29 GB, pero los datos viven en `/dev/sdb1` (1 TB,
  896 GB libres) porque `/home/hosting` es un **symlink** a
  `/mnt/docker-storage/hosting`. Medir siempre con `df -h <ruta-de-los-datos>` y
  `readlink -f <ruta>`. Igual en `frontdoor`: `/mnt/workloads` es otro disco.
- **Inventariar contenedores por las etiquetas de compose, no por `docker ps`.**
  `docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'`
  da el archivo real de cada contenedor. Así se descubrió que el proyecto
  `litellm` de `frontdoor` tiene **9 servicios** (proxy, db, headroom,
  vector-store, paperclip, hermes-gateway, ingress, tailscale-hermes, ollama) y que
  el compose de ITC está **duplicado en dos rutas**. `docker ps -a` además revela
  los contenedores `Exited` = cargas **ya migradas** que siguen ocupando lugar.

- **Recrear el nodo deja un dispositivo fantasma en el tailnet.** El dispositivo
  viejo conserva el nombre, así que el nuevo se registra como `<nodo>-1` y
  `tailscale ssh <nodo>` apunta al muerto: el SSH "no entra" con el ACL bien.
  `make nodo-verificar` lo diagnostica. Remedio: borrar el dispositivo viejo por
  API y renombrar el nuevo (dos llamadas). Se repite en **cada** recreación
  mientras no se limpie.
- **Longhorn: recrear el nodo invalida su disco.** Al reformatear cambia el
  `diskUUID` y Longhorn deja el disco **no agendable**
  (`DiskFilesystemChanged: record diskUUID doesn't match the one on the disk`,
  `max=0.0 GiB`) aunque el nodo figure `Ready`. Remedio (longhorn#626, caso
  idéntico: *"a new machine with the same name as the old machine"*): deshabilitar
  el disco (`allowScheduling: false`), quitarlo de `spec.disks`, y **re-crearlo**
  con la misma ruta. Exige 0 réplicas en el nodo, así que se hace **antes** de
  migrar cargas.
- **`kubectl get` sin aserción no verifica.** Dos verificadores propios reportaron
  en falso por esto: `awk '{print $NF}'` tomaba la **edad** (no el estado) y daba
  "11 de 11 fuera de True" con todo verde; `sleep 150` + volcado de
  `kubectl get nodes` mostraba `NotReady` con la IP vieja en plena ventana de
  arranque. Leer en JSON (`-o json` + parser) y **esperar el estado** con tope.
- **Un nodo muerto arrastra a todo workload que monte Longhorn.** `Kubelet stopped posting node status` **más** `tailscale ping <nodo>` sin respuesta significa que la máquina no está, no que el kubelet tuvo un hipo. Los PVCs quedan atados a un nodo inexistente: los rollouts de otros servicios aparecen `Terminating`/`Pending` con `FailedAttachVolume`, y no es una regresión de esos manifiestos — revísalo antes de tocar el workload que "se rompió".
  El error de montaje que lo confirma es `MountVolume.MountDevice failed … driver name driver.longhorn.io not found in the list of registered CSI drivers`: los pods `csi-attacher`/`csi-provisioner`/`csi-resizer` de `flux-system` **no son** el plugin de nodo, y es el plugin de nodo el que registra el driver en cada nodo — su ausencia explica el fallo aunque el PVC figure `Bound`. Estas VMs (incluida `vm-worker`) son guests libvirt **en `imac27`**: `vm-services` no tiene `virsh`, así que un nodo caído se levanta desde `imac27`, no desde el host donde corre el agente.
- **Al fijar una carga a un nodo, no uses un label que apunte a varios.** `reevolutiva.io/clase: desarrollo` también selecciona `vm-services` (bajo `disk-pressure` y sin CSI de Longhorn) y esa combinación produjo evictions en serie: fija por nombre de nodo o por un label exclusivo, y declara `ephemeral-storage` en requests/limits — un pod sin él es el primero en ser evictado bajo presión de disco.

## Retirar una VM del clúster y redimensionar guests libvirt (trampas reales)

Procedimiento completo en `docs/runbooks/retirar-nodo-y-redimensionar-vms.md` del repo. Lo que hay que
recordar SIEMPRE:

- **Serializar drenar → apagar → redimensionar → verificar. Nunca en paralelo.** Un intento en paralelo
  (2026-10-06) tumbó `vm-services` y el drenaje, sin receptores sanos, reprogramó las cargas en el host
  `imac27` — lo contrario del objetivo. **Antes de drenar: todos los receptores `Ready` y 0 réplicas
  Longhorn en el nodo a retirar.**
- **`virsh setmem` en vivo cuelga el guest** (el balloon lo deja sin RAM): sigue `running` en `virsh list`
  pero sin red ni consola. Redimensionar SIEMPRE con la VM **apagada** y `--config`
  (`setvcpus/setmaxmem/setmem --config`), después `virsh start`.
- **Recuperar el agente K3s de `vm-services` exige validar el servidor antes de reiniciarlo.** Primero lee solo el endpoint del kubeconfig activo y compáralo con `server` en `/etc/rancher/k3s/config.yaml`; no ejecutes a ciegas `/etc/systemd/system/k3s-agent-install.sh`, que puede apuntar a un control-plane retirado y contener un token inline. Revisa `systemctl show` (estado/PID/reinicios), cuenta procesos `k3s-agent` y comprueba `k3s.service` antes de detener o iniciar nada: nunca dejes dos agentes ni un servidor local compitiendo. Si la config local coincide con el API activo y contiene la fuente de token requerida, la recuperación observada usa `sudo -n systemd-run --unit=k3s-agent-run --property=Restart=always --no-block "$(command -v k3s)" agent --config /etc/rancher/k3s/config.yaml`; no es una reparación persistente. Antes del reinicio inventaría las cargas con PVC Longhorn en el nodo y coordina la interrupción: un `Ready` inmediato puede ser un heartbeat viejo. Después espera lease renovada y `Ready`, confirma el driver en `CSINode` y valida el montaje real del workload; `attached/healthy` de Longhorn no certifica que el filesystem esté montado ni íntegro. Revisa logs del kernel por errores ext4/JBD2/I/O y no ejecutes `fsck`, formato o restore sin autorización y plan de datos. Todo cambio duradero al aprovisionamiento debe corregirse en su fuente versionada mediante PR.
- **El PVC de backups puede llenarse por snapshots Longhorn, no por dumps.** `pg_dump` falla con
  `No space left on device` aunque `df` del PVC muestre 12 %: las snapshots del `RecurringJob` consumen
  el volumen. Revisar la retención de snapshots, no solo los dumps.
- **El pull del registry interno se cuelga en `vm-worker` también** (no solo `vm-dev`): `vector-store`
  quedó `Init:0/1` >4 min sin fallar. No es exclusivo de un nodo; priorizar `image-pull-progress-deadline`.
- **Tras churn, `External Secrets` puede reiniciarse** y dejar Kustomizations en
  `dependency 'flux-system/infra-secrets' is not ready`. Es transitorio: `flux reconcile kustomization
  infra-secrets -n flux-system` lo destraba y propaga a los dependientes.

## Almacenamiento y capacidad de un nodo: el disco de Longhorn vive en el fs raíz

**`defaultDataPath` de Longhorn es `/data/workspace/longhorn`, y dentro de la VM esa ruta es el
filesystem raíz** (solo `/data/workspace/projects` es el share virtiofs del host). Un nodo puede
reportar "28 G de almacenamiento" y estar reportando su propio disco de sistema: así se llega a
`disk-pressure` con las imágenes y los caches encima. Antes de hablar de capacidad: `findmnt -T` de
cada ruta, `du -x` (sin `-x` el `du` atraviesa el share y miente) y `kubectl get nodes.longhorn.io
<nodo> -n flux-system -o json | jq '.spec.disks'`. `defaultDataPath` **solo afecta discos nuevos**
(los CRs de nodo los crea Longhorn en runtime, no están en Git), así que migrar es declarar el disco
nuevo con `allowScheduling: true` y el viejo con `false` hasta que las réplicas se reconstruyan.
Ampliar la VM es un LV del array del host adjuntado como `/dev/vdb` (hot-plug) — **el `mkfs` lo
ejecuta un humano: es comando bloqueado para el agente**. Procedimiento, patrón de bind mounts con
`x-systemd.requires-mounts-for`, triaje de "el raíz se llena" y gates:
`references/almacenamiento-nodos.md`.

### Longhorn Node CRs + Flux SSA: evita el conflicto por ownership

Los `nodes.longhorn.io` los actualiza `longhorn-manager`; con Flux en server-side apply y `force: false`,
cambiar un campo ya poseído por el manager (p. ej. `spec.disks.<id>.allowScheduling`) termina en
`Apply failed with conflict` y deja la Kustomization en rojo.

**Regla:** antes de proponer un PR sobre `nodes.longhorn.io`, prueba el manifiesto con
`kubectl apply --server-side --dry-run=server -f <archivo>` y revisa `managedFields` del CR para ver quién
posee cada campo.

**Secuencia segura para migrar disco de Longhorn en un nodo existente:**
1. **PR-1:** agrega el disco nuevo (`/data/local/longhorn`) y mantiene los valores actuales del disco viejo
   (no intentes cambiar campos ya poseídos).
2. Espera `diskState: ready` del disco nuevo y mide la capacidad viva desde la API del manager (`kubectl get --raw /api/v1/namespaces/flux-system/services/http:longhorn-frontend:80/proxy/v1/nodes/<node>` + `jq`) para registrar `allowScheduling`, `storageReserved` y `storageAvailable` en la misma evidencia del gate. Guarda ese JSON en el comentario del gate: es la vista que usa la UI de Longhorn y evita cerrar con solo el `spec`.
3. **PR-2:** cambia el campo en disputa (`allowScheduling: false` del disco viejo) solo después de que
   `longhorn-manager` ya lo haya cambiado en runtime; Git declara ese estado y co-posee sin conflicto. Registra explícitamente en el issue/handoff que el manager ya escribió el valor (fuente: API/UI + managedFields) antes del PR.
4. Reporta capacidad usable, no solo capacidad cruda: capacidad programable = `storageAvailable - storageReserved` (con el mismo origen de datos de Longhorn), y deja el `storageReserved` exacto en Git para no perder la reserva en reconciliaciones futuras.

**Regla adicional:** no retires el disco viejo del `spec` mientras siga existiendo en la API de Longhorn. Quitar su declaración en Git no lo borra del CR si `longhorn-manager` sigue co-poseyendo la estructura; solo te hace perder el guardarraíl declarativo de `allowScheduling: false`. Si se decide limpieza completa, ejecútala por manager (UI/API), y documéntala como operación fuera de Git con deuda explícita.

**No uses `force: true` como salida rápida** para este caso: si hay error de esquema/manifiesto, Flux puede
borrar y recrear recursos críticos.

## Exposición por Tailscale: verificar el certificado, no el manifiesto

Un `Ingress` con `ingressClassName: tailscale` no sirve HTTPS de inmediato. El
operador crea un pod proxy por Ingress (`ts-<nombre>-<hash>-0`) que **pide el
certificado por ACME al arrancar**, y el primer intento suele chocar contra IPv6
(`dial tcp [2606:4700:…]:443: network is unreachable`) aunque el pod **sí tenga
IPv4**. Los reintentos terminan emitiendo el certificado (`cert("…"): got cert`).

- **Esperar antes de gritar error.** Un `curl` inmediato da
  `tlsv1 alert internal error` o timeout y parece que la config está mal: no lo está.
- **Si un proxy queda colgado**, `kubectl delete pod ts-<nombre>-…` y el operador lo
  recrea con `TS_DEBUG_ACME_FORCE_RENEWAL=true` (reintenta el ACME al toque).
- Verificar con `curl -sS -o /dev/null -w '%{http_code} %{ssl_verify_result}'`:
  el segundo valor tiene que ser **`0`** (certificado válido).
- Sin `tls:` en el Ingress, el proxy **no** sirve HTTP: `Couldn't connect to server`
  en el puerto 80. Con `tls.hosts`, solo HTTPS.

### Backend fuera de K8s detrás de Service sin selector (patrón Paperclip)

Cuando el dominio público entra por proxy Tailscale en K8s pero el backend real corre en una VM/proceso fuera del clúster, valida en este orden:

1. `curl` público (`code`, `remote_ip`, `ssl_verify_result`) para confirmar síntoma y destino.
2. `kubectl get svc/endpoints` del servicio expuesto para ver a qué `IP:puerto` reenvía realmente.
3. Estado del proxy (`ts-*`): si está `Running` pero sus logs muestran `dial tcp ... connect: connection refused`, el problema suele ser backend no escuchando.
4. En el host backend, verifica el bind real (`ss -tlnp`) y compara con el endpoint del Service.

Pitfall:
- No des por bueno un endpoint porque existe. Si el proceso escucha en `127.0.0.1` pero el Service apunta a `IP_del_nodo:puerto`, el proxy responde 502 con `connection refused`: la exposición está sana y el backend está inaccesible por dirección de bind.

**Dashboard de Traefik:** `--api.dashboard=true` **no alcanza**. Con
`api.insecure=false` (y K3s no lo pone inseguro), Traefik no sirve nada por el
entrypoint `traefik` (:8080) — `/dashboard/`, `/api/rawdata`, `/api/http/routers` y
`/api/version` dan **404**. Hace falta un `IngressRoute` que apunte a
`api@internal`, y su `Host(...)` tiene que ser el **FQDN exacto del tailnet**
porque es lo que Traefik ve en la petición:

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
spec:
  entryPoints: [web]
  routes:
    - match: Host(`traefik.<tailnet>.ts.net`)
      kind: Rule
      services: [{name: api@internal, kind: TraefikService}]
```

**El chart de Headlamp renderiza su Ingress con clase `traefik`** aunque se le pase
`className: tailscale`, o sea que no publica nada al tailnet: queda un duplicado
inútil al lado del Ingress real. Poner `ingress.enabled: false` en el HelmRelease y
mantener el `headlamp-tailscale-ingress.yaml`.

## DNS del tailnet: MagicDNS sin upstreams rompe Flux y ESO

Si el tailnet tiene MagicDNS activo y **cero nameservers globales** (`dns: []`), `tailscaled`
responde **SERVFAIL** a todo nombre público, esa IP queda como upstream de CoreDNS y **1 de
cada 3 consultas del clúster falla**. Síntoma: `server misbehaving` / `no such host`
intermitentes en `GitOperationFailed`, `HelmRepository Failed` y `ExternalSecret UpdateFailed`
(se autorrecuperan solos, así que parecen ruido de despliegue). El diagnóstico en tres
comandos, el arreglo por API del tailnet y las trampas asociadas están en
`references/gotchas-verificados.md` → *DNS del tailnet*; el procedimiento formal, en
`docs/tailnet-dns.md`. Regla corta: **`dig +short @100.100.100.100 github.com` tiene que dar
una A**.

Una resolución exitosa desde un pod no demuestra por sí sola la configuración global de
MagicDNS, nameservers o ACL: CoreDNS puede responder desde `NodeHosts`, el plugin
`kubernetes` o el upstream configurado. Para diagnosticar drift, compara la consulta
real desde el pod, una consulta directa a `100.100.100.100` desde un peer Tailscale y la
configuración global consultada en modo lectura. Del mismo modo, que un hostname público
resuelva solo demuestra que existe una respuesta DNS; no prueba qué túnel ni origen atiende
eses nombres.

### `forward . /etc/resolv.conf` no sirve con nodos de distinto `resolv.conf`

Los nodos no tienen el mismo `/etc/resolv.conf`: `produccion` (Azure Flatcar) apunta al
archivo de **uplinks** (`100.100.100.100`, `fd7a:115c:a1e0::53`, `168.63.129.16`), mientras
`vm-services`/`vm-worker` usan el **stub** de systemd-resolved. Con `dnsPolicy: Default`
cada réplica de CoreDNS hereda el de su nodo y con varios upstreams `forward` elige **uno
al azar por consulta**. Azure responde **NXDOMAIN autoritativo** para `*.coyote-paridae.ts.net`
(AUTHORITY `ts.net. SOA ns1.dnsimple.com`: trata `ts.net` como TLD público) y el plugin
`cache 30` lo guardaba en negativo. Síntoma: los pods fallan **de a rata** (`no such host`)
al resolver LiteLLM/Grafana/Headlamp/registry, mientras `dig @100.100.100.100` desde el nodo
siempre funciona. Medido: `headlamp` 4/10, `matomo` 3/10, `litellm` 8/10 — la tasa depende
del momento, no del nombre, porque es caché negativa.

**Regla:** en el Corefile de un CoreDNS propio, declara el upstream explícito
(`forward . 100.100.100.100`) en vez de `/etc/resolv.conf`. Un resolutor que no conoce el
tailnet contesta NXDOMAIN (no SERVFAIL), así que **no hay reintento** y la respuesta mala
se cachea. Para diagnosticarlo: `dig @<ip-de-la-replica> <nombre> A` (la AUTHORITY revela
quién contestó), `curl -s http://<ip>:9153/metrics | grep proxy_request_duration_seconds_count{`
(lista los upstreams reales de cada réplica; son contadores **acumulativos**, así que el
delta tras N consultas es lo que decide, no el valor absoluto), y
`kubectl get endpoints kube-dns -n kube-system` para llegar a cada réplica por separado.

**Gate de este plano: `make tailnet-check-readonly`** (`scripts/tailnet-check-readonly.sh`,
`wait: false` no aplica: es un script). Siete secciones: `NodeHosts` repo vs live, nodos
`Ready`, MagicDNS + nameservers + split DNS + **lista de peers** validada contra `NodeHosts`,
túneles Cloudflare con sus conexiones, resolución DNS interna/externa, proxies Tailscale, y
revisión de Flux. Corre **sin sudo** (ver *Secretos*: con sudo se pierde la sesión de `az` y
las secciones de Tailscale/Cloudflare dan SKIP en vez de FAIL).

- **El `forward` del Corefile SÍ es una palanca del repo** desde que CoreDNS dejó de ser el
  addon de k3s y se declara en `infrastructure/dns/`: editar el `forward` ahí y mergear basta
  (el plugin `reload` lo toma sin reiniciar pods; el volumen del ConfigMap tarda ~1 min en
  propagarse, así que un `dig` inmediato tras el merge todavía ve el comportamiento viejo).
  Lo que sigue siendo cierto es que **dos `forward` en el mismo server block no compilan** —
  para *otros* plugins la vía es `import /etc/coredns/custom/*.override`.
- **En un CoreDNS propio, no dejes `forward . /etc/resolv.conf`.** El `resolv.conf` de los
  nodos no es homogéneo (unos usan el stub de systemd-resolved, otros la lista de uplinks) y
  con `dnsPolicy: Default` cada réplica hereda el de su nodo: el mismo nombre resuelve en una
  réplica y no en la otra. Ver la sección de drift de upstreams más arriba.
- **IPv6 sin ruta pero con AAAA.** El nodo resuelve AAAA y no tiene ruta v6, así que el primer
  intento muere con `dial tcp [2606:…]:443: connect: network is unreachable` (reproducible:
  `curl -6` falla en milisegundos, `curl -4` da `200`). Se corrige filtrando AAAA en CoreDNS
  (`coredns-custom`; el Deployment ya monta `custom-config-volume`).
- **`resolv.conf` del nodo con entradas de más**: systemd-resolved lista los del ISP dos veces
  más los de Tailscale (v4 y v6) → kubelet aplica sólo 3 y avisa `DNSConfigForming: Nameserver
  limits were exceeded` en los pods con `hostNetwork` (`coredns`, `node-exporter`). Cosmético.

## Secretos (arquitectura vigente)

External Secrets Operator contra **Azure Key Vault**, ya cableado y funcionando.

| Pieza | Valor |
|---|---|
| Vault | `giorgio` — `https://giorgio.vault.azure.net/`, tenant `127554d0-25ed-4843-ad2c-ca94d91866b3` |
| Suscripción | `Microsoft Azure Sponsorship` (`e2bbfb55-…`); hay otra y un vault `claves-hosting` |
| Service Principal | **`imac27-eso-sp`** con `Key Vault Secrets User`, scope solo del vault |
| ClusterSecretStore | **`azure-kv`** en `infrastructure/external-secrets/` |
| Kustomization | **`infra-secrets`** con `wait: false` (un fallo de AKV no debe tumbar el grafo) |
| Nombres en AKV | `<namespace>-<service>-<key>`; `litellm-env` va como JSON y se consume con `dataFrom.extract` |
| Secreto raíz | `azure-kv-credentials` en `flux-system` — **fuera de Git**, es el único que no puede venir del vault |

**NO reutilizar `kelenfold-eso-sp`**: es de otro entorno y rotar su credencial lo
rompe. Crear un SP dedicado.

**Rotar un secreto** (ahora es barato): `az keyvault secret set` → forzar refresh
del `ExternalSecret` → reiniciar el consumidor.

Si la sesión de `az` aparece con `AADSTS70043`, es el refresh token vencido
(vida máxima 30 días): requiere `az login` interactivo del usuario.

**No corras comandos que consulten AKV bajo `sudo`.** La sesión de `az` vive en el home del
usuario, así que `sudo az keyvault secret show …` falla; en un script de verificación eso se
manifiesta como **SKIP silencioso** (el `|| true` se traga el error) y el check parece pasar
sin haber mirado nada. El kubeconfig del usuario ya es legible: `KUBECONFIG=$HOME/.kube/<cfg>
<comando>`, sin sudo. Si hace falta sudo para *reconciliar* Flux, pasalo por variable de
entorno en la misma línea (`sudo KUBECONFIG=… flux reconcile …`) y dejá la consulta a AKV en
un comando aparte, sin sudo.

## LiteLLM: un solo dueno por clave (archivo vs DB)

LiteLLM resuelve la config por **dueno, clave por clave**: el archivo
(`proxy_config` del HelmRelease → `config.yaml`) y la persistida en Postgres. Y lo
hace cumplir con una guarda explicita:

> 400 `litellm_settings key 'cache_params' is set in the config file and cannot be
> changed here` … `remove it from the file to let the database own it`

**Declarar una clave en el archivo Y en la DB es un conflicto, no un respaldo.**
Y el ganador no es el que uno espera: el `litellm_settings` de la DB *reemplaza*
el del archivo, asi que declarar `cache_params` en el HelmRelease sin limpiar la
DB **no hace nada** (el ConfigMap sale bien y `/cache/ping` sigue en `LOCAL`).
Encima, para el **cache** el dueno efectivo es la fila `LiteLLM_CacheConfig` (el
proxy aplica "Cache settings initialized from database"), que pisa al archivo.

En este repo **Git manda**: el cache se declara en `proxy_config` del HelmRelease
(con `password: $REDIS_PASSWORD`, para que el secreto siga solo en AKV)
y la fila `LiteLLM_CacheConfig` se borra. Claves que el archivo **no** declara
(`drop_params`, `default_team_params`, `anthropic_*`) le corresponden a la DB.

Claves utiles: `litellm_settings.cache: true` + `cache_params: {type: redis, host,
port, password: $REDIS_PASSWORD, namespace: litellm}` y
`enable_redis_auth_cache: true` (sin esto el auth cache queda por-worker en
memoria y el proxy lo avisa en cada arranque).

## LiteLLM: los guardrails viven en la DB, no en Git (y rompen por DNS)

Un `guardrail` de LiteLLM se registra en la tabla **`LiteLLM_GuardrailsTable`** del
PostgreSQL del proxy, con su propio `api_base`. No está en el repo y **ningún gate lo mira**.
Si ese `api_base` apunta a un nombre de servicio del compose legacy (p. ej.
`http://headroom:8787`), en el clúster la resolución DNS falla **dentro del pod** y el
guardrail corta en `pre_call`: `502 {'error': '… service unreachable', 'detail': 'Cannot
connect to host <n>:<p> … [Name or service not known]'}`.

**Por qué falla "a algunos" y no a todos — el diagnóstico en tres pasos:**

```bash
# 1. ¿Es global o está pegado a claves?
curl -sS -H "Authorization: Bearer $MASTERKEY" https://litellm.<tailnet>.ts.net/guardrails/list
#    {"guardrails":[]}  → NO es global: alguien lo referencia por clave
# 2. ¿Quién lo referencia? (solo el alias; nunca imprimir el token)
psql -tAc "select key_alias, metadata from \"LiteLLM_VerificationToken\" \
           where metadata::text ilike '%guardrail%';"
# 3. ¿Y el apunte?
psql -tAc "select guardrail_name, litellm_params->>'api_base', litellm_params->>'mode', \
           litellm_params->>'unreachable_fallback' from \"LiteLLM_GuardrailsTable\";"
```

`fail_on_error: true` + `unreachable_fallback: fail_closed` es lo que convierte un sidecar
ausente en un corte de servicio. **Corolario que ahorra el trabajo:** si el guardrail apunta
a `http://headroom:8787` y el sidecar se declara como Service **`headroom`** en el **mismo
namespace** que el proxy, el nombre resuelve tal cual y **no hay que tocar la fila de la DB**.
El fix es declarar el servicio que falta, no editar la configuración.

**Trampa mayor, el `502` no era de red:** el caché estaba sano (`/cache/ping` → `cache_type:
redis`) y las completions con la masterkey daban 200. Antes de culpar a la migración del
proxy, mirar quién es el dueño del corte: un guardrail pegado a una clave explica que el
servicio funcione "casi siempre".

## LiteLLM: la config persistida en Postgres GANA sobre env y Git

Al migrar LiteLLM de host (o al rotar credenciales de Redis) hay que revisar
**también** su configuración persistida en la DB, o el proxy seguirá apuntando
al host viejo aunque el Secret esté correcto:

- `LiteLLM_Config.general_settings` → puede tener
  `coordination_redis.host` con el host viejo.
- `LiteLLM_CacheConfig.cache_settings` → mismo problema, cifrado en reposo.

**Trampa mortal:** los endpoints de admin validan contra el cache, así que con el
circuit breaker abierto devuelven
`400 Authentication Error — Redis circuit breaker is open`. **La API no puede
arreglar el bug que la bloquea**: hay que ir por SQL directo (`update
"LiteLLM_Config" set param_value = param_value - 'clave' where
param_name='general_settings'`), con backup de la fila antes.

Diagnostico: `/cache/ping` (devuelve `cache_type`: tiene que decir `redis`, no
`LiteLLMCacheType.LOCAL`), `redis-cli pubsub channels` (los canales
`litellm_proxy.*` solo existen con suscriptor vivo → prueba positiva de que la
coordinacion funciona), y `redis-cli dbsize`.

**Prueba real de que el cache funciona** (no basta con que este configurado):
misma request dos veces, comparando `%{time_total}` y el header
`x-litellm-cache-key`. Con cache en Redis, la 2a llamada baja de ~1,3 s a ~0,009 s
y aparece el header. Ojo: en los aciertos `x-litellm-response-cost` puede seguir
reportando el costo real — revisar si los spend logs lo contabilizan.

Credenciales de Redis: `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` van en el
Secret `litellm-env` (ESO ← AKV). El bloque `redis:` del HelmRelease con
`host`/`passwordSecretName` **no es config del chart** (su `redis:` es el
subchart embebido): Helm lo ignora en silencio.

### GPT-6.x en Azure AI Foundry: `reasoning_effort` + function tools = HTTP 400

Los modelos gpt-6-luna, gpt-6.1-sol y gpt-6-astra en Azure Foundry rechazan la
combinación de `reasoning_effort` con function tools en `/v1/chat/completions`:

```
Function tools with reasoning_effort are not supported for gpt-6.1-sol in
/v1/chat/completions. To use function tools, use /v1/responses or set
reasoning_effort to 'none'.
```

**Solución en dos partes:**

1. **Hermes**: `agent.reasoning_effort: none` en `config.yaml` — deshabilita el envio
global de reasoning effort, que es incompatible con los modelos del router que usan
function tools. Si se necesita reasoning para modelos especificos que si lo soportan
(DeepSeek, Kimi), usar `agent.reasoning_overrides` por modelo.

2. **LiteLLM**: `additional_drop_params: [reasoning_effort]` **en el `litellm_params`
del router mismo** (`rc_azure_implementer`), NO en los modelos destino individuales.
El `auto_router` forwardea los params del request directamente al modelo elegido sin
consultar los `litellm_params` del modelo destino para `additional_drop_params` — un
drop declarado en `azure_ai/gpt-6-astra` se ignora cuando el modelo se llama via
router. El drop en el router aplica antes del forward y cubre todos los tiers.

El `reasoning_effort` es un parametro **soportado** por estos modelos (la doc de
Microsoft lo lista con ✅), asi que `drop_params: true` no lo dropea solo. Hace
falta `additional_drop_params` explicito.

```yaml
# ✅ Correcto — en el router, cubre todos los tiers:
- model_name: rc_azure_implementer
  litellm_params:
    model: auto_router/complexity_router
    additional_drop_params: [reasoning_effort]
    complexity_router_config:
      # ...

# ❌ Incorrecto — en el modelo destino, el router lo ignora:
- model_name: azure_ai/gpt-6.1-sol
  litellm_params:
    model: azure_ai/gpt-6.1-sol
    additional_drop_params: [reasoning_effort]  # no aplica via router
```

**Diagnóstico rápido** cuando el error persiste a pesar del fix de Hermes:
1. Revisar los request dumps de Hermes en `~/.hermes/sessions/request_dump_*.json`
   para confirmar que el body NO incluye `reasoning_effort`.
2. Si Hermes no lo envia pero el error sigue, es LiteLLM inyectando un default —
   el `additional_drop_params` debe estar en el router, no en los modelos destino.
3. Verificar que Flux ya reconcilio el cambio (`flux get hr litellm -n litellm`).

### La key de Azure de los modelos vive en la DB del proxy, NO en el Secret (ni en AKV)

Los modelos `azure_ai/*` **no leen `AZURE_AI_API_KEY` de `litellm-env`**: cada fila de
`LiteLLM_ProxyModelTable` referencia una *credential* de la UI
(`litellm_params.litellm_credential_name` → `LiteLLM_CredentialsTable`), y dos filas
llevan la `api_key` **inline** en la propia fila. Medido (2026-10-02): rotar la key en AKV,
refrescar el ExternalSecret y reiniciar el Deployment **no arregla nada** — el `401` sigue,
porque el proxy usa la key guardada en la DB (en el clúster, las dos credenciales azure y
las dos `api_key` inline apuntan todas a `https://reevolutiva-ai.services.ai.azure.com/`).
Antes de rotar: **contar los dueños de la key** (`env`, credencial, api_key inline).

Cómo verlo y arreglarlo:

```bash
# 1) ¿es la credencial o el env? los modelos azure salen con api_base=None en /model/info
curl -sS -H "Authorization: Bearer $MK" $PROXY/model/info | jq '.data[]|{model_name}' | head
# 2) descifrar (dentro del pod; usa LITELLM_SALT_KEY del env)
#    from litellm.proxy.common_utils.encrypt_decrypt_utils import decrypt_value_helper
#    sirve para litellm_credential_name, credential_values y las api_key inline
# 3) actualizar por API, no por SQL:
#    PATCH /credentials/{credential_name}   {"credential_name","credential_info","credential_values":{"api_key","api_base"}}
#    PATCH /model/{model_id}/update         {"litellm_params":{"api_key":"…"}}
# 4) verificar FUNCIONAL: POST /v1/chat/completions a cada modelo azure (200). El /health/liveliness no prueba la key.
```

Trampas concretas de este clúster: el nombre de la credencial **puede tener espacio final**
(`"Azure Reevolutiva "` → URL-encode); el Deployment es **`litellm`** en el ns **`litellm`**
y el ExternalSecret es **`litellm-env`** (no `litellm-proxy` ni `kelenfold`); el kubeconfig es
`/etc/rancher/k3s/k3s.yaml`; **no existe `make smoke-test`** (el gate real es `make health`
más un completion de verdad). Y al rotar una key de Azure: quedan **copias en texto plano**
fuera del clúster (`/opt/litellm/.env` y los `.env` de los perfiles de Hermes en `frontdoor`,
`(archivo de configuración local)` en `imac27`): limpiarlas es parte de la rotación, y el env muerto
`AZURE_OPENAI_API_KEY` de `litellm-env` no lo usa ningún modelo.

## vector-store / PGVector: dos trampas que solo aparecen con el pod corriendo

Ninguna de las dos la ve `make lint`; las dos cuestan un rato de diagnóstico.

- **El SDK de LiteLLM resuelve el proveedor por el prefijo del modelo.** Llamar
  `litellm.aembedding(model="bge-m3", api_base=<proxy>, ...)` con el alias pelado muere con
  `LLM Provider NOT provided. ... You passed model=bge-m3`. El proxy habla la API de OpenAI,
  así que la ruta correcta es `openai/<alias>`: el SDK postea el alias pelado a
  `/v1/embeddings` del proxy. **`ollama/<alias>` NO sirve** aunque el modelo sea de Ollama —
  `api_base` apunta al proxy, no a Ollama, y da `OllamaException 404`. Medido con las tres
  variantes en el pod.
- **La extensión `pgvector` va en el schema de la app, no en `public`.** Prisma deriva su
  `search_path` del parámetro `?schema=` del `DATABASE_URL` (`vectorstore`), así que una
  extensión en `public` **le es invisible** y `prisma db push` muere con
  `ERROR: type "vector" does not exist`. El script de `/docker-entrypoint-initdb.d` tiene que
  crear el schema **antes** y hacer `CREATE EXTENSION ... WITH SCHEMA vectorstore`. Y ojo:
  esos scripts **solo corren con el datadir vacío** — en una base ya inicializada el arreglo
  es manual (`DROP EXTENSION` + `CREATE EXTENSION ... WITH SCHEMA vectorstore`; el `DROP`
  falla si hay tablas dependientes, que es el comportamiento que se quiere).

### El registry interno no tiene las imágenes: hay que construirlas y pushearlas

ADR 0010 manda el registry interno como fuente de verdad, pero **no hay automatismo**: los
workflows `build-*.yml` publican a GHCR y **un runner de GitHub no alcanza el tailnet**. Si un
manifiesto referencia `registry.coyote-paridae.ts.net/<img>:<tag>` y el repositorio no está en
`/v2/_catalog`, el pod queda en `ErrImagePull` con un `not found` que parece un typo. Se
construye y se pushea desde un host del tailnet: `docker build --provenance=false -t
registry.coyote-paridae.ts.net/<img>:<tag> . && docker push ...`. El paquete de GHCR de un repo
privado **nace privado** y el clúster no tiene `dockerconfigjson`: no es un camino de escape.

**Jerarquía de registros (confirmada 2026-10-13):**

1. **Registry interno** (`registry.coyote-paridae.ts.net`) — fuente primaria. Los deployments
   de producción jalan de acá. Acepta push anónimo dentro del tailnet.
2. **ACR** (`reevolutivacr.azurecr.io`) — respaldo si el registry interno falla. Los secretos
   `acr-pull` ya existen en los namespaces `reevolutiva` y `wordpress`. Si el registry interno
   cae, los deployments deben re-apuntar a ACR y usar `imagePullSecrets: acr-pull`.
3. **GHCR** — **NO usar**. Deprecado como destino de publicación. Los workflows no publican a GHCR.

Los workflows `build-*.yml` actuales publican **directo al registry interno** (`--push` a
`registry.coyote-paridae.ts.net`), no a GHCR. El script `scripts/mirror-ghcr-to-registry.sh`
está deprecado (exit 1) — ese camino ya no existe.

Para publicar una imagen nueva o actualizada:

```bash
# vm-services. Requiere QEMU para emular arm64:
docker buildx build --platform linux/amd64,linux/arm64 --provenance=false \
  -t registry.coyote-paridae.ts.net/<app>:<tag> --push <build-context>
```

Para el respaldo en ACR:

```bash
docker buildx build --platform linux/amd64,linux/arm64 --provenance=false \
  -t reevolutivacr.azurecr.io/<app>:<tag> --push <build-context>
```

**El pull del registry interno funciona por nodo, no por clúster.** Medido: `vm-services` baja
403 MB en ~35 s; `vm-dev` se cuelga indefinidamente **sin fallar** — no aparece como
`ImagePullBackOff`, aparece como `Pulling` que nunca termina. Desde `vm-dev` el nombre resuelve
(`getent hosts`) y el TLS verifica (`Verify return code: 0`), así que no es DNS ni CA. La causa
raíz sigue abierta. Antes de mover una carga a un nodo, probar el pull ahí con un pod antifaz;
y si el pod cae en un nodo que se cuelga, borrarlo y dejar que reprograme. **El síntoma depende del nodo y de los reintentos**: el mismo pull puede verse como `Pulling` que nunca termina **o** como `ImagePullBackOff` tras cientos de intentos. Antes de buscar un tag mal escrito o un manifiesto roto, probar el pull en el nodo donde quedó el pod.

## Nodo Flatcar (producción) — resumen

Desde el PR #84 un nodo es **`kit@version` + su spec**, no un `.bu` por nodo:
`infrastructure/host/flatcar/{kit.conf, node.bu, nodes/<nodo>.conf}` + un único
renderer (`scripts/render-nodo.sh`). Los targets `make nodo-*` no cambiaron de nombre.
El diseño completo, las trampas y los contratos abiertos: `references/nodo-kit.md` y
`docs/host-inmutability-rfc.md` del repo. Lo que hay que tener presente SIEMPRE:

- **El sufijo del sysext no es `uname -m`**: Flatcar usa **`x86-64`** para amd64 y
  `arm64` para arm64; `-amd64.raw` y `-usr.raw` dan **404**, que **no rompe el render**
  —el nodo arranca sin sysext y nunca se une, sin error—. Por eso existe
  `make kit-verificar`.
- **Un bloque condicional de la plantilla que no se activa cae en silencio**: con
  `AGENT` sin exportar, el nodo salía **sin la línea `server:`** en el `config.yaml` y
  el chequeo de marcadores sobrantes no lo veía. Un cambio así solo se ve en el `.ign`.
- **La versión de la imagen de Azure NO es la del SO que va a correr**: Flatcar se
  auto-actualiza y reinicia solo (~18 min después del arranque).

### Sustrato `libvirt` (VMs Flatcar en `imac27`)

- **La clave del `fw_cfg` es `opt/org.flatcar-linux/config`.** Con
  `opt/com.coreos/config` o `opt/com.flatcar/config` la VM **arranca perfecta y el
  Ignition nunca corre**: no hay síntoma, hay una VM impecable y sin configurar.
- **El `.ign` de `fw_cfg` NO es un disco del dominio**: libvirt etiqueta solo los
  discos que ve en el XML, así que el archivo necesita su propia línea de
  abstracción en `/etc/apparmor.d/abstractions/libvirt-qemu`
  (`/var/lib/libvirt/flatcar-linux/** r,`) y ser legible por el usuario de qemu.
- **Una VM amd64 necesita `/etc/hostname` explicito**: la imagen de Azure lo trae
  puesto por el agente de la nube, la de QEMU no, y sin él la VM se registra con el
  nombre de la imagen en K3s y en el tailnet. Va en la plantilla bajo un guard por
  sustrato, para no cambiar el Ignition de Azure.
- **Rol `standalone` para las VMs que NO son nodo del clúster** (MinIO del contrato
  S3, VM de desarrollo): apaga sysext de K3s, `config.yaml` del agente, puente de
  node-ip, guarda anti-bucle e ISCSI de Longhorn. Sin ese rol intentan unirse.
- **Los bloques condicionales de la plantilla se resuelven recursivamente** en
  `render-bu.py`: si un bloque activo envuelve una condición en línea y no se
  procesa, la condición sale **literal** al Ignition (`@@?IF:AGENT@@server:`).
- **El disco de datos de una VM libvirt se llama `/dev/vdb`** y la spec declara label,
  ruta y padre derivado; el orden de los virtio es determinista con un solo disco de
  datos, y el `<serial>` deja además `/dev/disk/by-id/virtio-<serial>`.
- **`/data/workspace` es el checkout de `rdp-kelenfold`**: su `.gitignore` ya ignora
  `*.img`/`*.qcow2` (por eso el pool de discos no ensucia su working tree) pero **no**
  ignora `*.ign` — el Ignition, que lleva el token de K3s y la authkey, va a
  `/var/lib/libvirt/flatcar-linux/<vm>/`.
- **Arranque BIOS/SeaBIOS, no UEFI/OVMF** para estas VMs: es el camino que documenta
  Flatcar para libvirt; UEFI suma dos volúmenes de firmware que versionar y arrastra la
  trampa de q35/OVMF — **sin ACPI, QEMU rechaza el `fw_cfg` y el Ignition no corre**.

El detalle (rutas reales de los sysext, el bucle de Tailscale con su evidencia,
Tailscale SSH y el ACL del tailnet, trampas del primer provisionamiento) está en
`references/nodo-flatcar.md`. Lo que hay que tener presente SIEMPRE:

- **La versión de la imagen de Azure NO es la del SO que va a correr**: Flatcar se
  auto-actualiza y reinicia solo (~18 min después del arranque).
- **Los sysext no instalan donde uno asume** (Tailscale en `/usr/bin`, K3s en
  `/usr/local/bin`): usar `command -v`, nunca rutas fijas.
- **Validar el URN de la imagen ANTES de cualquier paso destructivo.**
- **El CLI de Azure lee `--custom-data` como latin-1**: nada fuera de ese rango en
  los scripts inline del Ignition.
- **Antes de declarar un pendiente, probar si hay camino programático**: el ACL de
  Tailscale SSH se arregló por API, no en la consola.
- **Un bucle de red se verifica con 6 muestras de 10 s, nunca con una sola.**

## Paperclip: persistencia de usuarios y roles

Para administrar acceso en una instancia self-hosted autenticada:

1. Lee la guía Members & Access y la referencia CLI Access vigentes; distingue `instance_admin` (toda la instalación), acceso/membresía por compañía y rol dentro de cada compañía.
2. En un primer bootstrap, usa el Board claim documentado solo si se cumplen sus precondiciones: modo `authenticated`, `local-board` es el único instance admin y hay challenge activo. El claim por UI, tras autenticar al usuario real, transfiere el admin al usuario, retira el placeholder y lo deja como owner activo en las compañías existentes.
3. Después del claim, administra `instance_admin` y acceso a compañías en Settings → Instance → Access (o mediante comandos documentados `paperclipai admin user ...`). Esa pantalla concede rol `operator` por defecto al crear acceso; eleva a `owner`/`admin` por separado desde Members en cada compañía.
4. Para CLI, usa `paperclipai auth login` y aprueba el challenge desde el navegador como usuario autorizado; añade `--instance-admin` solo para solicitar ese nivel. Confirma identidad con `paperclipai auth whoami` y valida cambios con comandos read-back (`admin user list`, `company-access`, `member list`).
5. Los usuarios, roles y membresías persisten en la base de datos de Paperclip; la recuperación duradera requiere preservar y restaurar DB y backups, no copiar roles a `app.env` ni a manifiestos GitOps. Comprueba el backup configurado y la restaurabilidad antes de dar por protegida la instalación.

Pitfalls:
- No modifiques tablas de auth/membresías directamente por SQL como procedimiento normal: los endpoints y flujos de Paperclip aplican validación, side effects y reglas de negocio que el esquema relacional por sí solo no garantiza.
- No cuentes con Board claim después de crear un administrador humano: es un bootstrap de una sola vez y solo aparece mientras el placeholder local sea el único administrador de instancia. Para cambios posteriores, usa Instance Access y los Members de cada compañía.
- No confundas acceso a compañía con rol de propietario: el acceso central puede crear una membresía `operator`; el rol elevado se configura aparte en la compañía.

## Rotar una credencial: no alcanza con cambiar el Secret

- **Redis**: reiniciar el Deployment (`redis` arranca con
  `--requirepass $REDIS_PASSWORD`), y LiteLLM también para que reconecte.
- **Grafana**: `GF_SECURITY_ADMIN_PASSWORD` **solo aplica en el primer
  arranque**; la credencial vive en el SQLite del PVC. Hay que correr
  `grafana cli --homepath /usr/share/grafana admin reset-admin-password "$GF_SECURITY_ADMIN_PASSWORD"`
  dentro del pod. Reiniciar no rota nada.
- Forzar el refresh de ESO es con **timestamp**, no con un token:
  `kubectl annotate externalsecret <n> force-sync=$(date +%s) --overwrite`.
  Con un valor no numérico el refresh no se dispara y parece que falló.

## Estado de la migración (2026-09-24)

En el clúster hay: LiteLLM, PostgreSQL, Redis, Grafana, Prometheus, Traefik,
Headlamp, Longhorn, Tailscale Operator, External Secrets, **y WordPress `familey.cl`**.
Supabase todavía no.

**`familey.cl` está cortado y sirviendo desde el clúster**: el túnel de Cloudflare rutea
`familey.cl` **a Traefik** (`traefik.flux-system.svc.cluster.local:80` + `httpHostHeader` por
hostname), que rutea por `Host` al Ingress público del sitio; el camino por el ingress de
Tailscale es sólo interno (validación). El procedimiento, el rollback y las trampas —cómo
identificar qué túnel sirve un conector, el puerto que el Service tiene que exponer, y el bucle
de 301 por `X-Forwarded-Proto`— están en `references/cloudflare-tunnel.md`.

**El patrón de repos legacy es `<app>` + `<app>-ws`** (`familey-ws` es el repo de
despliegue: compose, Dockerfile, scripts de ops). Hay que buscar el `-ws` de cada
proyecto antes de dar de baja un host. El submódulo **no** garantiza reproducibilidad:
medido en `frontdoor`, el código desplegado corría `18c6cb6f` mientras `origin/main`
estaba en `049759e3` — no correspondía a ninguna rama publicada. Detalle en
`docs/repos-y-despliegue.md`.

### Migración WordPress — reconocimiento verificado (2026-09-25)

| | `familey.cl` | `reevolutiva.com` |
|---|---|---|
| Host / arch | `frontdoor` / arm64 | `hosting` / amd64 |
| Imagen | propia `php:8.3-apache` (Dockerfile preservado en `apps/wordpress-familey/build-context/`) | `demyx/openlitespeed:bedrock` — **de terceros, amd64-only, sin Dockerfile** |
| ¿Corre en `produccion` (arm64)? | **sí** | **no** |
| Peso | 642 MB + DB 26 MB | **9,1 GB** + DB 421 MB / 800 tablas |
| Estructura | single-site | **multisite de 5 sitios** |

- **El código de `familey.cl` es un submódulo git** (`github.com/famileycl/familey.cl.git`):
  no hay que copiar 642 MB, solo los 33 MB de uploads y la base.
- **Decisiones tomadas:** `familey.cl` primero (es chico y su host está degradado).
  `reevolutiva.com` se reconstruye sobre `php:8.3-apache` con Dockerfile propio —
  es la única forma de que corra en arm64. **Se pierde el page cache de
  `litespeed-cache`** (es caché del servidor OpenLiteSpeed, no del plugin) y no hay
  plugin de caché alternativo instalado; se mitiga con Redis de objetos (el
  contenedor existe pero está **vacío**, `DBSIZE=0`) + el edge de Cloudflare.
  Ambos WordPress con su MariaDB y Redis **co-locados en `produccion`** (nodo único).
- **Faltantes antes del corte:** ningún secreto de ninguno de los dos sitios está en
  AKV (passwords de MariaDB, `JWT_AUTH_SECRET_KEY` y las 8 salts viven solo en
  `.env` en los hosts legacy). Y **no hay registry ni `imagePullSecret` en el repo**
  (todas las imágenes que corren son públicas), así que una imagen propia todavía no
  tiene cómo llegar al clúster.
- **Bug a corregir en el cutover:** el `.env` de `reevolutiva.com` define
  `WP_HOME=http://` con la base ya en `https://`; la constante de Bedrock gana
  sobre la DB y produce mixed content.

Interfaces internas expuestas y verificadas (PR #15): `grafana`, `prometheus`,
`longhorn`, `traefik` y `headlamp`, todas en `<nombre>.coyote-paridae.ts.net`.
La topología vive en `infrastructure/exposure/` (Kustomization `infra-exposure`,
`wait: false`).

**Inventario medido** — está completo en `docs/inventario-migracion.md` del repo.
Lo esencial:

- **`reevolutiva.com` es un WordPress MULTISITE de 5 sitios** (Bedrock, WP 7.0.3,
  PHP 8.3.24), base `reevolutivacom_dev` **421,5 MB / 800 tablas**, uploads
  **7,6 GB**. Caddy sirve 6 hostnames; **vivos**: `reevolutiva.com`, `www`,
  `upskills`, `orci`. `jump` y `talks` **sin DNS**. Plugins que definen el trabajo:
  BuddyBoss (+pro), LearnDash, Elementor (+pro), Fluent, WooCommerce.
- **`hosting` NO tiene ningún repo Git**: Caddy y el compose del sitio son a mano.
  En `/home/hosting/scripts/migration/` hay un **`migrate-site.sh`** reutilizable.
- **`frontdoor`**: WP `familey.cl` (WP 7.0.4, 642 MB, base 26,4 MB) + 9 servicios
  del proyecto `litellm` + Supabase (14 cont.) + `itc-*-dev`. Su `litellm` y `db`
  están **`Exited`** = ya migrados. `paperclip-data` = **13 GB**.
- **Decisión del dueño:** migrar paperclip + su Supabase (no descartarlos).
  Los dos WordPress van al **VPS limpio de producción**; los servicios internos
  (LiteLLM, monitoring, storage) quedan en `imac27`.

**Alcance fijado por el dueño:** de `hosting` lo **único** a recuperar es WP
`reevolutiva.com` + su MariaDB 10.11. Después de eso **el host se destruye**: su
stack Supabase, su LiteLLM, Prometheus, ollama y Caddy **no se migran**. Su K3s
huérfano tampoco requiere acción — muere con la máquina.
Pendiente en `frontdoor`: WP `familey.cl` + MariaDB 11.4, stack Supabase (16
contenedores), `hermes-gateway`, `paperclip`, `headroom`, `vector-store`,
`itc-*-dev`, `ollama`, cloudflared. **`frontdoor` está degradado: load 40-50, disco
89 %, y 1 de cada 3 requests a `familey.cl` muere por timeout.**

## Respaldos: qué hay y cómo se verifica

Todo en `infrastructure/backups/` (namespace `backups`, Kustomization `infra-backups`): dumps
diarios de PostgreSQL y MariaDB a PVC, copia fuera del clúster a Azure Blob (`backup-offsite` con
rclone), prueba semanal de restore y `RecurringJob/sites-backup-daily` para los volúmenes de los
sitios.

```bash
make backup-probar          # restaura los dos dumps en un servidor propio: PASS/PASS en ~220 s
make backup-offsite-probar  # sube al Blob y compara conteos origen/destino
```

**El hecho que explica casi todos los tiempos raros del clúster: el RTT entre nodos es de ~140 ms**
(casa ↔ Azure westus3; el ancho de banda sí está bien, ~8 MB/s). Todo protocolo con muchas idas y
vueltas se derrumba a ~30 KB/s, y Longhorn con 2 réplicas paga ese RTT en **cada** escritura. La
regla es **acercar el trabajo al dato** (`podAffinity` al pod de la carga, con `namespaces`
explícito). Números, trampas y cómo verificar cada pieza: `references/backups-y-rtt.md`.

## Reglas del repo

- Todo cambio entra por Git (rama + PR; `make lint` verde antes de mergear).
- **NUNCA aplicar manifiestos a mano (`kubectl apply`, `kubectl patch`, `kubectl delete`)
  como estrategia normal.** Si un cambio no está en Git, no existe. La recuperación
  operativa puntual fuera de Git deja issue + deuda técnica documentada.
- **NUNCA editar la config remota de un túnel por API y declarar el trabajo terminado.**
  Si la config no está en `infra/cloudflare/` (Terraform u otro manifiesto versionado),
  es drift. El túnel se declara en Git; la API es para aplicar, no para diseñar.
- **Para cambios de DNS/túnel en Cloudflare, primero ajustar `var.hostnames` en `variables.tf` y después `terraform plan`. Nunca parchear remoto aunque el backend de state no esté listo.** El cambio entra por PR (Git). Si el backend S3 no existe (endpoint `REEMPLAZAR` en `backend.tfvars`, contrato pendiente por MinIO diferido), migrar temporalmente a `backend 'local' {}` con nota de migración hacia S3.
- **El `terraform.tfstate` del borde NO está versionado** (`.gitignore`: `infra/**/*.tfstate`), así que el estado del túnel y de sus registros DNS vive **solo en la máquina donde se aplicó**. Antes de cualquier `apply` sobre `infra/cloudflare/`, confirmá que el state local es el vigente (`serial`, fecha de modificación) y que no hace falta re-importar; si se perdió, el plan intenta CREAR el túnel y los registros que ya existen y Cloudflare los rechaza por duplicados. No lo copies a Git ni a imágenes.
- **El `terraform apply` de Cloudflare requiere importar los recursos existentes al state local ANTES del plan.** Orden: (1) reemplazar `backend "s3" {}` por `backend "local" {}`, (2) `terraform init -reconfigure`, (3) import el túnel: `terraform import cloudflare_zero_trust_tunnel_cloudflared.cluster <account>/<tunnel_id>`, (4) import cada registro DNS por hostname con su zone/record ID (consultable por API), (5) plan, (6) apply. Sin eso el plan intenta CREAR los recursos que ya existen.
- **`www` no es “otro sitio” en el mapa del túnel cuando la política es canonical host.** Declarar sólo el apex en `hostnames` y mover la redirección `www -> @` a una regla de redirect de Cloudflare (Bulk Redirect / Page Rule), porque DNS+ingress sólo resuelven tráfico; no expresan semántica de canonicalización. Documentar en README que es una regla de página, no DNS ni túnel.
- **Para eliminar subdominios del túnel: editar `var.hostnames` en `variables.tf` y aplicar Terraform.** El cambio entra por PR (Git). DNS wildcard no se toca (cubre los que quedan). Si el backend no está operativo, migrar a local temporal: `backend 'local' {}` + `terraform init -reconfigure` + importar túnel + dns_records, aplicar, y commitear el cambio de backend para migrar al S3 cuando exista.
- **Al buscar una credencial en AKV: listar TODOS los nombres, no filtrar.** Un token guardado con un nombre ortográficamente distinto no aparece en un `az keyvault secret list --query "[?contains(name, 'lo-esperado')]"`. La búsqueda que funciona es: `az keyvault secret list --vault-name <v> --query "[].name" -o tsv | grep -i <substring>`.
- **El token `CLOUDFLARE-API-TOKEN` puede NO tener permiso para Rules/Lists (Bulk Redirects).** Eso requiere `Account → Rules → Edit` adicional a Tunnel+Zone+DNS. Para Page Rules hacen falta `Zone → Page Rules → Edit`.
- **Validá el token de Cloudflare ANTES de construir sobre él.** En el vault conviven varias claves con nombres parecidos y **no todas sirven para la API**: algunas devuelven `{"success":false,"errors":[{"code":1000,"message":"Invalid API Token"}]}`. La comprobación es un GET, barato y sin efectos: `curl -sS -H "Authorization: Bearer $TOK" https://api.cloudflare.com/client/v4/user/tokens/verify` → `"status":"active"`. Con eso confirmás además que el token puede leer túneles y (si el plan lo permite) escribir DNS, sin adivinar por el nombre de la clave. Leer el token a una variable de shell, nunca imprimirlo.
- **Los tokens de *conector* de túnel no son tokens de API.** `cloudflare-tunnel-*-token` autentica el proceso `cloudflared`; para leer configuración por API necesitás un API token. Y ojo: el endpoint de configuraciones devuelve el objeto bajo `.result.config`, mientras la lista de túneles viene como `.result[]` — `jq` distinto para cada uno.
- Nada de secretos en el repo: SOPS+age o External Secrets → AKV.
- Exposición solo por Tailscale Operator; nunca `port-forward` permanente ni
  puertos públicos.
- Un namespace por dominio, declarado en `infrastructure/configs/namespaces.yaml`.
- Commits en conventional commits, **sin** atribución a IA.
- **`gh pr merge` sin número de PR falla en silencio** (imprime la ayuda o nada).
  Pasar siempre el número: `gh pr merge <n> --repo … --squash --subject "…"`.
  Y crear el PR + mergearlo en el mismo comando falla por mergeabilidad aún no
  calculada: separarlos unos segundos.
- **Para limpiar ramas remotas tras squash merge, no uses `git branch --merged` como criterio único.** Con squash, esa señal puede dejar ramas ya integradas como si siguieran abiertas. Audita por contenido (`git diff --stat origin/main..origin/<rama>`) o por estado real del PR (`gh pr list --state merged --head <rama>`), y borra solo lo que cumpla criterio explícito; lista aparte las ramas de rescate/archive/worktree para decisión del dueño.
- **No declares desplegado un cambio que solo tiene commit o PR abierto.** Para un encargo cuyo resultado es el despliegue, exige merge a `main` y verifica la revisión aplicada por Flux y el runtime. Si el usuario pidió preparar solo el PR, el PR abierto es el entregable: no lo merges sin autorización y explicita que el despliegue queda pendiente. Una Kustomization que sigue en una revisión vieja **no aplicó tu merge**: si `status.lastAppliedRevision` no coincide con el commit mergeado — o su condición dice `Running health checks for revision main@<sha>` con `Ready: Unknown` — el fix todavía no está en el clúster, y con `wait: true` un workload que nunca queda sano mantiene el reconcile chequeando la revisión anterior, así que el arreglo no aterriza hasta que ese health check pase o expire. Compara la revisión aplicada antes de concluir que el fix falló.

## Traspaso entre sesiones: el handoff con gates

Cuando una tarea de infraestructura no cabe en una sesión (migración de almacenamiento, cambio de
topología, rotación de credenciales), el entregable de la sesión que la abre **es el documento de
traspaso**, no un resumen en el chat.

1. El handoff es un **archivo versionado en el repo**: `docs/handoffs/<tema>.md`, en su propia rama
y por PR. Un traspaso que solo vive en el chat muere con la sesión.
2. Enlázalo desde el issue de seguimiento en el mismo movimiento: el issue es el hilo de
continuidad, el doc es el detalle.
3. Cada fase termina en un **gate**: comando exacto + resultado esperado + quién lo ejecuta. Sin
gate verde no se avanza, y el resultado del gate se registra en el issue.
4. El doc lleva siempre: reglas de ejecución (qué pasos son de un humano y cuáles del agente),
estado verificado con la fecha, alcance y fuera de alcance, gates, secuencia con responsables,
riesgos con rollback, DoD, y un **bloque de arranque** listo para pegar en la sesión siguiente
(repo, checkout, issue, doc, estado, reglas, accesos, próxima acción concreta).
5. Escribe el estado como **medición, no como recuerdo**: capacidades, porcentajes y réplicas salen
de comandos corridos en esa sesión. Un handoff con datos de memoria manda a la sesión siguiente a
perseguir un clúster que ya cambió.
6. Antes de tocar nada en una fase destructiva, guarda el rollback (el `spec`/JSON previo) **dentro
del propio doc**.

Plantilla lista para copiar y modificar: `templates/handoff-con-gates.md`.
