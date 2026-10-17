---
name: ree-paperclip-adapter-diagnosis
description: "Diagnostica adapters Paperclip (OpenCode, LiteLLM, gateway)."
version: 0.2.0
author: Hermes
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [paperclip, adapter, opencode, litellm, gateway, diagnosis]
    related_skills: [ree-paperclip-board-ops, ree-hermes-paperclip-method]
---

# ree-paperclip-adapter-diagnosis — Diagnóstico de adapters Paperclip

Diagnostica y remedia de forma segura los adapters que sirven a Paperclip:
OpenCode (`opencode_local`), proxies LiteLLM como gateway de modelos, y Hermes
gateway (`hermes_gateway`). No administra la instancia ni opera el board.

## When to Use

- Un run no progresa (`stalled`/`queued`) y `agent runtime-state` muestra
  `Model unavailable`, `Command not found` o `401`.
- La UI lista modelos vacíos o `Command not found in PATH`.
- El adapter reporta `gateway_auth_failed` o un secreto parece desalineado.
- Hay que configurar un adapter nuevo o diagnosticar su provider/model.
- Un error ENOENT menciona `opencode.exe` bajo `dist/vendor/`.

### No usar para

- Operar el board (issues, PRs, steering): usar `ree-paperclip-board-ops`.
- Reparar la instancia (UI 500, backups, join requests): usar
  `ree-paperclip-instance-admin`.
- Configurar providers LiteLLM: `litellm-azure-foundry-config`.

## How to Run

Trabajar siempre en modo lectura primero (`--json`). No mutar secrets, config
ni runtime sin autorización explícita y evidencia reproducible.

Requisitos:
1. `paperclipai` v2026.1012.0+ y acceso de lectura a `~/.paperclip/`.
2. Para diagnóstico Hermes gateway: `API_SERVER_KEY` para probes autenticados
   de solo lectura (`GET /v1/runs/<id>`). No crear runs como parte del
   diagnóstico.
3. Para OpenCode: acceso al host donde corre `opencode` o su daemon.
4. No copiar valores de secrets ni pegarlos en archivos versionados.

## Quick Reference

| Síntoma | Lecturas | Evidencia mínima |
|---|---|---|
| Error no clasificado | `agent runtime-state`, `agent configuration`, `issue active-run` | lastRunId, lastRunStatus, lastError, adapterConfig.model |
| ENOENT opencode.exe | `paperclipai --version`, inspeccionar `dist/vendor/.../opencode.exe` | vendor path existe o no; código que resuelve la ruta |
| 401 / auth | `agent config-revisions`, `secrets usage`, `agent configuration` | secretId en config-revision y usage |
| Run Hermes sin progreso | `agent runtime-state`, run-logs NDJSON, `session_admissions` | hermesRunId, admission rows, model en sessions |
| Model unavailable | `opencode models`, `opencode.json`, `PAPERCLIP_OPENCODE_PROVIDERS` | provider block shape, model en catálogo, cache freshness |

Las referencias técnicas están en `references/adapter-config.md` y
`references/gateway-run-diagnostics.md`.

## Procedure

### P1 — Triage inicial: clasificar la causa (5 pasos)

1. `paperclipai agent runtime-state <agentId> --json`: registrar lastRunId,
   lastRunStatus, lastError, sessionId, updatedAt.
2. `paperclipai issue active-run <issueId> --json` y `paperclipai issue runs
   <issueId> --json`.
3. `paperclipai agent configuration <agentId> --json` y `paperclipai agent
   config-revisions <agentId>`: adapterConfig.model, apiBaseUrl, referencia de
   secret.
4. `paperclipai secrets usage <secretId> --json` si existe secretId.
5. Clasificar: adapter payload, provider/model, auth, host path/ENOENT, o
   instancia (derivar a Slice 3).

Salida: clasificación provisional con IDs (agentId, runId, secretId) y
timestamps; sin mutaciones.

### P2 — Configurar OpenCode adapter para Paperclip

1. Inspeccionar `paperclipai --version`, `~/.paperclip/cli/current` y el
   paquete `@paperclipai/adapter-opencode-local` instalado.
2. Provider en `~/.config/opencode/opencode.json` bajo la clave `provider`.
   Credencial en el `.env` que consume OpenCode o en el entorno del run.
3. Si Paperclip inyecta providers: `PAPERCLIP_OPENCODE_PROVIDERS` (JSON con
   forma `provider` de OpenCode) en el entorno del servidor Paperclip.
   `{env:VAR}` se resuelve del entorno del run o del proceso servidor.
4. `adapterConfig.model` debe ser `provider/model`. Con IDs anidados
   (`litellm/azure_ai/gpt-6-luna`), solo el primer segmento es el provider.
