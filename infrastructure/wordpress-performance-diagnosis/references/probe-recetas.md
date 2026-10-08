# Recetas de sondeo: WordPress en Kubernetes

Snippets listos para copiar. El porqué de cada paso, en `SKILL.md`.

## Medir las tres capas del mismo sitio

```bash
# 1) por el borde (Cloudflare)
for i in 1 2 3; do curl -s -o /dev/null -w 'borde   ttfb=%{time_starttransfer} total=%{time_total} code=%{http_code}\n' "https://<dominio>/?cb=$RANDOM$i"; done

# 2) por el ingress, desde adentro del tailnet (sin borde)
for i in 1 2 3; do curl -s -o /dev/null -w 'ingress ttfb=%{time_starttransfer} total=%{time_total} code=%{http_code}\n' "https://<sitio>.<tailnet>.ts.net/?cb=$RANDOM$i"; done

# 3) por el pod (el número de la home es el de la ÚLTIMA respuesta)
kubectl -n <ns> exec deploy/<sitio> -- sh -c 'for i in 1 2 3; do curl -sL -o /dev/null \
  -w "pod     ttfb=%{time_starttransfer} total=%{time_total} redir=%{num_redirects} size=%{size_download}\n" \
  -H "Host: <dominio>" -H "X-Forwarded-Proto: https" "http://127.0.0.1/?cb=$RANDOM$i"; done'
```

Comparar `%{time_starttransfer}` **de la última respuesta**: en una cadena con redirect, ese
es el tiempo del render, y el redirect suma su propio round trip aparte.

## Barrido de redirects: qué URLs redirigen

```bash
kubectl -n <ns> exec deploy/<sitio> -- sh -c '
for u in "/" "/?v=abc" "/index.php" "/feed/" "/wp-json/" "/robots.txt" "/sitemap_index.xml" "/wp/wp-login.php" "/un-post-real/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: <dominio>" -H "X-Forwarded-Proto: https" "http://127.0.0.1${u}")
  loc=$(curl -sD- -o /dev/null -H "Host: <dominio>" -H "X-Forwarded-Proto: https" "http://127.0.0.1${u}" | grep -i "^location" | tr -d "\r" | cut -c1-90)
  echo "$code  $u  $loc"
done'
```

### Cómo leer la tabla

| Observación | Significado |
|---|---|
| `307` con un parámetro **agregado** a la misma URL (`?v=<hash>`) en `/`, `/feed/` y las páginas | *cache buster* de front-end: defecto de rendimiento, no señal de salud |
| ese `307` **no** aparece en `/wp-json/`, `/robots.txt`, `/sitemap_index.xml` ni en los estáticos del core | el culpable es un hook de front-end de WordPress, no el web server ni el proxy |
| `/?v=abc` también redirige al hash actual | compara versiones, no canonicaliza |
| `301` a `https://` a secas | redirect canónico, benigno |
| `X-Redirect-By: WordPress` en la respuesta | lo emite `wp_redirect()`, no un proxy |

### Qué NO sirve para identificar el origen (probado)

- Grepear el árbol de código: plugins, tema, tema padre, mu-plugins.
- Buscarlo en `wp_options`, **incluido el valor del hash**: si no está persistido se calcula y
  cambia entre mediciones. Buscarlo igual es barato; un "no está" no cierra el caso.
- Las tablas de redirecciones de plugins de SEO (si no existen, el módulo no está activo).

### Qué sí lo acota

`wp_redirect()` vive en `wp-includes/pluggable.php`, así que es **reemplazable**: se puede
interceptar con `php -d auto_prepend_file=<archivo>` **antes** de que WordPress cargue y volcar
la traza con `wp_debug_backtrace_summary()`. **Tiene que correr en el SAPI web**: en CLI el
redirect no se dispara.

## Receta de probe en PHP

```bash
kubectl -n <ns> cp probe.php <ns>/<pod>:/tmp/probe.php
kubectl -n <ns> exec deploy/<sitio> -- php -d memory_limit=1024M /tmp/probe.php
```

Booteo en dos tiempos — es la única forma de registrar un hook (no se puede antes de que
exista `add_filter`, y precargar `class-wp-hook.php` choca contra el `require` de
`wp-settings.php`: `Cannot declare class WP_Hook`):

