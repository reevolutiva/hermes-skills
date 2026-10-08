---
name: wordpress-bedrock-migration
category: infrastructure
version: 0.3.0
description: "Migrar Bedrock WP (single-site o multisite) a K3s."
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wordpress, bedrock, migration, kubernetes, k3s]
    related_skills: [reevolutiva-infra-gitops, infrastructure-bootstrap]
---

# WordPress Bedrock → K3s (single-site y multisite)

## When to Use
Use when migrating a **Bedrock** WordPress site — single-site o **multisite**, sobre OpenLiteSpeed/Demyx o sobre una imagen propia `php:8.3-apache` — desde un host Docker/VPS a **K3s**, evitando **mixed content** y minimizando el riesgo de corte.

## Production Guardrails (for this user's infra)
- If the site is **production with uptime 100%**, do **not** place it on a home iMac node as the primary hosting target.
- **NO usar la regla "frontdoor-first" (obsoleta).** `frontdoor` NO es nodo del
  clúster K3s de `imac27` (verificado: `kubectl get node frontdoor` → `NotFound`).
  Es un host Docker legacy en retiro. Programar pods ahí es imposible.
  Los WP vivos al 2026-09-24 son:
  - `reevolutiva.com` → host **`hosting`** (100.114.42.76), contenedor
    `reevolutiva-wp` (`demyx/openlitespeed:bedrock`), core en
    `/demyx/web/wp/wp-includes/version.php`, MariaDB 10.11, detrás de Caddy +
    Cloudflare. **Este es el WP productivo principal.**
  - `familey.cl` → host **`frontdoor`** (100.89.96.125), `wordpress-familey`
    (`familey-bedrock:php8.3`, `127.0.0.1:8088`), MariaDB 11.4, detrás del túnel
    Cloudflare `litellm-ingress-1`.
  Ambos destinos válidos hoy son el clúster de `imac27` o el VPS limpio nuevo.

## Bedrock Layout Notes (important)
Bedrock multisite deployments often place core + config under nested paths like:
- `wp/web/wp/wp-config.php`
- `wp/web/wp/wp-content/…`
- uploads may appear under `wp/web/app/uploads/…`

Always confirm the expected mount target inside the container **matches the bedrock layout**, and extract `wp/.env` from the tarball to understand initial settings.

## Goal
1) Transfer DB dump + WP files into K3s persistent storage.
2) Ensure the site serves content with **HTTPS**.
3) Run **WordPress core upgrade** for multisite (defer plugin/theme upgrades).
4) Validate quickly and run an anti-mixed-content remediation.

## Workflow (Investigar → Definir → Planificar → Implementar → Actualizar)

### 1) INVESTIGAR (origen)
- Confirm runtime: bedrock multisite layout.
- Extract versions:
  - WordPress core: `$wp_version` from `wp-includes/version.php`.
  - Required PHP version often tied to container expectations.
- Identify DB engine/version and dump timestamp.
- Check for embedded `http://<domain>` strings in:
  - the SQL dump,
  - and WP files tarball (plantillas y recursos HTML que embeben URLs absolutas).

### 2) DEFINIR (target)
- Architecture (recommended):
  - `MariaDB StatefulSet + PVC` (fresh DB).
  - `WordPress Deployment + PVC` mounted at the bedrock expected path.
- Scheduling:
  - **NO programar en `frontdoor`**: es un host Docker legacy, no un nodo del clúster.
  - Declarar la ubicación **en `clusters/<cluster>/`**, no en el manifiesto de la app:
    `nodeSelector` **más** la toleración del taint del nodo destino (la etiqueta sola no
    alcanza si el nodo está tainted).
  - Gate previo obligatorio: la arquitectura del destino tiene que soportar las
    imágenes (ver `references/image-architecture-checks.md`).
- Ingress/Tunnel:
  - Use the cluster's ingress wiring (Traefik + Cloudflare Tunnel and/or pre-existing ingress wiring).
  - Gate on: **Ingress must route `reevolutiva.com` to the WP Service and present TLS/HTTPS**.
- Upgrade scope (scope A):
  - Run **multisite core upgrade only** (defer plugin/theme upgrades).
- Anti mixed content requirement:
  - all domain constants and DB references must be `https://`.

