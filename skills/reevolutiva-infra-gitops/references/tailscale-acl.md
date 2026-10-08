# Tailscale ACL para reevolutiva-infra

## Cómo se edita (2026-10-06)

Las credenciales de la API de Tailscale están en AKV:
- `tailscale-client-id`
- `tailscale-client-secret`

Para hacer cambios:

```bash
export TS_CLIENT_ID=$(az keyvault secret show --vault-name giorgio --name tailscale-client-id --query value -o tsv)
export TS_CLIENT_SECRET=$(az keyvault secret show --vault-name giorgio --name tailscale-client-secret --query value -o tsv)

TOKEN=$(curl -sS -m 15 -X POST "https://api.tailscale.com/api/v2/oauth/token" \
  -d "client_id=${TS_CLIENT_ID}" \
  -d "client_secret=${TS_CLIENT_SECRET}" \
  -d "grant_type=client_credentials" \
  -d "scope=all" | jq -r '.access_token')

# Leer ACL actual (HuJSON)
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://api.tailscale.com/api/v2/tailnet/coyote-paridae.ts.net/acl" > acl.hujson

# Editar y hacer POST (HuJSON, no JSON!)
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/hujson" \
  -d @acl_patched.hujson \
  "https://api.tailscale.com/api/v2/tailnet/coyote-paridae.ts.net/acl"
```

## Reglas SSH

```json
"ssh": [
  {"action": "check", "src": ["autogroup:member"], "dst": ["autogroup:self"], "users": ["autogroup:nonroot", "root"]},
  {"action": "accept", "src": ["tag:server"], "dst": ["tag:server"], "users": ["root", "autogroup:nonroot"]},
  {"action": "accept", "src": ["giolapietra@github"], "dst": ["tag:server"], "users": ["giolapietra"]},
]
```

## Tags

| Tag | Owner | Dispositivos |
|-----|-------|-------------|
| `tag:server` | (nadie) | frontdoor, gio-zorin, hosting, imac27, MacBook-Air-de-Giorgio, produccion, vm-dev, vm-services, vm-worker |
| `tag:k8s` | autogroup:admin | k8s operator pods |
| `tag:k8s-operator` | autogroup:admin | TS Operator |
| `tag:giolapietra` | giolapietra@github | (personal) |

## Reglas importantes

- **Un FQDN como dst en SSH rule es rechazado** por la API (`invalid dst "vm-services.coyote-paridae.ts.net"`). Siempre usar tags o dirección IP del tailnet.
- **vm-services NO tenía tag hasta 2026-10-06**. Por eso SSH fallaba incluso con `tailscale up --ssh`.
- Para aplicar un tag a un dispositivo: POST `/api/v2/device/{id}/tags` con `{"tags": ["tag:server"]}`.
- **scope=all** en el OAuth token da acceso a todo incluyendo ACL write. El token expira en 3600 s.

## Trampas

- La API devuelve **HuJSON** (JSON con comentarios //). jq no lo parsea. Usar sed para limpiar o Python con `json.loads(re.sub(r'//.*', '', raw))`.
- El endpoint POST `/tailnet/{tailnet}/acl` **reemplaza toda la ACL** — no hay merge automático. Cuidado con no eliminar reglas existentes.
- Un PATCH es la misma URL con `acceptHeader: application/hujson` pero la API maneja la diferencia: POST reemplaza, PATCH hace merge parcial (soportado desde v2).