```php
<?php
define('SAVEQUERIES', true);                 // antes de wp-load si querés el conteo de queries
$_SERVER['REQUEST_URI']='/'; $_SERVER['HTTP_HOST']='<dominio>'; $_SERVER['SERVER_NAME']='<dominio>';
$_SERVER['HTTPS']='on'; $_SERVER['REQUEST_METHOD']='GET'; $_SERVER['REMOTE_ADDR']='127.0.0.1';
$_SERVER['SCRIPT_NAME']='/index.php'; $_SERVER['SERVER_PORT']='443';
function L($s){ fwrite(STDERR, $s."\n"); }  // STDERR: el render contamina stdout

$t0 = microtime(true);
require '/var/www/html/web/wp/wp-load.php';   // acá ya existen add_filter() y get_num_queries()
L(sprintf('BOOT(wp-load)=%.3fs', microtime(true)-$t0));

add_filter('wp_redirect', function($loc,$st){ L("REDIRECT $st -> $loc\n".wp_debug_backtrace_summary()); return $loc; }, PHP_INT_MAX, 2);

$t1 = microtime(true);
ob_start(); wp(); $html = ob_get_clean();       // dispatch completo
L(sprintf('DISPATCH=%.3fs SIZE=%d QUERIES=%d', microtime(true)-$t1, strlen($html), get_num_queries()));

global $wpdb; $q = (array) $wpdb->queries; usort($q, fn($a,$b) => $b[1] <=> $a[1]);
foreach (array_slice($q, 0, 12) as $r) L(sprintf('  %.4fs %s', $r[1], substr(preg_replace('/\s+/',' ',$r[0]),0,140)));
```

### Trampas del probe

- **`-d memory_limit=1024M` siempre.** Con el default, `wp-load` muere por OOM y lo que se ve
  es la pantalla "Ha habido un error crítico en esta web", que parece un bug del sitio y es el
  probe. Sin `display_errors` ese fatal sale por **STDOUT**: capturar `>/tmp/o.txt 2>&1` en vez
  de descartar stdout, o el error se pierde.
- Escribir todo a **STDERR** (`fwrite(STDERR, …)`), nunca `echo`.
- Verificar si hay `php-cgi` en la imagen (`command -v php-cgi`); si no lo hay, el CLI es la
  única vía — y **el CLI no reproduce el contexto web**.
- Si usás `-d auto_prepend_file=…`, probar el prepend con un caso trivial antes de confiar en
  que el probe automático corrió.

## Leer la base sin manejar credenciales

El pod ya tiene `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` en su entorno.

**Antes de lanzar el probe, verificar qué extensión de MySQL está disponible**: no todas las
imágenes incluyen `pdo_mysql`. La imagen `wordpress-producto` (Apache/PHP) tiene `mysqli` y
`pdo_sqlite` pero NO `pdo_mysql`. Si el probe muere con `could not find driver`, usar la
variante con `mysqli`:

```bash
# Verificar extensiones disponibles
kubectl -n <ns> exec deploy/<sitio> -- php -m 2>&1 | grep -iE 'mysql|pdo'
```

### Variante PDO (preferida si pdo_mysql está disponible)

```bash
kubectl -n <ns> exec -i deploy/<sitio> -- php -r '
$pdo = new PDO("mysql:host=".getenv("DB_HOST").";dbname=".getenv("DB_NAME").";charset=utf8mb4", getenv("DB_USER"), getenv("DB_PASSWORD"));
foreach (["home","siteurl","template","stylesheet","WPLANG"] as $o) {
  $s = $pdo->prepare("select option_value from wp_options where option_name=?"); $s->execute([$o]);
  printf("  %s = %s\n", $o, $s->fetchColumn());
}
$r = $pdo->query("select count(*) c, sum(length(option_value)) s from wp_options where autoload in (\"yes\",\"on\",\"auto-on\",\"auto\")")->fetch();
printf("  autoload: %s filas / %s bytes EN CADA REQUEST\n", $r["c"], $r["s"]);
$ap = $pdo->query("select option_value from wp_options where option_name=\"active_plugins\"")->fetchColumn();
foreach (unserialize($ap) as $p) echo "  plugin: $p\n";
foreach ($pdo->query("select status, count(*) c from wp_actionscheduler_actions group by status") as $x) printf("  scheduler %s=%s\n", $x["status"], $x["c"]);
foreach ($pdo->query("select table_name, round((data_length+index_length)/1048576,1) mb from information_schema.tables where table_schema=database() order by (data_length+index_length) desc limit 8") as $x) printf("  %-38s %s MB\n", $x["table_name"], $x["mb"]);
'
```

### Variante mysqli (fallback cuando no hay pdo_mysql)