### 3) PLANIFICAR (migración)
- Data staging: llevar el dump SQL y el tarball de WP al PVC, en dos movimientos
  distintos porque fallan distinto:
  - **Tarball grande (código): `kubectl cp` al pod y extraer DENTRO del pod.** No usar
    `gzip -dc <tarball> | kubectl exec -i -- tar -x` para un archivo grande: el pipe
    muere con **SIGPIPE** a mitad del stream (`tar: Child died with signal 13`) y el PVC
    queda a medio llenar. Y el exit code del pipeline es el del último comando, no el
    del `tar`: verificar que los archivos de entrada existan en el destino, no confiar
    en el código de salida.
  - **Dump SQL: import desacoplado dentro del pod** (`nohup … &` + escribir el exit code
    a un archivo) para que ningún timeout del cliente lo mate a mitad de camino. Es
    **idempotente** — el dump hace `DROP TABLE IF EXISTS` + `CREATE TABLE` — así que
    re-correrlo es seguro; verificar contando tablas contra el origen.
  - **Excluir `.env` del tarball al extraer** (`--exclude='<raíz>/.env'`): el backup trae
    las credenciales del host legacy y la fuente correcta es el Secret.
  - No dejar una copia suelta en el host legacy (se va a apagar) ni asumir que el
    destino comparte el layout de rutas del origen.
  - Keep dump/tarball immutable (do not edit content in-place).
- DB import:
  - Create a Job/initJob that imports SQL into the fresh MariaDB using a client container.
  - Ensure the Job reads from the mounted frontdoor path.
- Files extraction:
  - Extract WP tarball into the WP PVC mount target matching bedrock layout.
- Critical env settings from `wp/.env`:
  - The tarball may include `WP_HOME` / `WP_SITEURL` set to `http://…`.
  - Update those values (or enforce equivalent settings via Deployment env vars) **before** upgrade cutover.

### 4) IMPLEMENTAR (orden estricto)
1. Create namespace.
2. Apply MariaDB PVC + StatefulSet en el **nodo destino** (ver arriba: `frontdoor` NO
   es un nodo del clúster, y la ubicación se declara en `clusters/<cluster>/`).
3. Run DB import Job; wait for DB readiness.
4. Deploy WordPress; mount WP PVC; set environment consistent with production domain and HTTPS.
5. Validate ingress routing to the WP Service for `https://reevolutiva.com`.
6. Smoke checks:
   - bedrock-equivalent login/entry route returns expected HTTP status and HTML shell.
   - check that served HTML does not contain `http://<domain>`.
   - verify theme parity at DB level: `SELECT option_name, option_value FROM wp_options WHERE option_name IN ('template','stylesheet');` and confirm the referenced theme directories exist in `web/app/themes/`.
   - if `stylesheet` points to a child theme, verify the parent theme is present and readable; child-only restore is not visually equivalent.
   - run an asset sweep from rendered HTML (`curl -sSL` + extract asset URLs and curl each) covering **images + CSS + JS + fonts**; treat any 404/5xx in theme/logo/core assets as migration failure.
  - run a route sweep beyond home (`/wp-json/` + at least 2 content URLs like `/contacto/` or equivalent). A home `200` with route `404` means rewrite/docroot drift, not a healthy migration.
  - when parsing HTML for assets, ignore template literals/placeholders (`${...}`, `{{...}}`) to avoid false broken-link reports.
7. Upgrade core (scope A):
   - Run `wp core update --network` (multisite).
8. Anti mixed content remediation (hard gate):
   - `wp search-replace 'http://<domain>' 'https://<domain>' --network --all-tables`
9. Re-scan:
   - `http://<domain>` occurrences in HTML/static sources.
   - verify static resources load without browser mixed-content errors.

### 5) ACTUALIZAR DOCUMENTACIÓN
- **Cuando el dueño pide el estado o "qué queda", entregar un inventario itemizado,
  no un resumen en prosa** (ya marcó que un resumen no le alcanza): tabla de
  **deuda / cómo se verificó / quién la cierra**, agrupada por área (bloqueante,
  datos, operación, documentación, migración). Cada ítem con su evidencia —"0
  CronJobs en el clúster", "`backup-target` no existe", "pull anónimo = 403"— porque
  sin evidencia es una opinión, y una lista de opiniones no se puede priorizar.
  Volcarlo también a un issue consolidado (`technical-debt`), y distinguir **trampa
  latente** de **bug activo** cuando algo está mal configurado pero hoy nada lo
  dispara: cambia la prioridad y evita alarmas falsas.
- Record:
  - bedrock image/container tag
  - DB import Job approach and logs
  - wp core upgrade output
  - anti mixed content command output
- Update: `infrastructure/docs/reports/wordpress-phase3-transfer.md`

## Mixed Content Checklist (hard gate)
- Replace must be **network-wide** (multisite + all tables).
- HTML response for the home page and at least one multisite page must contain **only** `https://<domain>` for the site’s own domain.
- Static assets (CSS/JS/img) referenced from HTML must be `https://`.

