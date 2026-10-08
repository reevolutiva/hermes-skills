# Imágenes en GHCR: qué puede consumir el clúster y cómo se verifica

## La regla que no se ve en los manifiestos

**En el clúster no existe ningún secreto de tipo `kubernetes.io/dockerconfigjson`.** Verificalo antes de
suponerlo:

```bash
kubectl get secret -A --field-selector type=kubernetes.io/dockerconfigjson --no-headers
# → No resources
```

Consecuencia: **todo lo que un pod traiga de GHCR tiene que ser un paquete público**, o hay que decidir y
declarar el secreto de pull (en Git, nunca a mano en el nodo).

## Cómo se mide la visibilidad (el único test que vale)

El pull anónimo es exactamente lo que hace el clúster. Usá el token anónimo de GHCR, no `gh api`:

```bash
P=wordpress-familey
R=$(curl -sS "https://ghcr.io/token?service=ghcr.io&scope=repository:reevolutiva/$P:pull")
if echo "$R" | grep -q '"token"'; then
  TOK=$(echo "$R" | sed 's/.*"token":"\([^"]*\)".*/\1/')
  curl -sS -o /dev/null -w 'tags/list HTTP %{http_code}\n' \
    -H "Authorization: Bearer $TOK" "https://ghcr.io/v2/reevolutiva/$P/tags/list"
else
  echo "DENEGADO → paquete privado o inexistente: el clúster no lo puede traer"
fi
```

- `token` anónimo + `tags/list` **200** → público, el clúster lo trae sin credencial.
- `DENIED` en el token → **privado o inexistente**; en ambos casos el clúster no lo trae.
- **`gh api /orgs/<org>/packages/...` no sirve como test**: devuelve `404 Package not found` cuando el
token no tiene `read:packages`, aunque el paquete exista y sea público. Falso negativo.

Medido el 2026-09-28: `wordpress-familey` público (200, y su pod efectivamente corre así);
`wordpress-producto` y `wordpress-producto-plugins` **DENEGADOS**.

## Público ≠ código expuesto: medilo en las capas, no en el Dockerfile

Un paquete público asusta, pero **lo que expone son sus capas**, no el nombre ni la intención del
Dockerfile del repo (que además puede no ser el que construyó el tag). Se mide sin credenciales:

```bash
# indice -> manifest de la arquitectura -> config blob (Env/Cmd/Labels/history) y tamanos de capa
# 19 capas / 252 MB comprimido + la unica capa propia = COPY apache-bedrock.conf
#   -> runtime puro: NO hay arbol del sitio adentro
```

- **Runtime puro** (imagen base + extensiones + vhost): el paquete público revela el *stack*
  (PHP/Apache, que es Bedrock, los nombres de host) y **ninguna** linea de codigo nuestra.
  Ejemplo medido: `wordpress-familey:php8.3` — 19 capas, 252 MB, historia de build con un solo
  `COPY apache-bedrock.conf`; el contenido del sitio vive en el PVC, no en la imagen.
- **Codigo empaquetado**: ahi si es exposicion real. `wordpress-producto` pesa **1,1 GiB** porque
  `COPY`ea `plugins/`, `themes/` y `mu-plugins/` al docroot. Un paquete con codigo **no puede ser
  público**.
- La asimetria es la trampa: el paquete *runtime* puede ser público sin drama; el paquete *con
  codigo* privado obliga a declarar el camino de pull. Y hoy no hay ninguno de los dos declarado —
  ver arriba: sin `dockerconfigjson` y sin `registries.yaml`, lo privado entra **sólo por import a
  mano**, y `imagePullPolicy: IfNotPresent` lo disimula.
- Corolario de plataforma: una imagen importada a mano suele ser de **una sola arquitectura**. El
  `1.1 GiB` de `wordpress-producto` es **amd64-only**, asi que no puede correr en `produccion`
  (arm64) por mas que el nodo este sano. Verificarlo con
  `sudo k3s ctr images ls | grep <imagen>` antes de mover una carga ahi.

## La trampa que hace creer que todo está en Git

