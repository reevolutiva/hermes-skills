# Imágenes propias: publicación multi-arch y jerarquía de registros

## Jerarquía de registros (vigente)

1. **Registry interno** (`registry.coyote-paridae.ts.net`) — fuente primaria. Los deployments de
   producción jalan de acá. Acepta push anónimo dentro del tailnet. Ver ADR 0010.
2. **ACR** (`reevolutivacr.azurecr.io`) — respaldo si el registry interno falla. Los secretos
   `acr-pull` ya existen en los namespaces `reevolutiva` y `wordpress`. Si el registry interno
   cae, los deployments deben re-apuntar a ACR y usar `imagePullSecrets: acr-pull`.
3. **GHCR** — **NO usar**. Deprecado como destino de publicación. Los workflows no publican a GHCR.

## Publicar una imagen (build directo al registry interno)

```bash
# vm-services. Requiere QEMU para emular arm64:
#   sudo apt-get install -y qemu-user-static binfmt-support
docker buildx build --platform linux/amd64,linux/arm64 --provenance=false \
  -t registry.coyote-paridae.ts.net/<app>:<tag> --push <build-context>
```

El registry interno acepta push **anónimo** dentro del tailnet: no hay credencial que manejar.
Verificar el manifest list antes de desplegar:

```bash
curl -s -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json' \
  http://registry.coyote-paridae.ts.net:5000/v2/<app>/manifests/<tag> | grep -A2 architecture
```

Respaldo en ACR (si el registry interno no está disponible):

```bash
docker buildx build --platform linux/amd64,linux/arm64 --provenance=false \
  -t reevolutivacr.azurecr.io/<app>:<tag> --push <build-context>
```

La credencial de ACR vive en AKV (`reevolutivacr`), y el secret `acr-pull` está materializado
en los namespaces relevantes.

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

Plantilla de workflow (sin GHCR): `setup-qemu` + `setup-buildx` + `build-push` con
`platforms: linux/arm64,linux/amd64`, `provenance: false`, cache `type=gha`, y push directo
al registry interno. Verificado en el registro, no asumido.

- **Kubernetes NO filtra por arquitectura por defecto.** Un pod de una imagen mono-arquitectura
  programado en el nodo equivocado no queda `Pending`: queda en `ImagePullBackOff`/`exec format
  error`, que se lee como problema de permisos. Si una imagen quedara mono-arquitectura, el nodo hay
  que declararlo a mano (`nodeSelector: kubernetes.io/arch: arm64`).
- **Multi-arch resuelve la arquitectura, NO el acceso.** Sin credencial, el paquete tiene que ser
  público. El registry interno no exige credencial dentro del tailnet.
- **No construir lo que el upstream ya publica multi-arch.** El proxy de LiteLLM corre la imagen
  oficial `ghcr.io/berriai/litellm`; mantener un build propio que sólo repite el pin de versión y
  regenera Prisma es deuda, no necesidad.
- **La emulación es la parte lenta, y hay un caso que puede no cerrar.** `pip install` bajo QEMU se
  tolera con cache de GHA; **`pnpm build` bajo emulación arm64 no necesariamente**. Si un build no
  cierra por tiempo, la salida es construir la pata arm64 **en `produccion`** (arm64 nativo) y unir
  los manifests con `docker buildx imagetools create`.
- **Pinear la versión del upstream, no "latest"**, y subirla en su propio PR: colar un salto de
  versión dentro de un fix de disponibilidad mezcla dos variables y hace el rollback ambiguo.

## La trampa que hace creer que todo está en Git

`imagePullPolicy: IfNotPresent` (lo que usan todos los manifiestos) **oculta** el problema: si la imagen
ya está en el containerd del nodo, el pod levanta aunque el registro no la tenga. Y la imagen suele
haber llegado por `docker save … | k3s ctr images import -`, que es el paso previo al CI que
documenta el README del producto.

Así que **"el pod corre" no prueba que el clúster sea reproducible desde Git**. Probarlo es el pull
real desde el nodo destino con `imagePullPolicy: Always` en una prueba.

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