## Pitfalls (learn once, apply everywhere)
- **Bedrock lee su configuración con `getenv()`**, así que las **variables de entorno
de Kubernetes alcanzan: no hace falta ningún `.env` dentro del contenedor.** Lo no
secreto (`DB_NAME`, `DB_USER`, `DB_HOST`, `WP_HOME`, `WP_SITEURL`) va declarado a la
vista en el Deployment; lo secreto (contraseñas + las 8 salts) por ExternalSecret y
`envFrom`. Esto elimina el paso de extraer `wp/.env` del tarball y evita que la
configuración quede escondida en un archivo no versionado. **Al extraer, excluir el
`.env` igual** (`tar --exclude='<raíz>/.env'`): el del backup es del host legacy, con
credenciales viejas, y no tiene por qué quedar en el volumen.
- **Las 8 salts se CONSERVAN del sitio original.** No son un secreto rotable sin
costo: cambiarlas invalida todas las sesiones y cookies de los usuarios.
- **El código del sitio va en el PVC, no en la imagen.** Es lo que ya hacía el host
legacy (donde `bedrock/` era un volumen): la imagen queda como runtime del web server
y no hay que reconstruirla en cada deploy. `fsGroup: 33` (www-data) para que el PVC se
monte escribible sin pelear permisos, **junto con `fsGroupChangePolicy: OnRootMismatch`
(obligatorio: sin eso el `fsGroup` reescribe el volumen entero en cada arranque, ver el
punto siguiente)**, y `strategy: Recreate` porque el PVC es RWO y el
árbol de archivos es compartido (dos pods escribiendo ahí es peor que un corte breve).
- **`fsGroup` sin `fsGroupChangePolicy` reescribe TODO el volumen en cada arranque del
pod.** La política por defecto es `Always`, así que kubelet hace un `chown` recursivo del
PVC entero cada vez que lo monta: medido en un Bedrock, **38.033 archivos / ~4 minutos**
de I/O. Sobre un volumen replicado por red (Longhorn con la réplica en el otro nodo) eso
deja el sitio **~10 minutos** sin servir: los workers de Apache quedan en estado `D`
(espera de I/O ininterrumpible), PHP no responde **ni en 40 s** y el pod no llega a
`Ready`, así que el Service se queda sin endpoints y aparece un `502` que parece de
Cloudflare. `OnRootMismatch` hace el chown **sólo si el dueño de la raíz no coincide**: el
mismo reinicio pasó de ~10 min a **68 s y sin ningún chown**. Es lo que el propio kubelet
pide en el warning (`configured fsGroup ... would change ownership ...`) — si ese warning
aparece en los eventos, el arranque va a tardar.
- **`Ready` no significa que la app responda: hay un arranque en frío de ~60 s.** Tras cada
reinicio, los estáticos salen en **7 ms** y **PHP da timeout sin devolver un byte**
durante ~60 s, y después se recupera solo. No es la base (las conexiones están
establecidas) ni el volumen (`healthy`, réplicas `running`): con `opcache` activo las
primeras requests leen archivos fríos del volumen replicado, y los **44 millicores** de
CPU del contenedor son espera de I/O, no cómputo. Firma del diagnóstico: `ps -eo pid,stat,comm`
con **todos** los workers en `D`, `/proc/net/tcp` para confirmar que las conexiones a la
base están establecidas (hex little-endian: `84312B0A:0CEA` = `10.43.49.132:3306`), y
`grep -E '^(Dirty|Writeback):' /proc/meminfo` bajo para descartar backlog del kernel. Se
resuelve con la misma decisión de capas de arriba: código en la imagen ⇒
`opcache.validate_timestamps=0`.
- **En imágenes mínimas, verificar que la herramienta exista antes de creer un resultado
vacío.** En `php:8.3-apache` puede no haber `time` ni `find`, y su `sh` es `dash` (sin
`/dev/tcp`): así, un `find` ausente devuelve *"0 archivos en 2 ms"* y el `/dev/tcp` un
*"FALLA 0 ms"* — dos falsos negativos que se leen como hallazgos. Medir con
`date +%s%N` alrededor del comando, confirmar rutas con `ls`, y desconfiar de todo
resultado instantáneo.
- **`siteurl` apunta al CORE, no al sitio.** En Bedrock `home` = la URL del sitio
  (`https://<dominio>`) y `siteurl` = la del core (`https://<dominio>/wp`). Pedir `/wp/`
  devuelve un **404 con el tema del sitio** — parece una migración rota y no lo es.
  Antes de diagnosticar rewrites, leer `home` y `siteurl` en `wp_options`.
- **Verificar que los plugins cargan no necesita navegador.** `GET
  /wp/index.php?rest_route=/` devuelve la REST API completa: cientos de KB de JSON
  prueban que WordPress arrancó, la base responde y los plugins están cargados — es la
  forma barata de validar WooCommerce/Amelia/BuddyBoss **antes** de tocar el DNS. Un 404
  temático con el nombre del sitio en el `<title>` ya prueba core + tema: el 404 es del
  router, no del stack. Y para pedir la home sin depender de DNS, desde el propio pod:
  `php -r '$c=stream_context_create(["http"=>["header"=>"Host: <dominio>","ignore_errors"=>true]]); echo file_get_contents("http://127.0.0.1/",false,$c);'`
  (funciona porque Bedrock toma su config de `getenv()` y de la base, no del host de la
  petición).