```bash
kubectl -n <ns> exec -i deploy/<sitio> -- php -r '
$m = new mysqli(getenv("WORDPRESS_DB_HOST"), getenv("WORDPRESS_DB_USER"), getenv("WORDPRESS_DB_PASSWORD"), getenv("WORDPRESS_DB_NAME"));
foreach (["home","siteurl","template","stylesheet","WPLANG"] as $o) {
  $r = $m->query("select option_value from wp_options where option_name='$o'");
  printf("  %s = %s\n", $o, $r->fetch_row()[0]);
}
$r = $m->query("select count(*) c, sum(length(option_value)) s from wp_options where autoload in ('yes','on','auto-on','auto')")->fetch_assoc();
printf("  autoload: %s filas / %s bytes\n", $r["c"], $r["s"]);
foreach ($m->query("select status, count(*) c from wp_actionscheduler_actions group by status") as $x) printf("  scheduler %s=%s\n", $x["status"], $x["c"]);
foreach ($m->query("select table_name, round((data_length+index_length)/1048576,1) mb from information_schema.tables where table_schema=database() order by (data_length+index_length) desc limit 8") as $x) printf("  %-38s %s MB\n", $x["table_name"], $x["mb"]);
'
```

**Las variables de entorno varían por imagen**: en imágenes de WordPress oficial es `WORDPRESS_DB_HOST`/`WORDPRESS_DB_USER`/`WORDPRESS_DB_PASSWORD`/`WORDPRESS_DB_NAME`; en imágenes personalizadas pueden ser `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`. Revisar con `env | grep -E 'DB_|WORDPRESS_DB'` antes de lanzar el probe.

Consultas que valen la pena en cada revisión de rendimiento:

| Consulta | Qué te dice |
|---|---|
| `autoload` en `wp_options` (filas y bytes) | cuánto se lee en **cada** request; cientos de KB es trabajo regalado |
| `wp_actionscheduler_actions` por `status` | cola de WooCommerce: muchos `pending`/`failed` = cron que no corre |
| `wp_options` con `_transient_timeout_` vencido | basura acumulada |
| `information_schema.tables` por tamaño | dónde está el peso real de la base |

Nunca imprimir el valor de una credencial ni leer `.data` de un Secret.

## WP-Cron y la cola de Action Scheduler

```bash
# ¿está apagado el cron de WordPress? Buscar en wp-config.php (imagen estándar) o application.php (Bedrock)
kubectl -n <ns> exec deploy/<sitio> -- sh -c 'grep -nE "DISABLE_WP_CRON" /var/www/html/wp-config.php /var/www/html/config/application.php 2>&1'
# ¿el loopback sale a internet y muere? Buscar en TODOS los conectores cloudflared del clúster
kubectl get deploy -A | grep cloudflare | awk '{print $1,$2}' | while read ns dep; do
  echo "=== $ns/$dep ==="
  kubectl -n $ns logs deploy/$dep --tail=200 | grep -iE "wp-cron|as_async_request|context canceled" | tail -5
done
```

Firma del problema: `wp-cron.php?doing_wp_cron=…` y
`admin-ajax.php?action=as_async_request_queue_runner` terminando en
`Incoming request ended abruptly: context canceled`, con la cola del scheduler en
`pending`/`failed`. El arreglo es `DISABLE_WP_CRON=true` + un CronJob que pegue **por dentro
del Service**, nunca por el hostname público.

## Longhorn: leer los CRD con `-A`

```bash
kubectl get volumes.longhorn.io -A -o custom-columns='NAME:.metadata.name,STATE:.status.state,ROBUSTNESS:.status.robustness,REPLICAS:.spec.numberOfReplicas,NODE:.status.currentNodeID'
```

Los CRD son *cluster-scoped* y el release puede vivir en otro namespace: consultarlos con
`-n longhorn-system` devuelve *No resources found* con el storage sano. **Un vacío que
confirma lo que uno sospecha no es un dato.**

## Estado de la app: dónde está la verdad

`kubectl -n flux-system get kustomizations` (y el `suspend` del manifiesto del clúster)
gobiernan si la app está activa; el `README` de la carpeta de la app y los docs de exposición
pueden quedar atrás. Verificado que divergen: un README declaraba "no activo, `suspend: true`"
con el sitio sirviendo tráfico.

## Quién sirve realmente: DNS + túnel + Ingress

Cuando un dominio responde pero no está claro desde dónde, triangular:

```bash
# 1) DNS: ¿apunta a Cloudflare o va directo al host?
dig +short <dominio> A
# 2) Túnel: ¿qué cloudflared tiene este hostname en su config remota?
kubectl get deploy -A | grep cloudflare | awk '{print $1,$2}' | while read ns dep; do
  echo "=== $ns/$dep ==="
  kubectl -n $ns logs deploy/$dep --tail=500 | grep 'Updated to new configuration' | tail -1 | python3 -c "import sys,json; [print(f'  {r[\"hostname\"]} -> {r[\"service\"]}') for r in json.loads(json.loads(sys.stdin.read().split('config=')[1]).replace('\\\\',''))['ingress'] if 'hostname' in r]" 2>&1
done
# 3) En el clúster: ¿qué Ingress/Service/endpoints hay para este hostname?
kubectl get ingress -A | grep -i <dominio>
kubectl -n <ns> get endpoints
```
