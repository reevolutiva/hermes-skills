---
name: ree-paperclip-adapter-diagnosis
description: "Diagnostica adapters Paperclip (OpenCode, LiteLLM, gateway)."
version: 0.1.0
author: Hermes
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [paperclip, adapter, opencode, litellm, gateway, diagnosis]
    related_skills: [ree-paperclip-board-ops, ree-hermes-paperclip-method]
---

# ree-paperclip-adapter-diagnosis — Diagnóstico de adapters Paperclip

Usa esta skill para triage y diagnóstico de adapters y gateways que sirven a
Paperclip: OpenCode/opencode_local, proxies LiteLLM (litellm), y el Hermes
gateway. No realiza cambios de instancia (restart global, backups, restores)
ni rota secretos sin autorización humana explícita.

## When to Use

- Un run queda `stalled` / `queued` sin progresar y `agent runtime-state` muestra
  errores relacionados con `Model unavailable`, `Command not found` o `401`.
- La UI muestra errores del adapter (model list vacío, `Command not found in PATH`).
- El adapter reporta `gateway_auth_failed` o un token parece desalineado.
- Quieres trazar si la causa es: adapter payload, provider/model, gateway auth,
  o la propia instancia Paperclip.

### No usar para

- Reparaciones de base de datos o restauraciones de instancia: usar
  `ree-paperclip-instance-admin`.
- Cambiar secrets en producción sin gate humano y evidencia reproducible.

## How to Run

Siempre trabajar en modo de sólo lectura al inicio: `--json` en las lecturas.
Evita mutaciones hasta tener evidencia (run IDs, logs, timestamps). Requisitos:

1. Acceso CLI con `paperclipai` (v2026.1012.0 comprobado aquí) y `curl` para
   probes HTTP cuando haga falta.
2. Un token `API_SERVER_KEY` o board token para probes Hermes (`POST /v1/runs`).
3. Acceso a los directorios de la instancia Paperclip donde se guardan run-logs
   (ej. `~/.paperclip/instances/default/data/run-logs/...`) cuando se diagnostica
   localmente.
4. No copies valores de secrets ni los pegues en ficheros versionados.

## Quick Reference

| Necesidad | Comandos | Evidencia mínima |
|---|---:|---|
| Confirmar causa básica | `agent runtime-state`, `agent configuration`, `issue active-run`, `issue runs` | lastRunId, lastRunStatus, lastError, adapterConfig.model |
| Gateway auth probe | `curl POST /v1/runs` con API key de prueba | 401 vs payload error (400) |
| Secrets uso/rotación | `paperclipai secrets usage <secretId>`, `secrets rotate <secretId>` | referencia de secretId en agent config revisions |
| Native ENOENT triage | inspeccionar `dist/vendor/.../opencode.exe`, `paperclipai --version` | vendor path existe o no |
| Adapter config history | `agent config-revisions <agentId>` | revision con afterConfig → adapterConfig.secretId |

Las referencias técnicas detalladas están en `references/adapter-config.md` y
`references/gateway-run-diagnostics.md`.

## Procedure

### 1. Triage inicial: clasificar la causa (5 pasos)

1. `paperclipai agent runtime-state <agentId> --json`: anotar `lastRunId`,
   `lastRunStatus`, `lastError`, `sessionId` y `updatedAt`.
2. `paperclipai issue active-run <issueId> --json` y `paperclipai issue runs <issueId> --json`:
   confirmar si la issue tiene run asociado y su historial.
3. `paperclipai agent configuration <agentId> --json` y `paperclipai agent config-revisions <agentId>`:
   buscar `adapterConfig.model`, `adapterConfig.apiBaseUrl`, y `afterConfig.adapterConfig.apiKey.secretId`.
4. `paperclipai secrets usage <secretId> --json` (si hay secretId) para ver referencias.
5. Clasificar: adapter payload (missing model/command), provider/model (Model unavailable),
   auth (401), host path/ENOENT (opencode.exe) o instancia (UI 500 pero API OK).

Salida: clasificación provisional y lista de IDs (agentId, runId, secretId, timestamps).

### 2. Native runner ENOENT triage (opencode.exe) — cuando aparece ENOENT

1. Confirma la ruta que falla en el error (`dist/vendor/.../opencode-ai/bin/opencode.exe`).
2. `paperclipai --version` y localizar ruta de install: `~/.paperclip/cli/current` o `~/.paperclip/cli/installs/npm/<ver>/node_modules/@paperclipai/`.
3. Verifica si el vendor path existe en la instalación activa. Si falta, crear puente:
   - Crear un script/symlink en un lugar persistente que apunte al binario opencode disponible,
     y documentarlo (no lo apliques en producción sin aprobación).
4. Alternativa segura: automatizar el puente en un script invoked pre-start (documentar).
5. Re-ejecutar el run de prueba o invocar `agent heartbeat:invoke <agentId>` en modo de comprobación.

Salida: `opencode` resolvible por la ruta esperada o evidencia que la ENOENT viene de layout vendor reconstruido.

### 3. Misaligned gateway secret (401) — fijado por rotation + reset