`imagePullPolicy: IfNotPresent` (lo que usan todos los manifiestos) **oculta** el problema: si la imagen
ya está en el containerd del nodo, el pod levanta aunque el registro no la tenga o sea privado. Y la
imagen suele haber llegado por `docker save … | k3s ctr images import -`, que es el paso previo al CI
que documenta el README del producto.

Así que **"el pod corre" no prueba que el clúster sea reproducible desde Git**. Probarlo es el pull
anónimo de arriba. Para forzarlo en un pod ya existente, `imagePullPolicy: Always` en una prueba.

## Contrato de las imágenes propias: multi-arquitectura, una sola etiqueta

**Toda imagen propia se publica multi-arquitectura.** `imac27` es amd64 y `produccion` es arm64, así
que una imagen de una sola arquitectura sólo puede correr en un nodo — y como se construyen en el host
que esté a mano, la que "funciona" suele ser la del host, no la del destino. Medido: las cuatro
imágenes del stack LiteLLM (`headroom`, `vector-store`, `paperclip`, `hermes-gateway`) estaban
**arm64-only** por haberse construido en `frontdoor`, y el nodo destino de los servicios internos es
amd64. **No arrancan ahí**, y el síntoma no dice eso.

**El artefacto es un `image index` con las dos plataformas bajo UNA etiqueta.** El runtime del nodo
baja la capa que le corresponde solo: **no hay etiqueta por arquitectura** y **no hay que tocar los
manifiestos de K8s**. El pin por digest sigue siendo lo correcto y **un digest de manifest list cubre
las dos arquitecturas**.

Plantilla que ya funciona en el repo: `.github/workflows/build-wordpress-familey.yml`
(`docker/setup-qemu-action` + `docker/setup-buildx-action` + `docker/build-push-action` con
`platforms: linux/arm64,linux/amd64`, `GITHUB_TOKEN` con `packages: write`, cache `type=gha`).
Verificado en el registro, no asumido:

```bash
curl -sS -H "Authorization: Bearer $TOK" \
  -H 'Accept: application/vnd.oci.image.index.v1+json' \
  https://ghcr.io/v2/reevolutiva/<paquete>/manifests/<tag> | python3 -m json.tool | head
# mediaType: application/vnd.oci.image.index.v1+json
#  - linux / arm64  sha256:…
#  - linux / amd64  sha256:…
```

- **Kubernetes NO filtra por arquitectura por defecto.** Un pod de una imagen mono-arquitectura
  programado en el nodo equivocado no queda `Pending`: queda en `ImagePullBackOff`/`exec format
  error`, que se lee como problema de permisos. Si una imagen quedara mono-arquitectura, el nodo hay
  que declararlo a mano (`nodeSelector: kubernetes.io/arch: arm64`).
- **Multi-arch resuelve la arquitectura, NO el acceso.** Sin `dockerconfigjson`, el paquete igual
  tiene que ser público. Y un paquete **nuevo** desde un repo privado **nace privado**: la vuelta a
  público es un paso manual (*Package settings → Change visibility*).
- **La visibilidad de un paquete de ORGANIZACIÓN no se puede cambiar por API. Es una limitación de
  GitHub, no un problema de scopes.** `PATCH /orgs/{org}/packages/container/{pkg}` devuelve
  **404 Not Found** aunque el token sea válido y pueda **leer** el mismo paquete con `GET`. Medido el
  2026-09-28 con `giolapietra` (rol `admin` en la org, scope `write:packages` recién agregado por
  `gh auth refresh`): `GET` → `{"visibility":"private","version_count":5}`, `PATCH` → `404`. También
  404 con el `GITHUB_TOKEN` del workflow.
  - **No gastes un `gh auth refresh -s write:packages`** (flujo de dispositivo, del usuario) para
    intentar esto: no lo arregla. Se probó y no cambia nada.
  - **Sólo los paquetes de usuario** (`PATCH /users/{user}/packages/...`) aceptan el cambio por API.
  - **El único camino es la UI:** `https://github.com/orgs/<org>/packages/container/<pkg>/settings`
    → *Danger Zone → Change package visibility → Public*. Es un clic.
  - Que la UI funciona en esta org no se asume: `wordpress-familey` es `owner: reevolutiva` (org),
    del **mismo repo privado**, y es **public** — esa visibilidad se cambió a mano, porque por API no
    se puede. Es el precedente.
  - El paso "Visibilidad del paquete" del workflow **falla siempre** (404) y va con
    `continue-on-error: true` a propósito: no rompe el build, pero **tampoco publica nada**. El primer
    pull anónimo de un paquete nuevo siempre falla hasta el clic — y en el clúster se ve como
    `ImagePullBackOff` con `failed to fetch anonymous token: ... 403 Forbidden`.
  - Verificación de que el clic funcionó (el único test que vale, el mismo camino del clúster):
    token anónimo por `tags/list` → **200**.
