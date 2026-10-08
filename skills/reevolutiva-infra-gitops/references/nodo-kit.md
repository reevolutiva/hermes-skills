# El nodo como artefacto (kit de base Flatcar)

Desde PR #84 un nodo es **`kit@version` + su spec**. No hay un `.bu` por nodo.

```
infrastructure/host/flatcar/kit.conf          versiones del SO y los sysext (UN lugar)
infrastructure/host/flatcar/node.bu           plantilla Butane, UNA para todas las arch y roles
infrastructure/host/flatcar/nodes/<nodo>.conf spec: ROLE, ARCH, SYSEXT_ARCH, SUBSTRATE,
                                              DATA_DISK_DEVICE, LONGHORN_PATH, K3S_URL,
                                              NODE_LABELS, NODE_TAINTS
scripts/render-nodo.sh <nodo> --ign <salida>  UNICO camino de render (Makefile + provision de Azure)
scripts/render-bu.py                          sustitucion de marcadores (stdlib, sin PyYAML)
scripts/verificar-kit.sh                      `make kit-verificar`: gate de la base
```

`make nodo-ignition|nodo-plan|nodo-apply|nodo-verificar NODE=<nodo>` no cambiaron de
nombre a proposito. `kit-verificar` es nuevo porque es una cosa nueva.

El sustrato decide solo *quien crea la VM*: Azure (`provision-nodo-produccion.sh`) o
libvirt (pendiente). Adentro de la VM el Ignition es el mismo.

## Trampa 1 — el sufijo del artefacto NO es `uname -m`

Flatcar nombra los sysext con su variable `%a`:

```
amd64 -> x86-64     k3s-v1.36.4+k3s1-x86-64.raw   -> 206
arm64 -> arm64      k3s-v1.36.4+k3s1-arm64.raw    -> 206
-usr.raw y -amd64.raw                             -> 404
```

**Un 404 no rompe el render**: Butane no valida que la URL exista. El nodo arranca
sin sysext, nunca se une al cluster y no hay error que lo explique. Por eso el mapeo
vive en un solo lugar (`render-nodo.sh`) y `make kit-verificar` comprueba la URL de
cada nodo (`curl -r 0-100` → tiene que dar **206**, no 200).

## Trampa 2 — un condicional que no se activa cae EN SILENCIO

La plantilla usa `«?IF:CLAVE» ... «?ENDIF»` (con `@@` de verdad, aca se escriben con
comillas angulares: el verificador de marcadores sobrantes no distingue comentario de
contenido, y un ejemplo literal en la plantilla hace fallar el render).

`render-nodo.sh` **exporta** `AGENT=1` o `SERVER=1` desde `ROLE`. Cuando no los
exportaba, el bloque se eliminaba sin ruido: el `config.yaml` salia con `token:` y
**sin la linea `server:`** — un nodo que arranca, no se une y no dice por que. El
chequeo de "quedaron marcadores sin sustituir" **no lo detecta**, porque el marcador
se consumio bien.

Leccion general: **un bloque condicional que se omite no falla, cambia el artefacto.**
La unica forma de verlo es mirar el resultado.

## Trampa 3 — un bloque multilinea hereda la indentacion del marcador

En un `inline: |`, la indentacion la aporta el marcador. Si el valor del bloque trae
su propia indentacion base, sale **sumada**: `node-label:` terminaba con 10 espacios
de mas dentro del archivo del nodo. `render-bu.py` copia la indentacion del marcador a
todas las lineas del valor, y el valor se arma **sin** indentacion base.

## Como se prueba que un refactor de provision no rompe nada

Refactorizar el camino que provisiona el **unico nodo que funciona** es de alto
riesgo. La prueba no es una opinion: se renderiza el Ignition por los dos caminos y se
compara **descomprimiendo los blobs inline** (Butane los guarda como
`gzip` + `data:;base64,…` en `storage.files[].contents.source`), porque un `diff` del
JSON crudo solo muestra base64 distinto.

```python
# por archivo: re.match(r"data:;base64,(.*)$", source, re.S) -> gzip.decompress
# la estructura (todo menos los inline) se compara con el JSON sin los blobs
```

