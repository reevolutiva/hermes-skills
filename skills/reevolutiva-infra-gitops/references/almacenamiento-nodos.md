# Almacenamiento y capacidad de los nodos (K3s)

Cómo diagnosticar un nodo cuyo filesystem raíz se llena, cómo ampliar la capacidad de una VM, y
por qué el disco de Longhorn es casi siempre la causa.

## El modelo de discos (tres capas que se confunden)

1. **Filesystem raíz de la VM** (`/dev/vda1`, ~29 G): todo lo que no tenga un montaje propio vive
   aquí — imágenes y capas de contenedores, caches de toolchains, logs, el disco de datos de
   Longhorn si apunta a una ruta local, y los homes de los agentes.
2. **Share virtiofs del host.** En `vm-services` **solo** `/data/workspace/projects` es un
   `<filesystem type='mount'>` de `imac27`. Un `du` sobre `/data/workspace` **sin `-x`** atraviesa
   ese montaje y reporta decenas de GB que no están en la VM: medir con `du -x -sh <ruta>` y
   confirmar el montaje con `findmnt -T <ruta>`.
3. **Disco de datos propio** (`/dev/vdb`, un LV del array del host): el lugar correcto para
   Longhorn, docker y los homes que crecen.

**Regla:** antes de hablar de capacidad, `findmnt -T` de cada ruta involucrada y `lsblk` del nodo.
La misma ruta existe en el host y en la VM con contenidos distintos; el nombre no dice cuál es.

## El disco de Longhorn en el fs raíz es la causa del DiskPressure

`defaultDataPath` del HelmRelease de Longhorn apunta a `/data/workspace/longhorn`, y dentro de la VM
esa ruta **es el filesystem raíz**. Consecuencias observadas:

- El nodo reporta como "disco de almacenamiento" el mismo disco donde viven el SO y las imágenes
  (un nodo de 28 G con 8 G disponibles no es un nodo de almacenamiento), y su raíz entra en
  `disk-pressure`: kubelet pone el taint y evicta primero los pods sin `ephemeral-storage`.
- `defaultDataPath` **solo afecta discos nuevos**. Los CRs `nodes.longhorn.io` los crea Longhorn en
  runtime y **no están en Git**: cambiar el valor y mergear no mueve nada de lo existente.

**Migrar el disco de un nodo:**

1. Inventariar y guardar el rollback: `kubectl get nodes.longhorn.io <nodo> -n flux-system -o json
   | jq '.spec.disks'`.
2. Declarar en Git el CR de nodo con **dos discos**: el nuevo (`allowScheduling: true`) y el viejo
   (`allowScheduling: false`). El viejo no se quita hasta que las réplicas estén reconstruidas.
3. Esperar la reprogramación (`kubectl -n flux-system get replicas.longhorn.io -o wide`) y que
   `status.diskStatus` del disco nuevo reporte `storageAvailable` en GB.
4. Recién entonces retirar el disco viejo de `spec.disks`.

No se "migran" los datos de un disco de nodo: se reconstruyen réplicas. Por eso el disco viejo se
mantiene agendable hasta que el nuevo esté sano.

## Ampliar la capacidad de una VM

El array del host tiene LVs libres (el VG que alimenta los discos de las VMs): se crea un LV nuevo y
se adjunta a la VM como disco de datos. Hot-plug con el dominio encendido y, dentro de la VM:

**En el host, `virsh` sin `sudo` consulta `qemu:///session` y devuelve una lista vacía** — parece que
no hay VMs y el dominio real (`qemu:///system`) queda invisible. Usar `sudo virsh list --all` (o
`virsh -c qemu:///system`). Descubrir antes de crear nada: `sudo virsh domblklist <vm>`, `vgs`, y
`lvs -o lv_name,vg_name,lv_size`. El nombre del dominio libvirt es el del nodo.

```bash
lsblk                                    # confirmar /dev/vdb
sudo mkfs.ext4 -L <label> -m 1 /dev/vdb  # el formateo lo ejecuta un humano
echo 'LABEL=<label> /data/local ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab
sudo mount -a && df -h /data/local
```

- **`mkfs` es comando bloqueado para el agente** (lista negra dura, no se puede ni con
  aprobaciones). Se entrega el comando exacto al humano y se verifica después con `findmnt`/`df`.
- `nofail` en la entrada de `fstab`: un volumen que no monta no debe impedir el arranque de la VM.
- `mount -a` avisa `fstab has been modified, but systemd still uses the old version`: es cosmético
  para el montaje actual, pero los **bind mounts** que dependan del volumen sí necesitan
  `systemctl daemon-reload`.

## Mover un directorio del home al volumen nuevo

```bash
# con los servicios que lo usan parados: systemctl --user stop <svc>...
sudo mkdir -p /data/local/home/<D> && sudo chown "$USER:$USER" /data/local/home/<D>
rsync -aHAX ~/.<app>/<D>/ /data/local/home/<D>/
mv ~/.<app>/<D> ~/.<app>/<D>.old && mkdir ~/.<app>/<D>
sudo mount --bind /data/local/home/<D> ~/.<app>/<D>
echo "/data/local/home/<D> $HOME/.<app>/<D> none bind,nofail,x-systemd.requires-mounts-for=/data/local 0 0" | sudo tee -a /etc/fstab
rm -rf ~/.<app>/<D>.old      # solo después de verificar el bind
```

`x-systemd.requires-mounts-for=/data/local` es lo que evita que el bind se monte antes que el
volumen y quede un directorio vacío encima. Verificar con `df -h <dir>`: tiene que mostrar el
dispositivo del volumen, no el raíz. Un directorio **sin nada usándolo en caliente** se puede mover
sin ventana; los que sostienen servicios vivos exigen pararlos.

## Triaje de "el raíz se está llenando"

```bash
df -h / ; df -h /data/local
sudo du -x -sh /home/* /var/lib/docker /var/lib/rancher 2>/dev/null | sort -h | tail
```

Sospechosos por tamaño en estas VMs: cachés de npm (`~/.npm/_cacache`, GBs), imágenes y capas de
docker (`docker image prune -a`), cachés de Hermes/Paperclip (`~/.hermes/{tools,installs,cache}`,
`~/.paperclip/cli/installs`) y un **home de usuario sin procesos** (`/home/paperclip` acumula GBs
mientras el servicio corre como otro usuario).

Si el raíz crece **mientras** trabajas, mira si Longhorn acaba de arrancar en el nodo (manager y
engine recién creados) antes de buscar la causa en tus propios pasos.

## Gate de cierre

```bash
kubectl get nodes -o custom-columns='N:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,DISK:.status.conditions[?(@.type=="DiskPressure")].status'
# esperado: ningun nodo con DiskPressure=True
kubectl get nodes.longhorn.io -n flux-system -o json | jq -r '.items[] | .metadata.name as $n | .spec.disks | to_entries[] | "\($n) \(.value.path) sched=\(.value.allowScheduling)"'
# esperado: ningun path de Longhorn dentro del filesystem raiz de una VM
```

Los cambios de capacidad en una VM se verifican **dentro** de la VM (`df`, `findmnt`); los de
Longhorn, en el CR del nodo y en el estado de las réplicas. Un `Ready` del nodo no prueba que su
disco de datos sea el correcto.