- **No construir lo que el upstream ya publica multi-arch.** El proxy de LiteLLM corre la imagen
  oficial `ghcr.io/berriai/litellm`; mantener un build propio que sólo repite el pin de versión y
  regenera Prisma es deuda, no necesidad.
- **La emulación es la parte lenta, y hay un caso que puede no cerrar.** `pip install` bajo QEMU se
  tolera con cache de GHA; **`pnpm build` bajo emulación arm64 no necesariamente**. Si un build no
  cierra por tiempo, la salida es construir la pata arm64 **en `produccion`** (arm64 nativo) y unir
  los manifests con `docker buildx imagetools create`.
- **Pinear la versión del upstream, no "latest"**, y subirla en su propio PR: colar un salto de
  versión dentro de un fix de disponibilidad mezcla dos variables y hace el rollback ambiguo.

## El camino de la imagen del producto (y dónde se corta)

1. `apps/wordpress-producto/**` en `main` → dispara `.github/workflows/build-wordpress-producto.yml`
   (`push` a `main` sobre esos paths).
2. El workflow arma la pila: las piezas libres desde wp.org pineadas por versión + sha256; las
   **licenciadas** desde el bundle `ghcr.io/reevolutiva/wordpress-producto-plugins`, pineado por digest
   contra `plugins.lock`.
3. El bundle **no se arma en CI**: requiere acceso a una copia licenciada, así que se publica a mano
   con `bin/pack-bundle.sh` desde donde esté esa copia, y se pinea por digest en un PR.
4. La imagen sale multi-arquitectura **por necesidad**: `imac27` es amd64 y `produccion` es arm64.

**Dónde se corta hoy:** el bundle no está publicado → el workflow falla en 27 s con
`manifest unknown` al consumirlo → no se publica `wordpress-producto` → el clúster sigue dependiendo del
import a mano. Estado y seguimiento en la carta `t_6fbff1c0` del tablero `reevolutiva-infra`.

**Segundo frente, aparte del bundle:** los manifiestos pinchan por **etiqueta**
(`ghcr.io/reevolutiva/wordpress-producto:0.1.1`). Una etiqueta se puede mover; el pin correcto es
`@sha256:`. Es lo que hay que corregir cuando el CI empiece a publicar.

## Higiene: objetos aplicados a mano

Flux **sólo poda lo que él posee**. Un objeto aplicado con `kubectl` nunca lo fue, así que un `prune`
**no se lo lleva**: queda huérfano, sin dueño que lo reconcilie y sin nadie que lo borre. Ese es el
riesgo real (no el que se suele enunciar), y es el origen de los `idsite` huérfanos de Matomo.

Auditoría de dueño por objeto (las cargas de Helm hay que contarlas como Flux, si no dan falsos
positivos en `monitoring` y `litellm`):

```bash
kubectl -n <ns> get deploy,sts,daemonset,cronjob,pvc,svc,ing,cm -o json | python3 -c '
import json,sys
for i in json.load(sys.stdin)["items"]:
    l=i["metadata"].get("labels") or {}; n=i["metadata"]["name"]
    if n=="kube-root-ca.crt": continue
    k=l.get("kustomize.toolkit.fluxcd.io/name")
    h=l.get("app.kubernetes.io/managed-by") or l.get("helm.sh/chart")
    print(i["kind"], n, ("kustomize:"+k) if k else ("helm:"+str(h)) if h else "NINGUNO <<<")
'
```

Un objeto `NINGUNO` está fuera de GitOps. Si es un arnés de prueba, dale ciclo de vida en Git
(aplicar + limpiar) y documentá que es efímero; si es una configuración de producto, va a Flux.
