# Trampas verificadas (no supuestas)

Cada regla acá se comprobó contra el clúster o contra la API real. Si una deja de
ser cierta, se corrige: una regla vieja que se aplica igual hace más daño que no
tenerla.

## GHCR y los tokens

**GHCR no soporta fine-grained personal access tokens.** Solo classic. La
consecuencia práctica: el permiso `Packages` **no aparece** en la interfaz de los
fine-grained, y eso no es un error de configuración — la opción no existe.
Síntoma si lo intentás igual: token válido (HTTP 200, identidad correcta) que
GHCR deniega con `Resource not accessible by personal access token`.

El camino limpio no es un PAT: **un workflow de GitHub Actions que publica con el
`GITHUB_TOKEN` del job**. No hay credencial de vida larga que rotar ni guardar en
AKV, y el build queda versionado junto al Dockerfile. Requiere
`permissions: packages: write` en el job.

Si hace falta un PAT classic, este link evita que la interfaz marque el scope
`repo` (innecesario y demasiado amplio):
`https://github.com/settings/tokens/new?scopes=write:packages`.

**Los paquetes pueden ser públicos sin riesgo cuando la imagen es solo runtime**
(PHP, extensiones, config de servidor — sin código del sitio ni secretos). El
código va en un volumen y los secretos llegan en runtime desde AKV. Público ⇒ el
clúster la baja **sin `imagePullSecret`**, y desaparece toda la complejidad de
mantener un token de pull.

## DNS del tailnet

Síntoma, medido: `server misbehaving` / `no such host` **intermitentes** en
`GitOperationFailed`, `HelmRepository/<x> Failed` y `ExternalSecret/<x> UpdateFailed`.
Se autorrecuperan, así que el árbol de Flux termina verde y el error se confunde con
ruido de despliegue — por eso conviene diagnosticarlo con la métrica, no con el ojo.

Causa: MagicDNS activo y **cero nameservers globales** en el tailnet (`dns: []`). Sin
upstreams, `tailscaled` sólo resuelve nombres del tailnet y responde **SERVFAIL** a todo
lo público:

```
journalctl -u tailscaled | grep 'no upstream resolvers set'
dns: resolver: forward: no upstream resolvers set, returning SERVFAIL
```

`100.100.100.100` queda en el `resolv.conf` del nodo (systemd-resolved lo toma como
global, junto a los del ISP), kubelet lo propaga y CoreDNS lo usa como upstream — el
Corefile de k3s hace `forward . /etc/resolv.conf`. Resultado: **1 de cada 3 consultas
del clúster arrancaba contra un resolutor roto**. Medido:
`coredns_proxy_request_duration_seconds_count{to="100.100.100.100:53",rcode="SERVFAIL"}`
= 7.828, con reparto parejo entre los 3 upstreams (11.484 / 11.513 / 11.458).

Diagnóstico (sin adivinar):

```bash
dig +short @100.100.100.100 github.com                      # SERVFAIL = roto
dig +short @100.100.100.100 headlamp.coyote-paridae.ts.net  # si esto resuelve, el fallo es sólo el reenvío de lo público
curl -s -H "Authorization: Bearer $TOK" https://api.tailscale.com/api/v2/tailnet/-/dns/nameservers   # {"dns":[]}
curl -s http://<pod-coredns>:9153/metrics | grep 'proxy_name="forward"'   # rcode por upstream
```

El token sale del OAuth client de AKV (`tailscale-client-id` /
`tailscale-client-secret`, scope `all`). Un contador de SERVFAIL que se congela =
arreglado; uno que sube = el problema sigue.

Arreglo: `POST /api/v2/tailnet/-/dns/nameservers` con `{"dns":["1.1.1.1","8.8.8.8"]}`.
**No hace falta** tocar `overrideLocalDNS`: los dispositivos siguen usando su DNS local,
lo que se repara es el forwarder de MagicDNS. Revertir = el mismo POST con `{"dns":[]}`.
Procedimiento formal y verificación en `docs/tailnet-dns.md`.

- **El `forward` del Corefile no se puede reemplazar desde el repo.** El Corefile de k3s
  ya tiene `import /etc/coredns/custom/*.override`, pero eso sirve para *otros* plugins:
  dos `forward` en el mismo server block no compilan. La palanca está en el resolutor del
  nodo (kubelet `--resolv-conf`) o en el upstream (tailnet), nunca en el Corefile.
- **IPv6 sin ruta pero con AAAA.** El nodo resuelve AAAA y no tiene ruta v6, así que el
  primer intento muere con `dial tcp [2606:…]:443: connect: network is unreachable`.
  Reproducible: `curl -6` falla en milisegundos, `curl -4` da `200`. Se corrige filtrando
  AAAA en CoreDNS (`coredns-custom`; el Deployment ya monta `custom-config-volume`).
- **`resolv.conf` del nodo con entradas de más**: systemd-resolved lista los del ISP dos
  veces más los de Tailscale (v4 y v6) → kubelet aplica sólo 3 y avisa
  `DNSConfigForming: Nameserver limits were exceeded` en los pods con `hostNetwork`
  (`coredns`, `node-exporter`). Cosmético.
- **CoreDNS corre 1 réplica, sólo en `imac27`**: si ese nodo cae, el clúster se queda sin
  resolución de nombres.

## Parchear un addon de k3s (CoreDNS) — lo que NO funciona

Intento medido: darle a CoreDNS una réplica por nodo. Terminó en un corte de DNS
de ~2m50s y en un revert. Las cuatro trampas, con su evidencia:

