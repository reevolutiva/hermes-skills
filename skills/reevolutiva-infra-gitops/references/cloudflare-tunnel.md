# El túnel de Cloudflare que expone familey.cl

## Qué es

Túnel **`front`** (`0e205852-572d-48ea-94a1-6c4408727100`), cuenta
`<CF_ACCOUNT_ID>`. Corre en `frontdoor` como el contenedor
`litellm-ingress-1`, con `TUNNEL_TOKEN` en el entorno y `network_mode: host`.
**No hay `docker-compose.yaml`** en `/opt/litellm/`: se creó con `docker run`.

Sus reglas son **configuración remota** (dashboard/API). El
`/workspace/litellm/cloudflared/config.yml` del host **se lee y se ignora**: editarlo no
cambia el ruteo.

## Credenciales

| Para qué | Dónde | Nombre |
|---|---|---|
| Leer y escribir las reglas (API) | AKV `giorgio` | **`CLOUDFLARE-API-TOKEN`** (funcional) |
| (candidato viejo) | AKV `giorgio` | `cloudlfare-token` (con typo) — puede expirar y dar 400 |
| El conector (corre el túnel) | entorno del contenedor | `TUNNEL_TOKEN` — **NO está en AKV** |

`cloudflare-tunnel-token` en AKV **no es el del contenedor** (184 vs 180 caracteres,
distinto sha256) y tampoco sirve para la API (`6003 Invalid request headers`).
`h-cloudflare-account-token` sí autentica pero **no tiene permiso sobre el túnel**
(`1001 Not authorized`).

**Trampa de búsqueda:** el token de API puede estar entre nombres similares y hasta expirar.
Filtrar por `contains(name,'cloudflare')` puede devolverte un token viejo que “parece el correcto” pero falla.

**Regla:** listar **todos** los nombres del vault (`az keyvault secret list --query "[].name" -o tsv`),
probar explícitamente `CLOUDFLARE-API-TOKEN` y el candidato viejo con typo, y confirmar por API `success: true` antes de asumir.


## Leer y escribir las reglas

```bash
ACCT=<CF_ACCOUNT_ID>
TUN=0e205852-572d-48ea-94a1-6c4408727100
TOK=$(az keyvault secret show --vault-name ${VAULT_NAME} --name cloudlfare-token --query value -o tsv)
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.cloudflare.com/client/v4/accounts/$ACCT/cfd_tunnel/$TUN/configurations"
```

El `PUT` a la misma URL con `{"config":{"ingress":[…]}}` **reemplaza** las reglas: es el
corte y el rollback. Ojo: el endpoint `/user/tokens/verify` devuelve `1000 Invalid API
Token` para tokens *account-scoped*, aunque funcionen — no confundir eso con un token roto.

**Guardá la config actual con su número de versión antes de tocar nada**: es el rollback y es
lo que hace reversible el cambio. Y después del `PUT`, releé el JSON **crudo**
(`jq -c '.result.config.ingress[0:2]'`): la API guarda y devuelve **camelCase**
(`originRequest.httpHostHeader`), así que un `jq` con el camino `snake_case` muestra `hdr=-` y
parece que la cabecera no se aplicó cuando sí está.

## Identificar qué túnel sirve un conector (por config, no por nombre)

Un deployment de `cloudflared` autentica con el token que le toque: **el nombre del secreto no
prueba a qué túnel se conectó.** En este repo, el secreto `cloudflare-tunnel-cluster-token`
abría el túnel **`front`**, mientras el túnel que sirve el camino público es **`produccion`**
(`<TUNNEL_ID>…`), con su propio token y su propio conector (`cloudflared-produccion`).

