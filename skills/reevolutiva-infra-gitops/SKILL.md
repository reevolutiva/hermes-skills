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

### LiteLLM lento o inestable en tailnet: medir ruta, scheduling y presión de nodo antes de tocar app config

Cuando la UI de LiteLLM “demora muchísimo en cargar”, separar primero red de app y luego estabilidad del pod.

**Secuencia mínima (en este orden):**

```bash
# 0) kubeconfig correcto (imac27 ya no corre k3s)
make kubeconfig
KUBECONFIG=$HOME/.kube/config kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'

# 1) medir desde cliente: DNS/TLS/TTFB/total
for i in 1 2 3; do
  curl -sS -o /dev/null --connect-timeout 10 --max-time 100 \
    -w 'http=%{http_code} dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}\n' \
    https://litellm.coyote-paridae.ts.net/ui/
done

# 2) medir dentro del clúster (sin hop cliente→tailnet)
kubectl -n litellm run curl-debug --image=curlimages/curl:8.12.1 --restart=Never --rm -i --command -- \
  sh -c 'for u in / /ui/ /health/liveliness; do
    printf "%s " "$u";
    curl -sS -o /dev/null -w "code=%{http_code} connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n" \
      http://litellm.litellm.svc.cluster.local:4000$u;
  done'

# 3) comprobar estabilidad de scheduling y presión del nodo
kubectl -n litellm get deploy,pod -o wide
kubectl -n litellm get events --sort-by=.lastTimestamp | tail -40
kubectl describe node vm-worker | grep -E 'Ready|DiskPressure|MemoryPressure|SystemOOM|NodeNotReady' -A3
kubectl top node vm-worker
```

**Regla:** si `/ui/` responde rápido dentro del clúster pero lento/intermitente desde cliente, el cuello está en la ruta tailnet/cliente. Si además hay `Evicted`, `NodeNotReady` o `SystemOOM`, tratar primero estabilidad del nodo/pod antes de culpar al frontend.

**Corolario operativo:** LiteLLM sin `resources.requests/limits` (incluido `ephemeral-storage`) y sin afinidad/nodeSelector queda a merced del scheduler; ante presión de nodo, reprograma o se evicta y la UI se vuelve intermitente.

**Flujo de hardening LiteLLM:**
1. Verifica kubeconfig activo, labels/taints, nodo de PostgreSQL/Redis, arquitectura de la imagen y presión de nodo antes de editar.
2. Declara CPU, memoria y `ephemeral-storage` requests/limits en el workload. Si se fija una clase de nodo, declara selector y toleration en `clusters/<cluster>/apps.yaml` (no en el manifest genérico de la app), y agrega `dependsOn: infra-nodos`.
3. Si el cambio toca `clusters/<cluster>/apps.yaml`, reconcilia primero la Kustomization raíz `flux-system`; luego avanza por dependencias (`infra-controllers` → `infra-configs`/`infra-storage` → `apps-databases` → `apps-litellm`). Una revisión raíz aplicada no significa que sus Kustomizations hijas ya estén al día.
4. Mide 12–20 muestras externas de `/ui/` antes y después (DNS, connect, TLS, TTFB, total), resume p50/p95 e informa el tamaño de muestra. Una muestra pequeña sin picos no demuestra que una cola histórica desapareció.
5. Verifica rollout, nodo, recursos efectivos, eventos recientes, `flux get ks`, health con certificado válido y login UI real antes de cerrar.

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

- **El `forward` del Corefile no se puede reemplazar desde el repo.** El Corefile de k3s ya
  tiene `import /etc/coredns/custom/*.override`, pero eso sirve para *otros* plugins: dos
  `forward` en el mismo server block no compilan. La palanca está en el resolutor del nodo
  (kubelet `--resolv-conf`) o en el upstream (tailnet), nunca en el Corefile.
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

**El pull del registry interno funciona por nodo, no por clúster.** Medido: `vm-services` baja
403 MB en ~35 s; `vm-dev` se cuelga indefinidamente **sin fallar** — no aparece como
`ImagePullBackOff`, aparece como `Pulling` que nunca termina. Desde `vm-dev` el nombre resuelve
(`getent hosts`) y el TLS verifica (`Verify return code: 0`), así que no es DNS ni CA. La causa
raíz sigue abierta. Antes de mover una carga a un nodo, probar el pull ahí con un pod antifaz;
y si el pod cae en un nodo que se cuelga, borrarlo y dejar que reprograme.

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
- **El `terraform apply` de Cloudflare requiere importar los recursos existentes al state local ANTES del plan.** Orden: (1) reemplazar `backend "s3" {}` por `backend "local" {}`, (2) `terraform init -reconfigure`, (3) import el túnel: `terraform import cloudflare_zero_trust_tunnel_cloudflared.cluster <account>/<tunnel_id>`, (4) import cada registro DNS por hostname con su zone/record ID (consultable por API), (5) plan, (6) apply. Sin eso el plan intenta CREAR los recursos que ya existen.
- **`www` no es “otro sitio” en el mapa del túnel cuando la política es canonical host.** Declarar sólo el apex en `hostnames` y mover la redirección `www -> @` a una regla de redirect de Cloudflare (Bulk Redirect / Page Rule), porque DNS+ingress sólo resuelven tráfico; no expresan semántica de canonicalización. Documentar en README que es una regla de página, no DNS ni túnel.
- **Para eliminar subdominios del túnel: editar `var.hostnames` en `variables.tf` y aplicar Terraform.** El cambio entra por PR (Git). DNS wildcard no se toca (cubre los que quedan). Si el backend no está operativo, migrar a local temporal: `backend 'local' {}` + `terraform init -reconfigure` + importar túnel + dns_records, aplicar, y commitear el cambio de backend para migrar al S3 cuando exista.
- **Al buscar una credencial en AKV: listar TODOS los nombres, no filtrar.** Un token guardado con un nombre ortográficamente distinto no aparece en un `az keyvault secret list --query "[?contains(name, 'lo-esperado')]"`. La búsqueda que funciona es: `az keyvault secret list --vault-name <v> --query "[].name" -o tsv | grep -i <substring>`.
- **El token `CLOUDFLARE-API-TOKEN` puede NO tener permiso para Rules/Lists (Bulk Redirects).** Eso requiere `Account → Rules → Edit` adicional a Tunnel+Zone+DNS. Para Page Rules hacen falta `Zone → Page Rules → Edit`.
- Nada de secretos en el repo: SOPS+age o External Secrets → AKV.
- Exposición solo por Tailscale Operator; nunca `port-forward` permanente ni
  puertos públicos.
- Un namespace por dominio, declarado en `infrastructure/configs/namespaces.yaml`.
- Commits en conventional commits, **sin** atribución a IA.
- **`gh pr merge` sin número de PR falla en silencio** (imprime la ayuda o nada).
  Pasar siempre el número: `gh pr merge <n> --repo … --squash --subject "…"`.
  Y crear el PR + mergearlo en el mismo comando falla por mergeabilidad aún no
  calculada: separarlos unos segundos.
- **Nunca cerrar una tarea sin haber hecho push + PR mergeado a `main`.** Un commit
  local o un cambio aplicado con `kubectl` no es un entregable: el estado deseado
  vive en `main` y lo aplica Flux. Si no está mergeado, la tarea no está terminada.