5. `adapterConfig.command` (default `opencode`) es lo que usa test-environment;
   el execute path también atiende `PAPERCLIP_OPENCODE_COMMAND`. Un run
   correcto no prueba que el test comparta el mismo PATH.
6. `PAPERCLIP_OPENCODE_SMALL_MODEL` requerido para tareas auxiliares de
   título/resumen; si falta, OpenCode usa su default y puede fallar.
7. Solo invocar test-environment o iniciar runs con autorización.

Salida: matriz command/provider/credential/model documentada; ningún secreto
expuesto.

### P3 — Native runner ENOENT triage (opencode.exe)

1. Confirmar que la ruta incluye `@paperclipai/server/dist/vendor/.../
   opencode-ai/bin/opencode.exe` y el error es `native_session_interrupted`.
2. `paperclipai --version` y localizar instalación activa.
3. Inspeccionar el código que resuelve la ruta (`runnerd-codex-transport.js`,
   `native-session-executor.js`) y comprobar existencia del path.
4. No parchear el paquete instalado. Proponer symlink/copia o hook pre-start
   solo con aprobación; documentar que una actualización recrea el vendor tree.
5. Tras remediación autorizada, verificar el path y ejecutar prueba aprobada.

Salida: atribución al runtime nativo o adapter local respaldada por versión,
código y path.

### P4 — Diagnosticar y corregir secreto Hermes desalineado

Diagnóstico (solo lectura):
1. Confirmar 401 del run y alinear timestamps con logs Hermes.
2. `agent config-revisions <agentId>` → `afterConfig.adapterConfig.apiKey.secretId`.
3. `secrets usage <secretId>` → referencias activas; nunca leer el valor.
4. Validar endpoint: `test-environment: pass` prueba liveness, no auth de
   creación de runs. El health exporter (8645) puede responder OK mientras
   `/v1/runs` con el puerto API real (8642) devuelve 401.
5. Comparar localmente la clave efectiva con la fuente de verdad usando
   metadatos/resultado booleano, sin imprimir valores.

Remediación (solo tras autorización):
6. `paperclipai secrets rotate <secretId> --value-env <ENV_VAR>` (nunca
   `--value` en texto visible).
7. Capturar estado previo; `paperclipai agent runtime-state:reset-session <agentId>`.
8. `paperclipai agent heartbeat:invoke <agentId>` solo si se autorizó.
9. Verificar nuevo lastRunId con progreso; `errorReason` antiguo puede
   persistir hasta el próximo run exitoso — no tratarlo como fallo del fix.

Salida: discrepancia confirmada; si se autorizó corregir, nuevo run sin 401.

### P5 — Diagnosticar run Hermes gateway trabado (9 pasos)

1. `agent runtime-state <agentId> --json`: lastRunId, lastRunStatus, lastError,
   `sessionParamsJson.hermesRunId` si existe.
2. Leer `~/.paperclip/instances/<id>/data/run-logs/<companyId>/<agentId>/
   <paperclipRunId>.ndjson`; comparar ejecución fallida vs exitosa.
3. `GET <apiBaseUrl>/v1/runs/<hermesRunId>` (autenticado, solo lectura):
   status, admission_id, output length.
4. `~/.hermes/state.db` → `session_admissions`: target_session_id, status
   (`queued|started|unknown|terminal`), owner_epoch, generation.
5. Documentar admissions huérfanas. No borrar filas, parar runs ni reiniciar
   dispatch sin backup, plan y autorización.
6. Si se autoriza nueva ejecución: verificar progreso simultáneo en Paperclip,
   Hermes y activity.
7. Si `started` sin eventos: buscar admissions duplicadas (`started` +
   `queued`/`unknown`) para el mismo target_session_id → admission-state
   corruption.
8. `sessions` para `paperclip:run:` → verificar `model`/`model_config` no
   nulos. Si son null, el adapter no está enviando model selection.
9. Inspeccionar `buildRunBody()` en `hermes-paperclip-adapter/dist/gateway/
   server/execute.js`. En builds actuales envía `input`, `instructions` y
   `session_id` opcional; si no hay campo `model`, es defecto de payload.

Salida: hipótesis con evidencia de los tres planos (Paperclip logs, Hermes
run, admissions/model).

### P6 — Triage de `Model unavailable`

1. `adapterConfig.model` debe ser `provider/model`. IDs anidados:
   `litellm/azure_ai/gpt-6-luna` → provider=`litellm`.
2. `opencode.json`: provider bajo `provider`, `models` contiene el ID exacto.
   Si Paperclip inyecta, verificar `PAPERCLIP_OPENCODE_PROVIDERS`.
3. `opencode models` como lectura. `--refresh` altera caché local; solo en
   host/contexto correcto y autorizado.