```bash
CF_TOKEN=$(az keyvault secret show --vault-name ${VAULT_NAME} --name cloudlfare-token --query value -o tsv)
ACC=<CF_ACCOUNT_ID>
curl -sS -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$ACC/cfd_tunnel?is_deleted=false" \
  | jq -r '.result[] | "\(.id) \(.name) \(.status)"'
# por túnel: reglas, versión y conexiones
curl -sS -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$ACC/cfd_tunnel/<id>/configurations" | jq '.result.version'
curl -sS -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$ACC/cfd_tunnel/<id>?is_deleted=false" \
  | jq -r '.result | "status=\(.status) conns=\(.connections|length)"'
```

**Gate de identificación:** la última línea `Updated to new configuration … version=N` del log del
conector tiene que coincidir con la `version` que devuelve esa URL para el túnel que creés que
sirve. Si no coincide, ese conector está en otro túnel y el DNS puede estar decidiendo otro camino
del que estás leyendo.

## Reglas: el destino es Traefik, y el puerto tiene que existir

El diseño (`infra/cloudflare/main.tf`) es `http://traefik.flux-system.svc.cluster.local:80` con
`originRequest.httpHostHeader = <hostname>`, para que Traefik rutee por `Host` al Ingress público de
cada sitio. Dos reglas que salieron caras:

- **Apuntar a `http://<svc>.<ns>.svc.cluster.local:80` cuando el Service expone 8088 no da error:
da timeout.** El `ClusterIP:80` no tiene listener, el paquete se descarta sin RST y el conector
cuelga (`dial tcp 10.43.x.x:80: i/o timeout`) hasta que el borde corta. Comparar cada regla con
`kubectl get svc -n <ns> <svc>` antes de aplicarla.
- **Un hostname con regla en el túnel pero sin Ingress público responde 404** desde el borde (el
conector entrega bien y Traefik no conoce el `Host`). Las dos piezas se declaran juntas: el mapa
`var.hostnames` de `infra/cloudflare/variables.tf` y el Ingress de `apps/<sitio>/`.

## El bucle de 301 a https: `X-Forwarded-Proto` y Traefik

El borde termina el TLS y el salto conector→Traefik es **HTTP plano**. Con el default del chart
(`forwardedHeaders.insecure: false`), Traefik **pisa** el `X-Forwarded-Proto: https` que manda el
conector y le entrega `http` al pod: WordPress (`is_ssl()`) redirige a https, el borde devuelve ese
301 al visitante que ya venía por https → **bucle** (`curl -L` corta con `Maximum (N) redirects
followed`).

- **Prueba directa, sin adivinar:** pedirle el sitio al **pod** con y sin la cabecera. Con
`X-Forwarded-Proto: https` el WP no redirige; sin ella aparece `x-redirect-by: WordPress`.
- **Fix declarado:** `ports.web.forwardedHeaders.insecure: true` (y `websecure`) en el HelmRelease de
Traefik. Confirmar que la clave existe en la versión del chart **antes** de escribirla — el render
tiene que cambiar:

```bash
helm show values traefik/traefik --version <v> | grep -n -B3 -A4 forwardedHeaders
helm template traefik traefik/traefik --version <v> --set ports.web.forwardedHeaders.insecure=true \
  | grep -A2 forwardedHeaders
```

Es correcto confiar en las cabeceras reenviadas acá: el único camino público es el túnel y Traefik
no está expuesto a internet.

- **Un `301` no es "el sitio anda".** Medir con `curl -L` y con `?cb=$RANDOM`; un 301 aceptado como
validación deja el bucle sin ver y el sitio sigue caído con otro síntoma.

## 404: distinguir el de ruteo del de aplicación

Un `404` desde el borde puede venir de tres capas, y se distinguen por el cuerpo y las cabeceras:

- **Traefik sin router para ese `Host`** (falta el Ingress público) → 404 pelado de Traefik.
- **OpenLiteSpeed** → su página por defecto (`server: LiteSpeed`, `<title> 404 Not Found</title>`),
típicamente porque el vhost no resuelve el directorio a `index.php` (`indexFiles index.html`) o
falta el `.htaccess` del rewrite en el webroot.
- **WordPress** → página del tema con el nombre del sitio y `x-pingback` en las cabeceras.

