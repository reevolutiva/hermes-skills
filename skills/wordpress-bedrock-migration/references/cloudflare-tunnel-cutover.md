# Corte de un túnel de Cloudflare: leer y escribir la config por API

Aplica cuando la exposición pública entra por un **Cloudflare Tunnel** cuyo contenedor
corre con `TUNNEL_TOKEN` (config **remota**) — el caso de los hosts legacy de este infra.
El corte es cambiar el `service` de un hostname; **el DNS no se toca**.

## 1. Confirmar de dónde salen las reglas

```bash
docker inspect <contenedor> --format '{{range .Config.Env}}{{println .}}{{end}}' | grep TUNNEL_TOKEN
docker logs <contenedor> 2>&1 | grep -iE "config|ingress|updated"
```

- `Settings: map[config:/etc/cloudflared/config.yml]` → lee el archivo local.
- `Updated to new configuration … version=N` con reglas que **no coinciden** con ese
  archivo (menos hostnames, sin el wildcard) → las reglas son **remotas** y el archivo es
  un vestigio. Un contenedor con `TUNNEL_TOKEN` es remoto por construcción.

## 2. Identificar cuenta y túnel (sin exponer el secreto)

El token del conector es base64 de un JSON `{"a":<cuenta>,"t":<túnel>,"s":<secreto>}`:

```bash
docker inspect <contenedor> --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep '^TUNNEL_TOKEN=' | cut -d= -f2- | python3 -c '
import sys, base64, json
t = sys.stdin.read().strip()
p = json.loads(base64.b64decode(t + chr(61) * (-len(t) % 4)))
print("cuenta:", p.get("a"), "| tunel:", p.get("t"), "| secreto len:", len(p.get("s","")))
'
```

Ese token **no sirve para la API** (`6003 Invalid request headers`). El token de API es
**otro**, y puede estar guardado en el vault con el nombre mal escrito: **listar todos los
nombres y leerlos**, no filtrar por el que uno espera. Comparar dos tokens sin imprimirlos:
`printf '%s' "$X" | sha256sum`.

## 3. Leer y escribir la configuración

```bash
ACCT=<cuenta>; TUN=<túnel>; TOK=<token de API>
API="https://api.cloudflare.com/client/v4/accounts/$ACCT/cfd_tunnel/$TUN/configurations"

# leer (las reglas autoritativas)
curl -s -H "Authorization: Bearer $TOK" "$API"

# listar los túneles de la cuenta (confirma nombre y conexiones)
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.cloudflare.com/client/v4/accounts/$ACCT/cfd_tunnel?is_deleted=false"

# escribir: el corte
curl -s -X PUT -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" "$API" \
  --data '{"config":{"ingress":[
    {"hostname":"otro.dominio","service":"http://127.0.0.1:3978"},
    {"hostname":"<dominio>","service":"https://<ip-del-origen>","originRequest":{"httpHostHeader":"<dominio>","originServerName":"<nombre-tls>"}},
    {"service":"http_status:404"}
  ]}}'
```

- **El `PUT` reemplaza la lista completa**: incluir todas las reglas, no solo la que
  cambia. La lectura previa **es** el rollback — guardarla antes de escribir.
- `httpHostHeader` evita que WordPress redirija en bucle al ver un `Host` distinto del
  canónico.
- `originServerName` es el nombre que se usa para SNI y verificación TLS cuando el
  `service` apunta a una **IP**.
- Un token *account-scoped* devuelve `1000 Invalid API Token` en `/user/tokens/verify` y
  funciona igual en `/accounts/…`. La prueba es el endpoint real, no el de verify.

## 4. Elegir el destino

| Destino | Cuándo | Ojo |
|---|---|---|
| `http://127.0.0.1:<puerto>` | el sitio sigue en la VM | es el valor que se conserva para el rollback |
| `https://<nombre>.ts.net` | ingress de Tailscale | **502**: un contenedor con `network_mode: host` no resuelve MagicDNS |
| `https://<ip-del-tailnet>` + `originServerName` | el mismo ingress | funciona; **frágil**: si el operator recrea el proxy, la IP cambia |
| cloudflared **dentro** del clúster | el destino correcto | el ingress se mueve con la carga y queda en Git |

## 5. Verificar el corte

```bash
curl -sSL -o /tmp/cut.html -w '%{http_code} %{size_download}\n' https://<dominio>/
kubectl -n <ns> logs <pod-nuevo> --tail=10 | grep -v kube-probe   # la request propia DEBE aparecer
ssh <host-legacy> 'docker logs <contenedor-legacy> --since 90s'    # y NO aparecer acá
```

Un `200` detrás de Cloudflare puede ser caché del edge. El corte se cierra cuando la
request propia aparece en el origen nuevo y desaparece del viejo.

## 6. Antes y después

- **Delta de datos**: comparar `max(post_modified)` y el conteo de pedidos/reservas del
  sitio vivo contra el timestamp del backup restaurado. Anterior ⇒ la copia ya está al
  día y no hace falta dump fresco.
- **Rollback**: el `PUT` con el valor anterior, con el contenedor legacy corriendo.
- **Deuda que deja este corte**: la credencial del conector fuera del vault y una IP de
  proxy como destino. Anotarla — un destino que no es un recurso del clúster se rompe
  cuando el proxy se recrea.