1. Confirmar 401 → `paperclipai agent runtime-state` y revisar timestamps coincidentes.
2. Identificar `secretId` de la config: revisar `agent config-revisions <agentId>` y buscar `afterConfig.adapterConfig.apiKey.secretId`.
3. Validar que el `secretId` es el que usa el adapter: `paperclipai secrets usage <secretId>`.
4. Si confirmado y tienes autorización de negocio:
   - `paperclipai secrets rotate <secretId> --value-env <ENV_VAR_CONTAINING_KEY>` (evita poner el valor en la shell y no lo guardes en ficheros)
   - `paperclipai agent runtime-state:reset-session <agentId>` — captura logs antes de reset.
   - `paperclipai agent heartbeat:invoke <agentId>` y seguir `agent runtime-state` hasta que reporte progreso.
5. No declares recuperación hasta que aparezca un nuevo `lastRunId` con progresión y actividad asociada.

Salida: secret rotado (si autorizado), nueva sesión del agente y run exitoso comprobado.

### 4. Hermes gateway run diagnostics (hermes_gateway adapter)

1. `paperclipai agent runtime-state <agentId> --json` → localizar `sessionParamsJson.hermesRunId` o `lastRunId`.
2. Buscar logs locales: `~/.paperclip/instances/default/data/run-logs/<companyId>/<agentId>/<paperclipRunId>.ndjson` — comparar una ejecución fallida y una exitosa.
3. Consultar Hermes `/v1/runs/<hermesRunId>` con `API_SERVER_KEY` (hacer una petición autenticada de lectura) y capturar `status`, `admission_id`, `output`.
4. Inspeccionar admissions en Hermes (`~/.hermes/state.db` `session_admissions`) para ver filas `queued|started|unknown` que colisionen con el mismo `target_session_id`.
5. Si hay admissions huérfanas, documentar y limpiar solo las filas huérfanas tras discusión: no ejecutar borrados hasta acordado. La remediación segura habitual es reiniciar la parte de dispatch o limpiar admissions antiguas bajo control.
6. Re-run y verificar tres señales: nuevo `lastRunId`, Hermes `/v1/runs` muestra progresión, y actividad nueva en `activity list` para el issue.

Salida: causa triada — admission-state corruption, adapter payload sin model, o gateway auth — y evidencia por timestamps/ids.

### 5. OpenCode / provider / model availability checks

1. Verificar `adapterConfig.model` formato: `provider/model` (contiene `/`).
2. En el host de OpenCode: `opencode models --refresh` y `opencode models | grep '^<provider>/'` (solo si tienes acceso host).
3. Confirmar provider block en `~/.config/opencode/opencode.json` y que `models` map incluya el model.
4. Si la UI list no muestra modelos pero `opencode models --refresh` sí los devuelve, documentar desync y aplicar `OPENCODE_ALLOW_ALL_MODELS=true` en pruebas solo si autorizado; prefer registrar el fallo y arreglar la fuente.

Salida: modelo disponible/indisponible y pasos seguros de mitigación.

## Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta |
|---|---:|---|---|
| Triage inicial | Clasificación correcta | noul | "¿La evidencia (runId, logs, config) soporta la clasificación adapter/provider/auth/instance?" |
| ENOENT triage | Sustitución segura | noul | "¿Existe un puente reproducible que no cambia el install upstream?" |
| Secret misaligned | Suficiencia de evidencia | noul | "¿El secretId aparece en config-revision y usage antes de rotar?" |
| Gateway run diag | Causa raíz identificada | noul | "¿Los run logs + admissions + Hermes run confirman la causa raíz?" |

Si Jev no está disponible, registra `[hermes-judgment]` con nivel de confianza y pide autorización humana para mutaciones.

## Pitfalls

- Rotar un secret sin confirmar `secretId` puede romper más agentes: siempre confirmar con `config-revisions` y `secrets usage`.
- `opencode.exe` ENOENT a menudo es un layout vendor cambiado por actualización — un puente local puede funcionar pero se pierde en la próxima actualización.
- `adapterConfig.apiBaseUrl` apuntando al health exporter (puerto 8645) puede devolver `health OK` mientras `POST /v1/runs` 401s o 400s.
- `opencode_local` legacy no infiere disposition; los runs pueden terminar `succeeded` sin cambiar issue state.
- No rotes secretos ni edites config de adapters sin gate humano y backup de la referencia del secret.

## Verification

1. Para ENOENT: `paperclipai --version` + existencia de la ruta vendor o ejecución de run de prueba.
2. Para secret fix: nuevo `lastRunId` con progresión + `activity` que muestre `environment.lease_acquired` y `issue` avance.
3. Para gateway diag: Hermes `/v1/runs` muestra eventos; `~/.paperclip/instances/default/data/run-logs` tiene nuevos eventos para el run.
4. Para model availability: `opencode models --refresh` y `opencode models` listan el provider/model o la evidencia de por qué no.

## References

- `references/adapter-config.md` — provider shape, env vars y guardarraíles
- `references/gateway-run-diagnostics.md` — pasos para correlacionar run IDs, logs y admissions