4. El adapter usa caché y refresca ante miss. `OPENCODE_ALLOW_ALL_MODELS=true`
   omite el availability probe pero **no** evita que OpenCode rechace el modelo
   en `getModel()`. No es un arreglo general.
5. Si listado y hello probe pasan pero tool calls dan 400 (ej.
   `reasoning_effort` no aceptado): compatibilidad de request/upstream, no
   auth. Para LiteLLM Reevolutiva, derivar a `litellm-azure-foundry-config`.

Salida: causa (provider shape, ID/caché, o incompatibilidad de request) con
evidencia del comando ejecutado.

## Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta |
|---|---|---|---|
| P1 — Triage inicial | Clasificación correcta | `noul` | "¿La evidencia soporta la clasificación adapter/provider/auth/instance?" |
| P2 — Configurar adapter | Piezas ubicadas | `noul` | "¿Están identificados command, provider, credencial y model con diferencias test/execute?" |
| P3 — ENOENT triage | Atribución correcta | `noul` | "¿El path y el código instalado confirman que el ENOENT es del native runner?" |
| P4 — Secret fix | Suficiencia de evidencia | `noul` | "¿El secretId aparece en config-revision y usage antes de cualquier mutación?" |
| P5 — Gateway run diag | Causa raíz identificada | `noul` | "¿Los tres planos (Paperclip logs, Hermes run, admissions/model) confirman la hipótesis?" |
| P6 — Model unavailable | Causa distinguida | `noul` | "¿La causa es provider shape, ID/caché o incompatibilidad de request?" |

Sin Jev: `[hermes-judgment]` con nivel de confianza; escalar mutaciones al
usuario.

## Pitfalls

- `test-environment: pass` es liveness, no auth. Siempre verificar endpoint
  efectivo y probar con el mismo bearer token.
- `adapterConfig.apiBaseUrl` apuntando al health exporter (8645) da health OK
  mientras `POST /v1/runs` al puerto API real (8642) devuelve 401.
- La clave `provider` en `opencode.json` debe ser exactamente `provider`. Un
  wrapper (`{"LiteLLM": {...}}`) se ignora silenciosamente.
- `OPENCODE_ALLOW_ALL_MODELS=true` omite el probe pero OpenCode igual rechaza
  modelos que no están en su `getModel()`. No es un fix universal.
- `PAPERCLIP_OPENCODE_PROVIDERS` con `{env:VAR}` se resuelve del entorno del
  servidor Paperclip, no del cliente que diagnostica.
- Model IDs con `/` anidados parsean correctamente: `litellm/azure_ai/gpt-6-luna`
  → provider=`litellm`, model=`azure_ai/gpt-6-luna`.
- Sin `PAPERCLIP_OPENCODE_SMALL_MODEL`, OpenCode falla en tareas auxiliares
  (session titles) y aborta runs.
- El test path usa `adapterConfig.command`; el execute path también atiende
  `PAPERCLIP_OPENCODE_COMMAND`. Run verde ≠ test verde.
- `opencode serve --service` daemon ignora `XDG_CONFIG_HOME` del cliente. Usar
  `opencode service set env` o `~/.config/opencode/.env` + `service restart`.
- `dotenv`-loaded vars no aparecen en `/proc/<pid>/environ`. Verificar
  funcionalmente, nunca concluir desde `/proc`.
- `runtime-state:reset-session` limpia `lastError`/`sessionId` pero
  `errorReason` persiste hasta el próximo run exitoso.
- Gateway model compatibility: hello probe puede pasar mientras tool calls
  reales dan 400. No asumir auth cuando listing ya pasa.
- `hermes_gateway` no implementa skill sync (`supported=false`). Un agente
  gateway recibe cero company skills.
- No rotar secrets sin confirmar `secretId` en `config-revisions` y `usage`.
- No limpiar admissions ni reiniciar dispatch sin backup y autorización.
- El vendor path de `opencode.exe` se recrea en cada update de Paperclip.
  Automatizar el puente con un script pre-start.

## Verification

1. P1: clasificación con IDs y timestamps; sin mutaciones.
2. P2: matriz command/provider/credential/model documentada; ningún secreto
   visible.
3. P3: vendor path confirmado con versión y código fuente.
4. P4: nuevo `lastRunId` con progresión post-rotación; o discrepancia
   documentada sin rotar.
5. P5: hipótesis con evidencia de logs NDJSON, `/v1/runs` y admissions.
6. P6: `opencode models` lista el modelo o se documenta por qué no.
7. Mutaciones solo con autorización explícita y confirmación post-cambio.

## References

- `references/adapter-config.md` — provider shape, env vars, secretId trace,
  model id rules
- `references/gateway-run-diagnostics.md` — correlación run IDs, logs NDJSON,
  admissions, API probes