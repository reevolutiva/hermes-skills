# Arquitecturas: host e imagen (pre-flight de migración)

Un desajuste de arquitectura **no falla con un error claro**: la imagen no arranca, o
arranca y el proceso muere, y el síntoma aparece lejos de la causa. Chequearlo antes de
mover datos.

## 1. Arquitectura de los hosts

```bash
uname -m                                   # aarch64 = arm64 | x86_64 = amd64
docker info --format '{{.Architecture}}'   # lo que ve el runtime de contenedores
```

Por host, y no por suposición: los mismos "servidores legacy" pueden ser de
arquitecturas distintas entre sí (uno Ampere/arm64 y otro x86), y eso decide dónde
puede correr cada carga.

## 2. Arquitectura de una imagen pública (registry API)

No alcanza con mirar el tag en la web. Dos casos posibles:

```bash
REPO=demyx/openlitespeed            # o library/mariadb para imágenes oficiales
TOKEN=$(curl -sS "https://auth.docker.io/token?service=registry.docker.io&scope=repository:$REPO:pull" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

# ¿es multi-arch o de una sola arquitectura?
curl -sS -H "Authorization: Bearer $TOKEN" \
  -H 'Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json' \
  "https://registry-1.docker.io/v2/$REPO/manifests/<tag>" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin);\nms=d.get("manifests");\nprint("MULTI-ARCH:", sorted({(m.get("platform") or {}).get("architecture") for m in ms}) if ms else "NO — manifiesto simple (una sola arquitectura)")'
```

Si la respuesta es un **manifiesto simple** (no una lista), hay que leer la config para
saber cuál es:

```bash
CFG=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
  "https://registry-1.docker.io/v2/$REPO/manifests/<tag>" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["config"]["digest"])')
curl -sS -L -H "Authorization: Bearer $TOKEN" \
  "https://registry-1.docker.io/v2/$REPO/blobs/$CFG" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("architecture"), d.get("os"))'
```

### 2b. GHCR — el registry de la casa (`ghcr.io/<org>/<pkg>`)

GHCR **no** usa el endpoint de token de Docker Hub. El intercambio correcto es
`https://ghcr.io/token?scope=repository:<org>/<pkg>:pull&service=ghcr.io`. Con el token
de Docker Hub la respuesta **no** es un error limpio: llega vacía y el parseo concluye
"no es multi-arch", que es exactamente lo contrario de la verdad.

```bash
PKG=<org>/<pkg>                     # SIN el prefijo ghcr.io
TOK=$(curl -sS "https://ghcr.io/token?scope=repository:$PKG:pull&service=ghcr.io" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -sS -H "Authorization: Bearer $TOK" \
  -H 'Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json' \
  "https://ghcr.io/v2/$PKG/manifests/<tag>" \
  | python3 -c 'import json,sys; ms=(json.load(sys.stdin).get("manifests") or []); print(sorted({(m.get("platform") or {}).get("architecture") for m in ms}) or "SIMPLE (una sola arquitectura)")'
```

Un paquete privado de la organización devuelve `401`/`403`, pero **ese 403 no prueba que
sea privado**: un curl anónimo tampoco distingue público de inexistente. La prueba que
vale es el kubelet (ver `references/ghcr-registry.md`).

### 2c. Chequear el stack COMPLETO, no la imagen principal

Cuando la pregunta es "¿este componente candidato puede correr en el nodo arm64?", la
imagen que decide no suele ser la principal: un sidecar amd64-only (motor de búsqueda,
exportador, UI) tumba el despliegue igual. Armar la lista con
`grep -E 'image:' <compose>` y pasar **cada** imagen por el mismo chequeo. Un stack
candidato puede tener 9 servicios donde uno solo parece la aplicación.

**Revisar TODOS los tags relevantes, no solo `latest`:** una imagen puede ser amd64 en
todas sus variantes (visto: `latest`, `v1`, `v1-bedrock`, `bedrock`, `1.11.0*`, `dev*` →
todas `amd64`). Si es así, no hay tag que salve el desajuste.

## 3. Arquitectura de una imagen local del host

```bash
docker image inspect <imagen:tag> --format '{{.Architecture}}/{{.Os}}'
```

Y de dónde sale: `grep -nE 'image:|build:|context:' <compose>` distingue las que se
**construyen** en el host de las que se **descargan**.

## 4. Qué hacer cuando no coinciden

En orden de preferencia:

1. **Reconstruir desde un Dockerfile portable.** Una imagen que sale de
   `FROM php:8.3-apache` (multi-arch) se reconstruye para cualquier arquitectura. Es la
   salida limpia — y de paso deja la imagen declarada en el repo, que suele faltar.
2. **Buscar una base oficial multi-arch.** Antes de dar una imagen por imposible,
   verificar la **oficial** del mismo stack: puede ser multi-arch aunque la de terceros
   que se usaba no lo sea. Construir sobre esa base preserva las extensiones del stack
   (p. ej. el plugin de caché a nivel de servidor).
3. **Programar la carga en un nodo de su arquitectura**, si el clúster tiene de las dos.
4. **Cambiar la arquitectura del nodo destino.** Es el último recurso y hay que
   enumerarlo completo, no improvisarlo: tamaño de VM, **oferta de imagen** del
   marketplace, y **todos** los artefactos específicos de arquitectura (binarios,
   sysext, links, guardas de arquitectura en los scripts).

## 5. Regla de higiene

Una imagen construida en un host y nunca publicada **no es reproducible**: si el host se
apaga, se pierde. Antes de planear el corte, preservar los contextos de build
(Dockerfile + configs, **sin** `.env`) en el repo, y publicarlas en un registry o
transferirlas al destino.
