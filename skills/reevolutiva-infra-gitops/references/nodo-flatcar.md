# Nodo Flatcar (producción) — detalle

Profundidad del tema: rutas reales de los sysext, el bucle de Tailscale con su
evidencia, Tailscale SSH y el ACL del tailnet, y las trampas del primer
provisionamiento. El resumen siempre-válido vive en `SKILL.md`.

El nodo de producción es **Flatcar + Ignition + K3s**, provisionado con
`scripts/provision-nodo-produccion.sh` desde `infrastructure/host/flatcar/produccion.bu`.
Diseño completo en el issue #3; datos medidos en el README de esa carpeta.

- **Verificar la arquitectura primero.** `FLATCAR_BOARD` en `/etc/os-release`. Los
  `E*v6` de Azure son **arm64** (Ampere): un sysext o binario de x86-64 arranca igual
  y el nodo **nunca** se une al clúster, sin error visible.
- **K3s y Tailscale van como sysext**, no con `curl | sh`. URLs verificables:
  `https://extensions.flatcar.org/extensions/k3s/k3s-<v>+k3s1-<arch>.raw` y
  `.../extensions/tailscale/tailscale-<v>-<arch>.raw`, más los `.conf` de sysupdate.
  Comprobar con `curl -r 0-100 -w '%{http_code}'`: tiene que dar **206**.
  El sysext de K3s debe ser **la misma versión que el server** (`kubectl version`).
- **Butane `variant: flatcar` acepta hasta `1.1.0`.** Con `1.4.0` (la numeración del
  spec de Ignition) falla con *"No translator exists for variant flatcar"*.
- **Longhorn en Flatcar no necesita el DaemonSet de prerrequisitos**: ese usa
  `apt`/`yum`. Flatcar **ya trae** `iscsiadm`/`iscsid`; solo hay que cargar
  `iscsi_tcp` (`/usr/bin/modprobe`) y habilitar `iscsid.service`.
- **La IP del tailnet no existe en el primer arranque.** Si el agente K3s se anuncia
  con la IP privada del proveedor, el server no puede rutearle aunque el nodo esté
  `Ready`. Hay que resolver `tailscale0` y escribir `node-ip` +
  `flannel-iface: tailscale0` en `/etc/rancher/k3s/config.yaml.d/` **antes** del
  agente. Verificación: `kubectl get nodes -o wide` → la IP interna debe ser `100.x`.
- **Ignition corre una sola vez.** Alternativa a recrear la VM: `flatcar-reset`
  (está en la imagen) permite re-ejecutarlo conservando datos.
- **La preauth key de Tailscale: de un solo uso** (`reusable: false` vía API de
  Tailscale con el OAuth client de AKV). Así la custom-data deja de ser un secreto
  vivo después del primer arranque. El `.ign` renderizado nunca se commitea.

### Trampas verificadas en el primer provisionamiento

- **La versión de la imagen de Azure NO es la versión del SO que va a correr.**
  Flatcar se auto-actualiza (update-engine) y **reinicia solo**: el nodo arrancó en
  `4593.2.5` —lo máximo publicado para arm64— y a los ~18 min reinició a `4757.2.0`.
  No diagnosticar "versión rara" sin mirar `journalctl --list-boots`.
- **Validar el URN de la imagen ANTES de cualquier paso destructivo.**
  `az vm image show --urn <urn>` en las precondiciones. El catálogo arm64 está en
  `kinvolk:flatcar-container-linux-corevm:stable` (el x64 usa la oferta `-amd64`
  con sku `stable-gen2`).
- **El CLI de Azure lee `--custom-data` como latin-1.** Un carácter fuera de ese
  rango (em dash, flecha, comillas curvas) en un **script inline** hace fallar
  `az vm create` con `'latin-1' codec can't encode character`. Los comentarios YAML
  del `.bu` no llegan al JSON y son seguros; el contenido `inline:` y los `contents:`
  de las unidades sí. `render-ignition.sh` lo rechaza antes de renderizar.