- **Sigue redirects al validar HTML público.** Usa `curl -L` en checks de home: WordPress puede responder `307` primero (canonical/version query) y un `curl` sin `-L` te deja validando headers o body vacío en vez del HTML final.
- **El corte es mover el ORIGEN del túnel de Cloudflare, no el DNS.** El DNS ya apunta
  al túnel; lo que cambia es a qué sirve el túnel. De ahí una consecuencia que se asume
  al revés: **la zona del dominio puede estar en OTRA cuenta de Cloudflare y el corte
  funciona igual** — no usar "la cuenta no lista la zona" como bloqueante. Lo que hay
  que confirmar es que la cuenta sea la del túnel y que la credencial pueda **leer y
  escribir** su configuración.
- **El archivo de config del túnel no es autoritativo, y creer que sí lo era cuesta una
  caída.** cloudflared *lee* su `config.yml` (`Settings:
  map[config:/etc/cloudflared/config.yml]`) y a continuación aplica reglas que **le
  llegan de Cloudflare** — `Updated to new configuration … version=N` — y que **no
  coinciden con el archivo** (menos hostnames, sin el wildcard). Editar el archivo local
  y reiniciar **no cambia el ruteo**. Un contenedor lanzado con `TUNNEL_TOKEN` es remoto
  por construcción y el archivo local es un vestigio. **Antes de prometer un corte, leer
  ese log y confirmar de dónde salen las reglas.** Si son remotas, el corte es un `PUT`
  a la API y no hay camino por SSH ni editando archivos: endpoints, payload y
  verificación en `references/cloudflare-tunnel-cutover.md`.