Medido en el PR #84: estructura identica; 14 lineas de diferencia, todas texto de
mensajes/comentarios. **El diff destapo dos bugs propios** (trampas 2 y 3) que ningun
`kubectl get` habria mostrado.

Ojo: los comentarios YAML del `.bu` **no** llegan al `.ign`, pero el contenido de
`contents: inline:` y de `systemd.units[].contents` **si**. Un cambio de redaccion
dentro de un script inline es un cambio del artefacto.

## El gate hay que probarlo en negativo

`make kit-verificar` se probo rompiendo a proposito: version de sysext inexistente
(`v9.99.9+k3s9` → 2 fallas, exit 1) y `SYSEXT_ARCH=amd64` (→ "validos: arm64,
x86-64", exit 1). Un gate que nunca fallo no es un gate.

## `make lint` y PyYAML

`scripts/lint-yaml.py` necesita PyYAML y el `python3` del PATH de `imac27` **no lo
tiene** (esta en `/usr/bin/python3`). La receta lo tenia fijo: fallaba **siempre**, con
exit 1 en un arbol limpio — un gate que no puede correr y no verifica nada. El Makefile
ahora elige el primer interprete que tenga PyYAML (`PYTHON_LINT`) y, si ninguno lo
tiene, lo dice con esas palabras.

## Presupuesto de virtualizacion de `imac27` (medido)

| Dato | Valor |
|---|---|
| CPU | Intel i9-10910, 20 hilos, `vmx`, `kvm_intel nested=Y` |
| KVM | `/dev/kvm` presente |
| RAM | 31 GB (14 en uso: agentes Docker + K3s + cargas) — **el recurso escaso** |
| Disco | un NVMe: `nvme0n1p3` = PV de **6,76 TB**, 4 LV (workspace 4T, backup 1T, ollama 1T, databases 500G), **279 GB libres** en el VG |
| Falta | `qemu-system-x86_64`, `virt-install`, `virsh` |

El iMac es hierro directo: **no hace falta virtualizacion anidada**. El riesgo 7 de
#26 queda cerrado; el limite real es la RAM compartida con el Docker de agentes.

## QEMU/libvirt: como se le pasa el Ignition (para F2)

```bash
virt-install --import … --qemu-commandline='-fw_cfg name=opt/org.flatcar-linux/config,file=provision.ign'
```

- El nombre de la entrada es `opt/org.flatcar-linux/config` (los docs viejos decian
  `opt/com.coreos/config`; con ese nombre QEMU lo ignora y **Ignition nunca corre**).
- En **q35/OVMF, ACPI tiene que estar activo**: si no, QEMU rechaza el `fw_cfg`.
- Con `--import` + disco CoW, **re-ejecutar el provision no re-corre Ignition**
  (`firstboot=false`): para re-aplicarlo hay que recrear el disco CoW. Es la misma
  doctrina de "recrear y no converger" que ya usa `produccion`.

## Estado del cluster dentro de un working tree ajeno (mina)

`--data-dir=/data/workspace/k3s` (19 GB, con el `state.db` de SQLite) y Longhorn en
`/data/workspace/longhorn` (8,7 GB) viven **untracked y sin ignorar** dentro del
checkout de **otro** repo (`rdp-kelenfold`) que ademas tiene cambios sin commitear. Un
`git clean -xdf` ahi **borra el estado del cluster**. Contrato 3 del RFC
(`docs/host-inmutability-rfc.md`): los dos tienen que salir a un LV propio.

## `verificar-nodo.sh` esta acoplado al sustrato

Los chequeos 3/6 y la medicion de trafico de `scripts/verificar-nodo.sh` salen por
`az vm run-command`: en un nodo libvirt no hay `az`. El criterio 4 de #27 ("debe
funcionar sin cambios en el nodo nuevo") **no se puede cumplir hoy**. La resolucion es
reemplazar `az` por `tailscale ssh` —que ya usa el 5/6— y asi un solo salto prueba el
acceso del tailnet **y** el interior del nodo.
