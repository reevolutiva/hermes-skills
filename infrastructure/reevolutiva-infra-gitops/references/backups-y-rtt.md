# Respaldos del clúster y la física que los hace lentos

Todo vive en `infrastructure/backups/` (namespace `backups`, Kustomization `infra-backups`):
dumps diarios de PostgreSQL (03:00 UTC) y MariaDB (03:30) a PVC, copia fuera del clúster a
Azure Blob (`backup-offsite` 05:00, rclone), prueba semanal de restore (domingos 05:00/05:30) y
`RecurringJob/sites-backup-daily` (04:00) para los volúmenes de los sitios. La prosa completa y
los números medidos están en `infrastructure/backups/README.md` del repo.

## Cómo se verifica (que el CronJob exista no prueba nada)

```bash
make backup-probar          # dispara los dos restore-check y espera: PASS/PASS en ~220 s
make backup-offsite-probar  # sube al Blob y compara conteos origen/destino
```

Y para un dump puntual, disparar el Job a mano y cronometrarlo (el patrón sirve para cualquier
CronJob del clúster):

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
j="prueba-$(date +%s)"; start=$(date +%s)
kubectl -n backups create job --from=cronjob/backup-mariadb "$j" >/dev/null
for i in $(seq 1 60); do
  [ "$(kubectl -n backups get job "$j" -o jsonpath='{.status.succeeded}' 2>/dev/null)" = 1 ] && break
  sleep 5
done
echo "$(( $(date +%s) - start ))s  nodo=$(kubectl -n backups get pods -l job-name=$j -o jsonpath='{.items[0].spec.nodeName}')"
kubectl -n backups logs "job/$j" --tail=8
kubectl -n backups delete job "$j"      # limpiar: los jobs de prueba se acumulan
```

## El hallazgo: el RTT entre nodos manda, no el ancho de banda

Medido el 2026-09-26 entre `imac27` (casa) y `produccion` (Azure westus3):

| Qué | Valor |
|---|---|
| RTT (`tailscale ping`) | **~140 ms** — y la conexión es **directa**, no relay |
| Ancho de banda (`ssh`+`dd`, 50 MB) | **7,4–7,9 MB/s** un stream; 10 MB/s con cuatro |
| Dump MariaDB de 9,1 MB cruzando nodos | **~300 s** (~30 KB/s) |
| El mismo dump **dentro** del pod de la base | **< 1 s** |
| El mismo dump con el Job co-locado (`podAffinity`) | **41 s** |

No es un problema de Tailscale ni de configuración: es geografía. Lo que se derrumba son los
protocolos con **muchas idas y vueltas**: a ~4 KB por vuelta, 9 MB son ~2.300 vueltas. Una
consulta trivial (conexión + `select 1`) cuesta **0,54 s** desde el nodo de la base y **1,18 s**
desde el otro.

**Regla operativa: acercar el trabajo al dato.** Todo Job que lea o escriba datos de una carga
va co-locado con ella. Y ojo: **Longhorn con 2 réplicas paga este RTT en CADA escritura** (la
segunda réplica vive en el otro nodo), así que ni co-locando el pod se arregla el I/O de una base
— hay que sacar el volumen del camino (disco local) o aceptar el costo.

## Trampas verificadas

- **`podAffinity` necesita `namespaces` explícito.** La afinidad entre pods mira sólo pods del
  **mismo namespace** por defecto. El Job vive en `backups` y la base en `wordpress`: sin
  `namespaces: [wordpress]` el scheduler no encuentra ningún nodo y el Job queda `Pending` para
  siempre (`0/2 nodes are available: 2 node(s) didn't match pod affinity rules`).
  **`kubectl apply --dry-run=server` acepta las dos formas**: el error lo atrapa el scheduler, o
  sea que sólo se ve corriendo el Job. Es la misma clase de trampa que "un manifiesto válido no
  es un manifiesto que funcione".
- **`MYSQL_PWD` / `PGPASSWORD` en el entorno se filtran a CUALQUIER servidor** al que se conecte
  el cliente. Si un script usa la credencial para el origen y además levanta un servidor local
  descartable (sin contraseña), todo lo local falla con
  `Access denied for user 'root'@'localhost' (using password: YES)`. Guardarla en una variable
  (`ORIGEN_PWD="$MYSQL_PWD"`) y hacer `unset MYSQL_PWD` para el resto.
- **El `RecurringJob` de Longhorn tiene `groups: []`:** sólo respalda los volúmenes con la
  etiqueta puesta a mano. Un PVC sin etiquetas queda en el grupo `default`, que **ningún**
  RecurringJob declara → no lo respalda nadie. Para que un volumen entre hacen falta **las dos**
  etiquetas en el **PVC** (no en el `Volume`):

  ```yaml
  labels:
    recurring-job.longhorn.io/source: enabled                 # marca que el PVC manda
    recurring-job.longhorn.io/sites-backup-daily: enabled
  ```

  `source: enabled` es el marcador de que el PVC es la fuente de verdad de las etiquetas del
  volumen; **no se espeja al `Volume`** (verificado: el PVC lleva las dos, el `Volume` sólo la del
  job). El objeto `Volume` es dinámico (`pvc-<uid>`) y no se puede declarar en Git: el PVC es el
  único lugar donde esto puede vivir. Verificar con
  `kubectl -n flux-system get volumes.longhorn.io <pvc-uid> -o jsonpath='{.metadata.labels}'` y el
  log del manager (`Adding Volume ... recurring job label ...`).
- **Una prueba de restore que restaura DENTRO del servidor de producción es lenta y peligrosa.**
  La primera versión creaba una base descartable en el servidor real: ~10 minutos para 139 tablas
  (cada escritura esperaba la confirmación de la réplica de Longhorn, a 140 ms de RTT) y escribía
  en producción. Lo correcto es que la prueba levante **su propio servidor** en un `emptyDir`
  (disco local del nodo) y del origen haga sólo **una consulta de lectura** para comparar el
  conteo de tablas. Queda más estricto, no menos: un dump que sólo restaura donde ya están las
  tablas no prueba gran cosa. Medido después del cambio: **72 s** PostgreSQL, **133 s** MariaDB.
- **Antes de "optimizar", medir; y si la medición contradice la hipótesis, revertir.** Dumpear a
  disco local y copiar al PVC (hipótesis: la escritura chica al volumen replicado) dio **299 s
  contra 309 s** del original: no servía. Se revirtió en vez de conservar complejidad sin
  beneficio medido, y se buscó la causa real (el RTT). Dos mediciones invalidan cualquier
  diagnóstico: la primera puede estar midiendo otra cosa (p. ej. una spec que Flux todavía no
  reconcilió).
- **Un Job de prueba que no termina deja el pod colgado.** Si el `create job --from=cronjob`
  queda `Pending` (afinidad imposible, taint sin tolerar, recursos), el bucle de espera agota su
  tope y parece que "tardó 300 s" cuando en realidad no corrió nunca. Mirar **siempre** el nodo y
  la fase del pod antes de creer un número.