- **Rutas de los sysext: no son las mismas.** Tailscale instala en `/usr/bin` y su
  unidad en `/usr/lib/systemd/system`; K3s instala en `/usr/local/bin` y sus unidades
  en `/usr/local/lib/systemd/system`. Asumirlo deja el nodo sin tailnet → sin ruta al
  API server. Usar `command -v`, no rutas fijas.
- **`Wants=` no alcanza para ordenar el arranque del agente K3s.** Si el servicio que
  resuelve la IP del tailnet falla, con `Wants=` el agente arranca igual y se anuncia
  con la IP privada del proveedor, a la que el server no puede rutear, **sin que nada
  lo grite**. Usar `Requires=`.
- **Bucle de Tailscale sobre K3s (el que deja el nodo `NotReady`).** Con flannel
  `wireguard-native` sobre el tailnet, `tailscaled` puede tomar una dirección del
  pod-network (`10.42.0.0`) como endpoint de un peer; sus sondas del puerto `41641`
  se rutean por el túnel de pods, no vuelven nunca, y reintenta a ~135k paquetes/s
  con tamaños crecientes. Medido: 80 MB/s, `tailscaled` al 188% de CPU, API server
  inalcanzable. Guarda:
  `iptables -I OUTPUT 1 -o flannel-wg -p udp --sport 41641 -j DROP`
  (el puerto propio de Tailscale hacia el túnel de pods nunca es legítimo).
- **El bucle es INTERMITENTE: una ventana tranquila no prueba nada.** Una regla mal
  elegida dio 48 KiB/15 s y parecía resuelta; minutos después volvía a 1,19 GiB/15 s.
  Verificar con **6 muestras de 10 s**, nunca con una sola.
- **`tcpdump` SÍ viene en Flatcar** (`/usr/bin/tcpdump`): es la vía para ver qué
  tráfico real circula, en vez de deducirlo. En `flannel-wg` se ve el paquete
  interno; en `tailscale0`, el encapsulado. Para atribuir volumen por dirección,
  reglas de conteo neutras (ACCEPT tempranos equivalentes a los de flannel) + leer
  sus contadores.
- **Tailscale SSH: el flag del dispositivo NO alcanza, y `tailscale set --ssh` tampoco.**
  `--ssh` en el `tailscale up` (o `tailscale set --ssh`) deja `RunSSH: True`, pero con
  eso puesto la conexión igual falla con *"tailnet policy does not permit you to SSH to
  this node"*. La causa es el ACL: la regla `ssh` por defecto usa
  `"dst": ["autogroup:self"]` = **"dispositivos que el usuario POSEE"**, y un
  dispositivo **etiquetado** no lo posee ningún usuario (y si su tag está declarado sin
  dueño —`"tag:server": []`— menos todavía). El síntoma previo es la salud del tailnet:
  `tailscale status --json` → `.Health`: *"Tailscale SSH enabled, but access controls
  don't allow anyone to access this device"*.
  Arreglo (en el ACL, no en el repo): agregar una regla con `"dst": ["tag:server"]`.
  Con `action: "accept"` no pide re-auth en el navegador; `"check"` sí.
- **El ACL se puede leer y escribir por API, sin consola.** El OAuth client de AKV tiene
  scope `all`: `GET`/`POST https://api.tailscale.com/api/v2/tailnet/-/acl`. El ACL es
  **HuJSON** (comentarios y comas finales): leerlo, insertar la regla sobre el texto
  original y reenviarlo tal cual — si se reescribe como JSON limpio se pierden los
  comentarios del usuario. La API valida antes de aplicar: un policy inválido se
  rechaza y no rompe nada.
- **Un "pendiente" que se puede resolver no se deja como pendiente.** El ACL de SSH
  quedó primero documentado como "no se arregla desde el repo" y era media verdad: no
  se arregla desde el repo, pero sí desde la API. Antes de declarar algo bloqueado,
  probar si hay camino programático.