Y el ruteo se valida **sin el borde**, desde un pod de un namespace que la NetworkPolicy permita
(`cloudflare`/`reevolutiva` → `flux-system`): pedir el sitio con el `Host` correcto contra
`traefik.flux-system.svc.cluster.local`. Un `curl` desde el nodo o desde otro namespace da
`connection refused` por la NetworkPolicy, no porque Traefik esté caído.

## El corte de familey.cl (2026-09-25)

```json
{"config":{"ingress":[
  {"hostname":"jako.reevolutiva.cl","service":"http://127.0.0.1:3978"},
  {"hostname":"familey.cl","service":"https://<TAILSCALE_IP>",
   "originRequest":{"httpHostHeader":"familey.cl",
                    "originServerName":"wordpress-familey.coyote-paridae.ts.net"}},
  {"service":"http_status:404"}
]}}
```

`*.familey.cl` **no existe** en la configuración real: si algo dependía del wildcard, no
funciona. La zona `familey.cl` está en **otra** cuenta de Cloudflare (no figura entre las
zonas de `087e1ddd…`), pero eso no bloquea: el DNS ya apunta al túnel y el túnel rutea por
hostname.

## Trampas verificadas, en orden de aparición

### Cuando un túnel sirve orígenes en más de un clúster, el DNS `*.svc.cluster.local` es local a cada cluster

Si tu configuración remota apunta a `wordpress-*.<ns>.svc.cluster.local`, cualquier conector que reciba la request pero que no tenga ese service en su red (CIDRs/clusterIP/ CoreDNS) devolverá 502 aunque el sitio esté sano en el “otro” clúster.

**Regla:** o
- un túnel por clúster con reglas que apuntan al Service/IP de ese clúster, o
- todos los conectores del túnel deben poder alcanzar los mismos orígenes (misma red de servicios).

1. **El nombre del tailnet da 502.** `service: https://wordpress-familey.coyote-paridae.ts.net`
   falla: `cloudflared` corre con `network_mode: host` y usa el DNS del host, sin MagicDNS.
   Hay que resolver el nombre a la IP del proxy de ingress y usar `originServerName` para
   el SNI.
2. **La IP es interina y frágil.** `<TAILSCALE_IP>` es el proxy del ingress; si el operator
   lo recrea, la IP cambia y el sitio se cae. El destino correcto es cloudflared **dentro**
   del clúster, con las reglas en un ConfigMap.
3. **La IP real no está en el `.yml` del host.** Leerla por API.
4. **Un YAML local mal indentado impide que `cloudflared` arranque** — dio `HTTP 530`
   durante ~1 minuto. El archivo se ignora para rutear, pero **se parsea al arrancar**.
   Validar antes de reiniciar, siempre. Y **medir la indentación, no asumirla**: un patrón
   de `sed` con la indentación equivocada no matchea y da la falsa sensación de haber
   cambiado algo.
5. **El rollback es el mismo `PUT`** con `service: http://127.0.0.1:8088`. El contenedor
   legacy queda corriendo a propósito: eso es lo que hace que el corte sea reversible en
   ~40 segundos, y por eso vale la pena intentarlo.

## Verificar el corte (lo único que vale)

El `200` de Cloudflare no prueba nada — puede venir de caché. Hay que ver las requests
**en el pod**:

```bash
kubectl -n wordpress logs <pod-web> --tail=5 | grep -v kube-probe
```

Y que **dejen de aparecer** en el contenedor legacy (`docker logs wordpress-familey`).

## Antes de cortar cualquier WordPress: medir el delta

El riesgo del corte no es el downtime, es **perder datos**. Comparar la producción viva
con la copia antes de mover el ruteo: `max(post_modified)` en `wp_posts`, el conteo de
`wp_wc_orders` y de `wp_amelia_customer_bookings`, y `find <uploads> -newermt '<fecha del backup>'`.
En este caso el último cambio era de dos días antes del backup: no había delta, y el corte
no necesitó dump fresco. Medirlo **antes**, no después.
