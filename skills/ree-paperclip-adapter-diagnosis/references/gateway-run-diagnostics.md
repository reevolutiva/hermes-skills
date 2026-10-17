# Diagnóstico de ejecuciones Hermes gateway

Pasos para correlacionar un run de `hermes_gateway` que no progresa usando tres
planos de evidencia: Paperclip, Hermes (API + almacenamiento) y código del
adapter instalado. Ejecutar solo lecturas hasta tener hipótesis basada en
evidencia; cualquier mutación (clean-up, heartbeat, restart) requiere
autorización.

Esta referencia complementa el procedimiento P5 de `ree-paperclip-adapter-diagnosis`.

## 1. Triangulación de run IDs

Desde Paperclip:
```bash
paperclipai agent runtime-state <agentId> --json
```
Registrar `lastRunId` (Paperclip), `lastRunStatus`, `lastError`, `sessionId` y
`sessionParamsJson.hermesRunId` (`run_<hex>`) si existe.

Si no se dispone de `hermesRunId` directo, consultar:
```bash
paperclipai issue runs <issueId> --json
paperclipai issue active-run <issueId> --json
```
Tomar el `runId` Paperclip más reciente que coincida temporalmente.

Algunas instalaciones pueden guardar logs:
```
~/.paperclip/instances/<instanceId>/data/run-logs/<companyId>/<agentId>/<paperclipRunId>.ndjson
```
Comparar líneas de una ejecución fallida contra una exitosa (mismos agente y
gateway) ayuda a detectar dónde se detuvo el progreso (creación, silencio
posterior, stop, timeout).

## 2. Inspeccionar el estado del run Hermes

```bash
curl -sS -H "Authorization: Bearer $API_SERVER_KEY" \
  "<apiBaseUrl>/v1/runs/<hermesRunId>"
```
El `apiBaseUrl` debe ser el configurado en `adapterConfig.apiBaseUrl` del
agente, verificado contra `agent configuration`. No inferirlo solo de
`test-environment`.

Registrar y anonimizar antes de compartir:
- `status` (p. ej. `started`, `completed`, `failed`, `running`).
- `admission_id` (si existe).
- Longitud de `output` disponible y presencia de campos esperados
  (`run_id`, `session_id`).
- Timestamps relevantes (no compartir valores de sesión/secreto).

Un status `started` sin eventos posteriores apunta a problema de dispatch,
admissions o payload. No reiniciar ni re-run sin hipótesis formada.

## 3. `buildRunBody()` y payload enviado

En la versión `2026.1012.0`, el código del adapter gateway envía a `POST
/v1/runs` un objeto construido por `buildRunBody()`:

```js
function buildRunBody(ctx, sessionKey) {
    return {
        ...payloadTemplate,
        input,        // contenido del prompt compuesto
        instructions, // comportamiento de alto nivel
        ...(sessionKey ? { session_id: sessionKey } : {}),
    };
}
```

Observaciones sobre ese payload:

- Si `payloadTemplate` contiene propiedades adicionales como `model`, se
  incluyen; en el código de referencia no se inserta un campo `model` por
  defecto.
- `sessionKey` se deriva de la estrategia configurada (issue, agent, run o
  none); una clave mal resuelta puede mapear mal admissions o sesiones.
- El endpoint Hermes espera ciertos campos; si falta `model` explícito, Hermes
  puede aceptar el run e intentar progresar sin `API call #1`. El síntoma es
  status `started` sin eventos.

No asumir que el payload es correcto porque la versión del adaptador sea la
última. Inspeccionar el código instalado con `read_file` sobre
`~/.paperclip/cli/current/node_modules/@paperclipai/hermes-paperclip-adapter/dist/gateway/server/execute.js`
y comparar con el contrato Hermes de la versión desplegada.

## 4. Inspección de admissions

Las admissions viven en `~/.hermes/state.db` (SQLite). Acceso de solo lectura:

```bash
sqlite3 ~/.hermes/state.db ".headers on" ".mode column" \
  "SELECT target_session_id, status, owner_epoch, generation, created_at
   FROM session_admissions
   WHERE target_session_id IN (
     '<sessionKey de Paperclip>',
     '<sessionKey alternativa>'
   )
   ORDER BY created_at DESC
   LIMIT 60;"
```

Buscar:

- Filas `started` + `queued`/`unknown` para el mismo `target_session_id`
  sugieren admission-state corruption.
- Admiral huérfanas (`queued`/`unknown` con owner_epoch antiguo) que no avanzan
  ni se limpian pueden bloquear el dispatch aunque el adapter envíe payload
  correcto.
- Si todas las admisiones son `started` sin `terminal`, sospechar de dispatch o
  del payload, no de modelo/proveedor.

No eliminar filas directamente sin backup y autorización; la referencia solo
documenta cómo leer e interpretar.

## 5. Modelo en sessions

Las filas de `sessions` con el prefijo `paperclip:run:` algunas veces se crean
con `model` o `model_config` nulos:

```bash
sqlite3 ~/.hermes/state.db \
  "SELECT session_id, model, model_config,
          json_extract(payload, '$.model') AS payload_model
   FROM sessions
   WHERE session_id LIKE 'paperclip:run:%'
   ORDER BY created_at DESC
   LIMIT 30;"
```

Si la `session` asociada al run actual tiene ambos campos nulos y `buildRunBody`
no está insertando un modelo explícito, la ejecución puede quedar `started` sin
`API call #1`. En ese caso la causa raíz es defecto de payload, no timeout,
admission cleanup ni heartbeat.

## 6. Correlación temporal y falsos positivos

- Alinear timestamps: un rate-limit 429 en logs Hermes de horas antes no es
  causa del run actual.
- `paperclipai service restart` o reinicio de gateway no son fixes primarios;
  pueden generar un epoch nuevo y enmascarar admissions duplicadas sin
  resolverlas.
- Una vez formada hipótesis con evidencia de los tres planos, proponer plan
  (limpiar admissions, ajustar payload, corregir sessionKey, reparar auth) y
  solicitar autorización antes de cualquier acción de escritura.