- **El manifiesto del addon no se edita: k3s lo re-escribe.** En este nodo vive en
  `/data/workspace/k3s/server/manifests/coredns.yaml` y los docs de k3s son
  explícitos: *"Manifests for packaged components are managed by K3s, and should
  not be altered. The files are re-written to disk whenever K3s is started"*.
- **Un apply server-side PARCIAL choca contra el manager del addon.** Los campos
  están reclamados por `deploy@<hostname>` (client-side apply del deploy
  controller de k3s). Verificado sin tocar nada:
  `kubectl apply --server-side --dry-run=server -f <parcial>.yaml` →
  `Apply failed with 3 conflicts: conflicts with "deploy@imac27" using apps/v1:
  .spec.replicas, .spec.strategy.rollingUpdate.maxSurge,
  .spec.template.spec.tolerations`. Un apply por SSA necesita hacerse cargo de
  esos campos, y eso es exactamente lo que k3s va a volver a escribir.
- **`force: true` en una Kustomization de Flux es `kubectl apply --force`: borra y
  recrea.** Con un objeto parcial la recreación NO pasa la validación
  (`spec.selector: Required value`, `spec.template.spec.containers: Required
  value`) y **el objeto queda borrado**. Pasó: el Deployment de CoreDNS se borró,
  el clúster se quedó sin resolución de nombres hasta que el deploy controller de
  k3s re-aplicó su manifiesto ~3 minutos después. Reglas: **nunca `force: true`
  con manifiestos parciales**, y para tocar algo crítico, `prune: false` (si no,
  sacar el archivo del repo hace que Flux borre el objeto, y k3s no lo recrea
  hasta el próximo arranque).
- **Un addon de k3s no se reconcilia solo.** Una anotación puesta a mano sobre el
  Deployment sobrevivió **más de 9 minutos**: k3s re-aplica cuando cambia el
  archivo o cuando el objeto desaparece, no por drift periódico.
- **El camino soportado es `--disable=<componente>` y declarar el tuyo con otro
  nombre** (docs de k3s y respuesta de mantenedores: *"The only supported way to
  modify the configuration of packaged components like CoreDNS is to `--disable`
  and deploy your own... give the file a different name"*). Es lo que este repo ya
  hace con traefik. Para CoreDNS implica recrear el Service `kube-dns` con
  `clusterIP: 10.43.0.10` explícito (todos los pods apuntan ahí) y aceptar una
  ventana de DNS durante el cambio.

Corolario de método: un cambio sobre el DNS del clúster se prueba primero con
`--dry-run=server` y, si toca objetos vivos, con un objeto de prueba — no en el
camino crítico. El corte no dejó daño visible (sin 5xx en el sitio, sin errores en
los pods), pero se llevó 3 minutos de DNS por no haber hecho el dry-run antes.

## Tailscale ACL: qué acepta cada campo

**En el `dst` de una regla `ssh` solo valen `tag:` y `autogroup:`.** Ni nombres de
dispositivo, ni IPs, ni CIDR, ni `*` — el validador los rechaza. Para dar SSH a
un host concreto hay que **etiquetarlo**; no hay forma de apuntar a un
dispositivo por nombre.

Consecuencia que muerde: **etiquetar un dispositivo lo saca de `autogroup:self`**
(deja de ser un dispositivo personal). Si tu propia máquina queda etiquetada,
tiene que estar cubierta por otra regla o te quedás afuera.

Validar antes de aplicar: `POST /api/v2/tailnet/-/acl/validate`. Y el ACL es
HuJSON: tiene comentarios, así que un `json.load` pelado falla.

La regla por defecto para dispositivos propios usa `action: check`, que abre un
navegador. Eso rompe cualquier automatización por SSH — no es un problema de
llaves ni de host keys.

## Verificación

**Una Kustomization suspendida no es una falla.** Está declarada y esperando a
propósito. Cualquier chequeo de "todo en True" tiene que excluir las suspendidas
y reportarlas aparte, o convierte una decisión en un falso error.

**No leer `kubectl get` por número de columna.** El orden cambia entre versiones y
`$NF` termina tomando la edad en vez del estado. Leer JSON:
`status.conditions[?(@.type=="Ready")].status`. Esta trampa apareció dos veces en
la misma sesión: una en un script y otra en un comando de resumen escrito a mano.

**Un `sleep` seguido de un volcado no verifica nada.** Si no hay aserción que
pueda fallar, el paso siempre da verde. Esperar la condición real con timeout, y
que el fallo sea ruidoso.

**Un gate que no puede fallar no es un gate.** Aplica igual a los scripts de
aceptación: probar que fallan cuando deben, no solo que pasan cuando deben.

## Antes de escribir código para algo que "falta"

**Buscar si ya existe.** El DoD pedía un `scripts/restore-databases.sh` que no
faltaba: `make backup` y `make restore` ya existían y funcionaban para PostgreSQL.
Lo que faltaba de verdad era otra cosa (la ruta MariaDB). Escribir el script
"faltante" habría duplicado una capacidad existente.

## Ubicación de cargas

El mecanismo y su verificación están en
`docs/runbooks/migracion-cargas-entre-nodos.md`. Lo esencial: se declara en
`clusters/<cluster>/` con un patch de Flux apuntado por label, y se verifica con
**dos** pruebas — positiva (el pod aterriza) y negativa (sin la tolerancia queda
`Unschedulable`). Solo la positiva no prueba nada: un pod puede agendarse en
cualquier nodo si el taint no está haciendo su trabajo.

## Arquitectura

`imac27` es **amd64** y `produccion` es **arm64**. Todo artefacto —imágenes,
sysexts, binarios— tiene que ser multi-arquitectura o elegir explícitamente una.
Un binario de la arquitectura equivocada arranca igual y falla de formas que no
señalan la causa.
