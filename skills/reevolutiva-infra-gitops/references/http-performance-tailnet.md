# Diagnóstico de rendimiento HTTP y UI sobre tailnet

Usar para interfaces SPA o servicios HTTP expuestos por Tailscale cuando el usuario reporta refresh/navegación lenta. El objetivo es localizar la capa —cliente, ruta tailnet/Ingress, servidor estático, API, dependencia o pod— con medidas comparables antes de cambiar configuración.

## Procedimiento

1. **Define el síntoma exacto.** Aclara si es recarga completa del navegador, navegación dentro de la SPA o botón de refresco de datos; registra URL, hora, origen del cliente y si es una carga fría, recarga normal o bypass de caché. No supongas que la máquina desde la que corre el diagnóstico comparte la ruta del navegador del usuario.

2. **Confirma el destino live.** Verifica kubecontext/API, Ingress, Service, endpoints, pod/nodo y readiness. Captura logs con una ventana que cubra la reproducción; resume timestamps, paths, códigos y duraciones, no vuelques líneas crudas que puedan contener tokens, prompts o cabeceras. Un log de acceso sin duración no descarta una respuesta lenta.

3. **Mide el endpoint externo varias veces.** Usa la URL real y registra DNS, connect, TLS, TTFB, total y código HTTP; separa TTFB del tiempo de descarga. Por ejemplo:

   ```bash
   for i in 1 2 3; do
     curl -sS -o /dev/null --connect-timeout 10 --max-time 100 \
       -w 'http=%{http_code} dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total} bytes=%{size_download} speed_Bps=%{speed_download}\n' \
       "$URL"
   done
   ```

4. **No confundas HTML con la carga de una SPA.** Obtén del HTML las referencias JS/CSS, localiza uno o más bundles grandes y mide su descarga completa desde el mismo cliente. Anota bytes, `Content-Encoding`, `Cache-Control`, `ETag` y tiempo; si el tiempo crece aproximadamente con los bytes, el cuello está en transferencia y no en TTFB. Compara HTTP/1.1 y HTTP/2 solo si sospechas un comportamiento de protocolo. No lances decenas de descargas concurrentes como primera prueba: eso puede crear la congestión que intentas diagnosticar.

5. **Compara el mismo recurso dentro del clúster.** Pide el mismo estático o endpoint por Service/localhost y descarta el body después de medirlo. Para endpoints protegidos usa credenciales ya disponibles dentro del pod/proceso, nunca las imprimas ni las pongas en argumentos visibles/historial; informa solo código, duración y bytes. Si el cliente externo es lento pero la lectura interna es rápida, investiga cliente/Ingress/tailnet antes de ajustar LiteLLM, DB o recursos.

6. **Inspecciona la ruta Tailscale del peer exacto.** Resuelve el hostname, localiza ese peer en `tailscale status --json` y observa `Relay` (valor no vacío indica DERP); `tailscale ping <host>` aporta RTT/ruta y `tailscale netcheck` aporta conectividad/DERP cercano. Filtra la salida al peer objetivo en vez de imprimir todo el inventario. Un RTT alto puede reducir el rendimiento, pero no cuantifica throughput: conserva una transferencia HTTP real con bytes y duración como evidencia.

7. **Correlaciona API y logs.** Mide las llamadas que la UI inicia (incluidas llamadas autenticadas, cuando sea seguro) una por una o con concurrencia moderada; recoge path, status, bytes y duración, sin cuerpo. Correlaciona su ventana temporal con errores/timeouts del pod y dependencias. Muchos `200` no prueban rapidez; la ausencia de duración en access logs tampoco.

8. **Comprueba caché y compresión sin asumir el efecto.** Los bundles versionados deberían poder comprimirse y cachearse de forma larga e inmutable. La falta de `Cache-Control` puede ampliar cargas frías o bypass de caché; ETag/`If-None-Match` puede permitir un `304` rápido. Prueba una revalidación condicional y distingue recarga normal de bypass: no afirmes que cada refresh vuelve a descargar todos los bytes sin medirlo en el navegador.

9. **Valida en el navegador del usuario.** Usa DevTools/Performance o HAR para distinguir DNS/connect/TLS/TTFB/download y localizar el recurso o request que bloquea `DOMContentLoaded`/`load`. Si no se dispone de esa sesión, declara que las medidas curl son del host de diagnóstico y no equivalen a un waterfall del navegador; pide un HAR de ese mismo cliente para cerrar la atribución y procesalo con la sección *Triage del HAR del cliente*.

## Triage del HAR del cliente

Un HAR no se lee a ojo: son megabytes de cuerpos en base64 y lo que decide el diagnóstico son
unas pocas relaciones entre campos. Parsealo con un script (Python + `json`) y proyectá solo los
campos que importan; no vuelques el archivo al contexto del chat.

1. **¿El retraso es posterior al servidor?** Compará el header `date` de la respuesta con
   `startedDateTime + blocked + connect + send + wait`. Si el `date` coincide con el instante del
   request y el primer byte llega decenas de segundos después, **el origen contestó al instante y
   todo el retraso es transporte**. Es la prueba más fuerte disponible y no necesita tocar el pod;
   `date` tiene resolución de 1 s, suficiente para separar segundos de minutos.