- **La credencial puede estar en el vault y aun así no encontrarla: filtrar por el
  nombre la esconde.** Un token guardado con el nombre mal escrito no aparece en un
  `secret list` filtrado por el nombre correcto, y la conclusión errónea ("no hay
  credencial, no hay camino") bloquea un corte que sí era posible. **Listar TODOS los
  nombres del vault y leerlos**, en vez de filtrar por el nombre que uno espera.
- **Un token de API *account-scoped* responde `1000 Invalid API Token` en
  `/user/tokens/verify` y funciona igual.** Ese endpoint valida tokens de usuario; los
  `/accounts/<id>/…` responden bien. No declarar muerto un token por ahí: la prueba es
  el endpoint que se va a usar. Y el **token del conector** (el `TUNNEL_TOKEN` del
  contenedor) **no es un token de API** — da `6003 Invalid request headers`; sirve para
  identificar cuenta y túnel, porque es base64 de un JSON con `a`, `t` y `s`, y los dos
  primeros se leen sin exponer el secreto.
- **Pasar una credencial de un contenedor al vault sin que pase por stdout.** El token no
  se lee con un `printenv` dentro del contenedor, y un `docker inspect` completo **imprime
  el secreto**: extraerlo a una variable con el parseo del lado local —
  `TOK=$(ssh <host> docker inspect <cont> | python3 -c "…Config.Env…")` — y verificar por
  **largo** (`${#TOK}`) y releyendo del vault, comparando byte a byte. Dos trampas: el
  `--format '{{…}}'` de `docker inspect` **no sobrevive al `ssh`** (muere con
  `template parsing error: … unclosed action`), y **no hay que reemplazar un secreto del
  vault cuyo origen no se puede identificar**: se agrega un nombre propio (`…-front`) y la
  ambigüedad se reporta como decisión del dueño, porque pisarlo puede romper un consumidor
  que no está a la vista.
- **Apuntar el túnel a un nombre del tailnet da 502.** cloudflared en un contenedor con
  `network_mode: host` no resuelve MagicDNS: el nombre `.ts.net` no resuelve y el sitio
  responde **502** aunque el mismo `curl` desde el host funcione. Usar la **IP del
  tailnet** del proxy de ingress más `originRequest.originServerName` con el nombre, para
  que SNI y verificación TLS sigan correctos. Es un destino **interino y frágil** — si el
  operator recrea el proxy la IP cambia y el sitio cae: el destino correcto es
  cloudflared **dentro** del clúster.
- **La prueba de un corte son los logs del origen nuevo, no el código HTTP.** Cerrar
  cuando la request propia aparece en los logs del pod nuevo **y** deja de aparecer en el
  host legacy. El rollback es el mismo `PUT` con el valor anterior, con el contenedor
  legacy **todavía corriendo**: sin eso no hay rollback.
- **Después del corte el árbol sigue vivo y otras manos escriben en él.** Entre dos
  comandos tuyos puede aterrizar un cambio ajeno (otra sesión de agente, otra persona) que
  rompa producción, y aparece en `git log` sin que hayas hecho nada. Antes de commitear,
  releer `git log --oneline -3` y `git status`; y cuando algo se rompe sin que hayas tocado
  nada, **mirar los commits recientes ajenos antes de buscar la causa en tu propio
  trabajo**. Señal útil: un `git add <dir>` que falla con `pathspec did not match any
  files` sobre archivos ya commiteados y sin modificar significa que **el trabajo ya está
  en Git**, no que falte la ruta.
- **Medir el delta de datos ANTES de cortar, no después.** Comparar la última escritura
  del sitio vivo (`select max(post_modified) from wp_posts`, el conteo de pedidos y de
  reservas) contra el timestamp del backup restaurado. Si la última escritura es
  **anterior** al backup, la copia ya es el estado actual y no hace falta dump fresco; si
  es posterior, hay que re-sincronizar o el corte pierde esos datos. Medirlo es lo que
  permite afirmar "cero pérdida" con evidencia en vez de suponerlo.
- **No se puede hacer una pasada humana en la copia antes de cortar.** `siteurl` y `home`
  son el dominio canónico: cualquier login en la copia —incluso por un hostname del
  tailnet— **redirige al dominio real**, así que la copia no es navegable como sitio
  propio. Las dos salidas son cortar y validar contra el dominio real, o cambiar
  `siteurl`/`home` en la copia (y entonces los enlaces y medios absolutos del contenido
  siguen apuntando al dominio viejo: la validación es parcial). **No prometer una
  validación previa que no se puede hacer.**
- **El readiness probe hereda ese mismo redirect canónico, y con una réplica eso es una
  caída.** El probe pide una ruta de WordPress (p. ej. `/wp/wp-login.php`) con **la IP del
  pod como `Host`**; WP ve un host que no coincide con su `siteurl` y responde el redirect
  — y **el kubelet lo sigue**: sale a internet, resuelve el dominio público y espera hasta
  el timeout. El pod pasa a `NotReady` sin que nada esté caído, sale de los endpoints del
  Service, y con **una sola réplica el Service se queda sin ninguno: `502` intermitentes**
  que parecen del origen o de Cloudflare. Diagnóstico: `kubectl get events` con
  `Readiness probe failed: … context deadline exceeded` **y** `ProbeWarning: Probe
  terminated redirects`. Arreglo: apuntar el probe a algo que **no redirija** — un archivo
  estático del docroot prueba Apache y el PVC y no tiene efectos; si se quiere ejercitar
  PHP y la base hace falta un `healthz.php` propio, y **`httpHeaders: Host: <dominio>` no
  alcanza**: la API lo acepta (`--dry-run=server` pasa) y el `302` **sigue igual** (medido),
  porque el redirect lo decide WordPress, no el host de la petición. Candidato verificado:
  un **estático del core** (`/wp/wp-includes/js/jquery/jquery.min.js` → `200` en **571 ms**,
  sin redirect), que prueba Apache y el PVC pero **no PHP**. Con más de una réplica el síntoma se disimula, pero el probe sigue
  midiendo la salud de un tercero.
- **Antes de reiniciar cualquier cosa que esté delante de producción: validar el archivo
  y medir la indentación en vez de asumirla.** Un `config.yml` con la indentación mal
  puesta hace que cloudflared **no arranque** y el sitio devuelve `530` hasta restaurar
  el backup. Tres reglas: (1) parsear el YAML (`python3 -c 'yaml.safe_load(...)'`)
  **antes** del `restart`; (2) un `sed` con la indentación equivocada **no matchea y no
  avisa** — deja el archivo intacto y da la falsa sensación de haber cambiado algo,
  mientras uno con la indentación "casi" correcta lo rompe: usar un patrón que
  **capture** la indentación y reimprimir la estructura parseada para confirmar;
  (3) con el backup hecho y el rollback **probado** (~40 s) el corte es seguro de
  intentar — sin eso no es un corte, es un cambio de producción.
  - **En el mismo PR del corte, apagar el CI del repo del proyecto que despliega al
    host legacy.** Esos workflows montan el FS del host (p. ej. `-v
    /opt/hosting/<sitio>:/opt/hosting/<sitio>`) y despliegan ahí: después del corte
    son una mina, porque un push a `main` intentaría desplegar a un host que ya no
    sirve el sitio. Los workflows de validación (lint, checks de PR) sí conviene
    conservarlos.
  - Y un `200` detrás de Cloudflare **no prueba** que el origen esté vivo: puede ser
    caché. Validar con URL no cacheable (`?cb=$RANDOM`) **y** contra el origen directo.
- **P0: Arquitectura del destino vs imágenes (bloqueante silencioso).** Antes de
  planear la migración, comparar la arquitectura del host de origen, la del destino y
  la de **cada** imagen. Caso real: el destino es **arm64**; `familey.cl` sale de un
  Dockerfile portable (`FROM php:8.3-apache`) → reconstruible en cualquier arch, pero
  `reevolutiva.com` corre `demyx/openlitespeed:bedrock`, que es **amd64 en todos sus
  tags** y no tiene Dockerfile propio → **no arranca en un nodo arm64**. Detectarlo
  ANTES de mover datos, no al final. Receta y comandos: `references/image-architecture-checks.md`.
- **P0b: Una imagen construida en el host no es reproducible.** Las imágenes de estas
  cargas se construyen con `build: context:` en los compose del host y **no están en
  ningún registry**: si el host se apaga, se pierde la capacidad de reconstruirlas.
  Preservar los contextos (Dockerfile + configs, **sin** `.env`) en el repo y
  publicarlas o transferirlas al destino antes del corte.
  - **El registry ya existe y el camino es Actions + GHCR.** Las imágenes se
    construyen en un workflow del monorepo y se publican en `ghcr.io/reevolutiva/<app>`
    con el **`GITHUB_TOKEN` del job** (`permissions: packages: write`): no hay PAT de
    vida larga que rotar. Tienen que ser **multi-arquitectura**
    (`linux/amd64,linux/arm64`); un build así bajo QEMU tarda **~30-35 min** y no está
    colgado — medir el avance con el `startedAt` del paso (`gh run view <id> --json
    jobs`) y no con la sensación del tiempo transcurrido.
  - **Un paquete creado por un workflow nace PRIVADO** y el clúster no lo puede bajar:
    eso **no** es un manifiesto mal escrito ni un `imagePullSecret` que falta.
    - **Repo ≠ paquete:** hacer público el *repositorio* no publica el *paquete*. Dar la
      ruta exacta
      (`https://github.com/orgs/<org>/packages/container/<paquete>/settings` → Danger
      Zone → Change package visibility); el dueño cree haberlo resuelto y el clúster
      sigue sin poder bajar la imagen.
    - **Por API no se puede, y no es por el token:** para paquetes de **organización** el
      endpoint de visibilidad devuelve **404 con cualquier credencial**, incluido el
      `GITHUB_TOKEN` del job con `packages: write`. Es un límite del endpoint. Paso
      manual del dueño: avisarlo apenas se publica el primer paquete, no cuando falla un
      despliegue.
    - La lectura confiable es `gh api … --jq .visibility` con el token del job (dejarlo
      como paso del workflow de build); un `curl` anónimo al registry **no distingue**
      público de privado ni de inexistente. La prueba definitiva es el kubelet: un pod de
      prueba con la imagen, y `failed to fetch anonymous token: 401` = no es pública.
    - Un paquete **público puede ser la base de uno privado** — la visibilidad no se
      hereda. Y un paquete borrado **se reconstruye, no se recupera** (no hay papelera):
      es barato si el build vive en el repo. Recetas: `references/ghcr-registry.md`.
  - **Si el paquete debe quedar privado, el pull necesita un PAT *classic*.** GHCR no
    acepta fine-grained para pulls, y la trampa es el diagnóstico: el fine-grained
    **obtiene token de registro (200)** y el manifest devuelve **403 DENIED**. La prueba
    que vale es pedir el manifest, no obtener el token.
  - **Verificar el vínculo entre el monorepo y el repo del proyecto antes de
    asumirlo.** Buscar `.gitmodules` y grepear el monorepo por la URL del repo del
    proyecto: **una mención en prosa en un README no es un mecanismo**.
  - **Un `.gitmodules` declarado NO significa código pinneado.** El directorio del
    sitio en el host legacy suele ser un repo de **despliegue** (convención `<app>-ws`
    en la org: compose + Dockerfile + Makefile + scripts de ops) que declara la app
    como submódulo — pero `git submodule status` devuelve `-<sha>` (no inicializado) y
    `git status` marca el directorio con ` m`: **el árbol desplegado no es la revisión
    commiteada**, es lo que haya en el disco. No planificar el corte sobre la
    suposición de que un `git clone` reproduce lo que corre, ni decidir "no hace falta
    copiar el código" en base al submódulo.
  - **El repo de la app es fuente, no un árbol ejecutable.** Es Bedrock gestionado con
    Composer: `vendor/` y `wp/` **no** están commiteados (cientos de archivos contra
    decenas de miles en el árbol desplegado). Un clone pelado no arranca el sitio:
    necesita `composer install`. Para **validar paridad**, extraer el árbol real del
    host; para la **imagen capa 2**, construir desde una revisión verificada +
    `composer install`.
  - **El mismo commit no produce la misma imagen.** Un rebuild del mismo Dockerfile dio
    digests distintos (el `apt-get install` resuelve versiones nuevas cada vez). El
    único pin real es el **digest**, no el tag ni el SHA del commit — que es
    exactamente por qué la capa 2 se fija por digest.
  - **Decisión abierta: dónde vive el código del sitio.** Hoy la regla de esta skill
    es *el código en el PVC* (espeja el modelo legacy y evita reconstruir imagen por
    cada plugin). La alternativa propuesta es **por capas**: el runtime (PHP +
    extensiones + config) como imagen pública de la plataforma, y el sitio como imagen
    del repo del proyecto (`FROM` la anterior) **fijada por digest** en el monorepo —
 inmutable y revertible con un PR, a costa de reconstruir imagen en cada cambio de
 código. **Decidida por el dueño: se aplica.** Construir la capa 2 desde la
 **revisión verificada** — la que realmente corría, medida contra el árbol desplegado
 — y **no** desde `origin/main`, que puede no corresponder a nada publicado. La regla
 *código en el PVC* sigue vigente para lo que ya está corriendo; se pasa a capas al
 estabilizar.
- **Longhorn es el storage del clúster (`imac27`), no `local-path`** (el runbook
  original asumía local-path/hostPath). El default del chart (**3 réplicas**)
  en un clúster de dos nodos hace nacer `degraded` a todo volumen nuevo, y eso **no es
  esperado: es un defecto de configuración** — con penalidad de escritura medida
  (inicializar una MariaDB tardó 8 min). El valor del clúster es **2** y se declara en la
  **StorageClass por defecto** (`persistence.defaultClassReplicaCount`), no solo en
  `defaultSettings.defaultReplicaCount` — el setting **no** gobierna los PVC. Con 2 nodos
  una réplica vive en el otro, así que **cada fsync cruza la red**: medido, un restore de
  26 MB tardó >7 min con los volúmenes ya sanos. Para contenido casi estático es
  tolerable; para restauraciones masivas o un multisite de 800 tablas, decidirlo con los
  números a la vista — la palanca es `dataLocality: best-effort`.
- **P1: Production uptime requirement violation:** no poner el destino productivo
  en el iMac de casa como hosting primario.
- **P2: Local storage co-location:** With `local-path`/PV/hostPath, DB and WP files must be on the **same node**.
- **P3: Credenciales reales desde AKV (sin placeholders):** Para producción, **no** uses `CHANGE_ME` en manifiestos. Crea/actualiza secretos en **Azure Key Vault** y **derívalos** a `Secret` de Kubernetes (p.ej. generando un `Secret` desde valores obtenidos con `az keyvault secret show`).
- **P4: `wp/.env` contains `http://`**: If `WP_HOME`/`WP_SITEURL` in the tarball are `http://…`, you must correct/enforce HTTPS before cutover.
- **P5: Bedrock nested paths:** The correct mount target may be `wp/web/wp/` rather than a flat WordPress root.
- **OLS nace con `indexFiles index.html` (sin `index.php`) y la portada se sirve con HTTP 404 aunque el contenido se vea.** El vhost `useServer 0` hace que una petición a un DIRECTORIO se resuelva sirviendo `index.php` con status 404 en vez de 200: el sitio se ve completo (el tema renderiza la home) pero el código de respuesta es 404. Señal de diagnóstico: `body class="home … page-id-2"` con HTTP 404 (no confundir con `class="error404 …"` que es el 404 del tema, de una URL inexistente). Arreglo: `indexFiles index.php, index.html` en el vhost (`sed` idempotente en el entrypoint declarado). **`lshttpd -r` no alcanza: hace falta `lswsctrl restart`.** El mismo arreglo va en el Dockerfile (fondo) y en el arranque declarado del Deployment (inmediato, retirable al publicar imagen).
- **P5b: Nested WP admin path mismatch (`wp/wp-admin` or docroot nesting):**
  - In some Bedrock layouts the WordPress entrypoints live under nested prefixes.
  - If the web server docRoot is `/var/www/html` but the WP core entrypoints (e.g. `wp-admin/`, `wp-config.php`) live under `/var/www/html/<nested>/...`, the web server returns **404** for `/wp-admin/`.
  - **Fix pattern (recommended):** use an `initContainer`/one-shot Job to flatten/copy the WordPress core from the nested bedrock folder into the docRoot expected by the web server.
  - **Verification gate:** inside the running pod, `test -e $DOCROOT/wp-config.php` and `test -d $DOCROOT/wp-admin` must succeed.
  - If using **litespeedtech/openlitespeed**, ALSO verify that the container’s vhost **docRoot** (e.g. via `vhRoot` + `docRoot`) points to the mounted location; otherwise you can still get 404 even when `/var/www/html/wp-admin` exists.
  - See also: `references/wp-bedrock-docroot-404-wp-admin.md`.
- **P6: Ingress wiring mismatch:** `ingressClassName` y el cableado del túnel tienen
  que rutear el dominio al Service del WP **y presentar TLS/HTTPS** antes de declarar
  éxito. En este repo los manifiestos viven en **Git** y los aplica Flux: **nada de
  copiar archivos a mano al nodo** (Flux los revierte o los duplica). Si algo hace
  falta en el host, es deuda técnica que se codifica en el repo.
- **La imagen Demyx deja un `wp-config.php` dentro del core que referencia rutas
  inexistentes en la imagen destino.** `demyx/openlitespeed:bedrock` coloca un
  `wp-config.php` en `web/wp/wp-config.php` que carga `/demyx/vendor/autoload.php` —
  una ruta que no existe en `php:8.3-apache`. Ese archivo gana sobre el
  `wp-config.php` correcto en el docroot porque WordPress busca primero en su propio
  directorio. Remedio: borrarlo o renombrarlo (`.demyx.bak`) y colocar el
  `wp-config.php` de Bedrock en `web/wp-config.php` (un nivel arriba del core, desde
  donde `dirname(__DIR__)` resuelve a la raíz del PVC).
- **`vendor/` está gitignored y la imagen destino no lo incluye: hay que copiarlo del
  origen.** En un Bedrock gestionado con Composer, `vendor/` no está en el repo ni en
  los tarballs de código. La imagen Demyx lo traía built-in; `php:8.3-apache`, no.
  Sin `vendor/autoload.php`, `config/application.php` falla con `Class "Env\Env" not
  found`. Copiarlo del origen en un paso separado: `tar -czf - ./vendor` (excluyendo
  `.env`), transferir con el mismo patrón que el código, y extraer en la raíz del PVC
  (`/var/www/html/vendor/`). No intentar `composer install` dentro del pod salvo que
  la imagen tenga composer y la red del pod alcance packagist.
- **Transferir archivos grandes (cientos de MB/GB) entre el host legacy y el clúster:
  nunca `scp` ni `rsync` en un solo hop cuando el RTT es alto (~140 ms).** Incluso con
  buen ancho de banda (~8 MB/s), `scp` de un archivo grande se cuelga a mitad de camino
  y `rsync --partial` puede no converger. El patrón que funciona: (1) comprimir en el
  host de origen (`tar -czf`), (2) transferir con `ssh <host> 'cat <file>' > <local>`
  en background con `notify=true`, (3) `kubectl cp <local> <ns>/<pod>:/tmp/`, (4)
  extraer DENTRO del pod (`tar -xzf`). Nunca usar `ssh … | kubectl exec -i` para esto:
  los timeouts del API de Kubernetes matan el stream.
  **Limpia inmediatamente el tar del contenedor (`rm /tmp/*.tar*`)** tras extraer: en
  nodos con disco pequeño, un tar multi-GB en `/tmp` dispara `DiskPressure` y evicciones
  en cascada.
- **Un readiness probe que da 404 porque el PVC está vacío deja el pod `NotReady`
  aunque después se copien los archivos.** Kubelet hace backoff del probe y no
  re-evalúa hasta el siguiente intervalo; el pod puede quedar horas en ese estado.
  Después de poblar el PVC, borrar el pod (`kubectl delete pod`) para que el
  ReplicaSet cree uno nuevo con estado limpio, o forzar una recreación. El manifiesto
  debe tener `strategy: Recreate` (RWO) así que no hay downtime por el reemplazo.
- **Bedrock con `.htaccess` en Apache exige tres cosas simultáneas: módulo + override + archivo.**
  Si falta cualquiera de las tres, el sitio puede dar home `200` pero rutas amigables `404` o `500`: 
  (1) `mod_rewrite` cargado, (2) `AllowOverride All` en el `DocumentRoot` real, (3) `web/.htaccess` presente con reglas de WordPress. Verifícalo dentro del pod antes de culpar al túnel/ingress.
  En imágenes `php:8.3-apache`, habilitar `rewrite headers expires remoteip` durante build/entrypoint y comprobar con probes de ruta (`/wp-json/` y una página de contenido), no solo con `/`.
- **En multisite, "muchas tablas importadas" no prueba import completo.** Un restore
  parcial puede tener cientos de tablas `wp_<id>_*` y aun así faltar las tablas de red
  (`wp_blogs`, `wp_site`, `wp_sitemeta`, `wp_signups`, `wp_registration_log`), lo que
  degrada en redirects a `wp-signup.php?new=...`. El gate de aceptación del restore en
  multisite debe incluir presencia de tablas globales de red, no solo conteo total.
- **Después de restaurar DB, valida `template`/`stylesheet` antes de declarar paridad visual.** El dump puede dejar activo un theme distinto al esperado (por ejemplo fallback a tema por defecto) y el sitio seguirá "arriba" pero con identidad visual incorrecta.

## Rollback
- Keep SQL dump + WP tarball immutable.
- If upgrade fails:
  - restore DB from the dump using a new DB volume (or reset PVC) and re-deploy WP files.
- Do not delete PV data until staging validation passes.