2. **Throughput real por request** = `response.content.size / timings.receive` (el cuerpo, no
   `time`), solo para cuerpos > 4 KB. Reportá mínimo, mediana y máximo: un único promedio esconde
   el colapso.
3. **¿Falta compresión?** Compará `response.content.size` con `_transferSize` y buscá
   `content-encoding` en la respuesta. Si son iguales y no hay `content-encoding` pese a que el
   request ofreció `accept-encoding: gzip, deflate, br, zstd`, **nada en el camino comprime** y el
   JS viaja crudo — en una SPA, la mayor parte del peso.
4. **¿Cuántos streams simultáneos sobre una conexión?** Agrupá las entradas por `_connectionId` y
   contá los solapes de `[startedDateTime, startedDateTime + time]` por página. N recursos en
   paralelo sobre un enlace que sostiene X KB/s dan ≈ X/N cada uno: el agregado colapsa y cada
   request parece colgado. Valores de `wait` **idénticos** en varias entradas = el navegador liberó
   esos streams a la vez (serialización a nivel de stream, no de servidor).
5. **`pageTimings.onLoad` / `onContentLoad` en `null`** = la página **nunca terminó**. Es distinto
   de un bucle de redirección: contá las entradas con `_resourceType: document` y comprobá
   `redirectURL` y URLs repetidas antes de dar por bueno el «loop infinito» que reporta el usuario.
   Si el agregado también colapsa, la recarga manual que hace el usuario se suma al problema en
   lugar de resolverlo.

### Pitfalls del HAR

- **No le pidas al usuario marcar «Disable cache» si vas a medir caché.** Contamina la captura:
  todas las subresources salen con `cache-control: no-cache` + `pragma: no-cache` puestos por el
  cliente y `cache: {}` en cada entrada, así que ningún reuso de caché es observable. Pedí la
  captura con la caché activada —o las dos, si querés separar el efecto— y detectá el artefacto
  por esa firma exacta antes de concluir «no hay caché».
- **Sanear el HAR rompe la atribución de sesión.** Borrar `Cookie`/`Authorization` (correcto por
  secretos) deja los requests sin header `cookie`: **no podés afirmar ni descartar nada sobre auth
  ni sobre una redirección a login**. Declaralo como límite del análisis en vez de inferirlo de una
  cookie ausente.
- **`status: 0` con `_error: net::ERR_ABORTED` y `blocked` alto** = el usuario abandonó esa
  navegación; es el primer síntoma, no un error de red.
- **`dns`, `ssl` y `connect` en `-1`** = reutilización de conexión, no un fallo. Un `_connectionId`
  compartido por todas las respuestas lo confirma.
- **`serverIPAddress` en `100.x`** = el cliente salió por el tailnet directo al ingress, sin pasar
  por DNS público ni por el túnel: lo medido ahí describe el camino tailnet.
- **Subdividir last-mile vs. relay DERP no sale del HAR.** Cuando (1) y (2) ya probaron que el
  retraso es de transporte, el HAR acota la capa pero no la subdivide: hace falta medirlo **en el
  dispositivo afectado** (`tailscale netcheck`, `tailscale ping --verbose <host>`). Un `Relay` o un
  RTT leído desde el host de diagnóstico describe el camino de ese host, no el del cliente
  reportado.

### Cómo se cierra la atribución

Separá tres bloques en la entrega: **verificado** (lo que muestran los campos, con la relación que
lo prueba), **no verificado** (lo que el HAR no puede separar y qué medición haría falta) y
**amplificadores** (compresión, caché, concurrencia: agrandan el problema pero no lo causan, y
arreglarlos no vuelve el camino rápido). No cierres con un culpable único si el diagnóstico acota la
capa sin subdividirla.

## Matriz de atribución

| Evidencia | Capa prioritaria |
|---|---|
| `/ui/` y recursos lentos también por Service dentro del clúster | pod/app o dependencia; correlacionar endpoints y logs |
| HTML rápido, estáticos lentos solo por URL externa, rápidos por Service | cliente, ruta tailnet o Ingress; revisar bytes/segundo y relay del peer |
| HTML/estáticos rápidos, una llamada API lenta | handler/API o dependencia llamada por esa ruta |
| TTFB alto tanto externo como interno | servidor/app/dependencia; revisar CPU, memoria, DB/cache y logs |
| `Running`/health 200 pero navegador lento | evidencia insuficiente: medir recursos y APIs del navegador |
| `date` del server == instante del request, TTFB del cliente de decenas de segundos, throughput < 10 KB/s | transporte cliente↔ingress (tailnet/last-mile); el origen queda descartado |
| Todo sobre un solo `_connectionId`, con `wait` creciente y valores repetidos entre entradas | saturación de una única conexión; reducir el payload (compresión/caché) antes de tocar el pod |
| `onLoad: null` sin navegaciones repetidas ni `redirectURL` | la carga no termina, no es un bucle; priorizar el peso total y el throughput |

Antes de cambiar manifiestos, proxy, caché o recursos, identifica cuál patrón aplica y conserva la medición de referencia. Los cambios permanentes de exposición/configuración siguen el flujo GitOps del repo.