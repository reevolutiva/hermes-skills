# Design Spec — Slice 2: `ree-paperclip-adapter-diagnosis`

## 1. Alcance

Crear la skill corporativa `ree-paperclip-adapter-diagnosis` en
`skills/ree-paperclip-adapter-diagnosis/SKILL.md`. Responsabilidad: diagnosticar
y remediar de forma segura los adapters que sirven a Paperclip — OpenCode
(`opencode_local`), LiteLLM (como gateway de modelos) y Hermes gateway
(`hermes_gateway`).

Todo el conocimiento proviene de:
- `paperclip-opencode-litellm` (249 líneas, skill fuente)
- Código fuente instalado de los adapters (`adapter-opencode-local/dist/`,
  `hermes-paperclip-adapter/dist/gateway/`)
- CLI `paperclipai` v2026.1012.0 verificado
- `ree-paperclip-board-ops` (skill ya canonizada, Slice 1)

## 2. Responsabilidad única

Diagnosticar y remediar de forma segura la capa de adapters y gateways de
Paperclip: configuración de provider/modelo, autenticación gateway, triage de
errores de runtime nativo, y troubleshooting de runs que no progresan por causa
de adapter (no por causa de instancia ni por causa de board).

NO cubre:
- Operación diaria del board (→ `ree-paperclip-board-ops`)
- Administración de la instancia Paperclip (→ `ree-paperclip-instance-admin`,
  Slice 3)
- Método completo intake→handoff→verificación (→ `ree-hermes-paperclip-method`)
- Configuración de providers/modelos LiteLLM (→ `litellm-azure-foundry-config`)

## 3. Clasificación de la skill fuente (Fase 2a entregable)

Cada sección de `paperclip-opencode-litellm` (249 líneas) se clasifica en uno de
tres destinos:

### → Slice 2: ree-paperclip-adapter-diagnosis

| Líneas fuente | Sección | Razón |
|---|---|---|
| 25-49 | "Where each piece goes" + "Native runner opencode.exe ENOENT triage" | Configuración de provider, paths de adapter, triage de runtime nativo |
| 50-63 | "Rules learned the hard way" | Provider shape, model ids, PAPERCLIP_OPENCODE_PROVIDERS, SMALL_MODEL, PATH del adapter, systemd drop-in |
| 64-71 | "Gateway authentication sanity checks" | Diagnóstico de auth entre adapter y gateway: health vs /v1/runs, secret drift, 401 |
| 72-95 | "Fixing a misaligned gateway secret" | Procedimiento completo de rotación + reset + heartbeat |
| 96-101 | "OpenCode background service gotchas" | Configuración del daemon opencode serve, env inheritance |
| 102-113 | "Verification (do this, don't guess)" | Test-environment endpoint, opencode models |
| 114-137 | "Hermes gateway run diagnostics (hermes_gateway adapter)" | 9 pasos de diagnóstico de runs trabados en gateway |
| 231-237 | "Creating and testing gateway agents" | Creación de agentes gateway, test-environment |
| 244-248 | "Gateway model compatibility" | Compatibilidad de modelos con gateway |
| ref | `references/paperclip-cli.md` § adapter commands | Comandos de adapter (agent configuration, config-revisions, heartbeat:invoke, runtime-state:reset-session) |

### → Slice 1: ree-paperclip-board-ops (ya extraído)

| Líneas fuente | Sección |
|---|---|
| 138-159 | "Delegating work to an agent (board ops)" |
| 161-173 | "Driving a long-running issue to completion (steering loop)" |
| 175-186 | "Reviewing and merging an agent's PR" |
| ref | `references/delegation-and-org-model.md` |
| ref | `references/paperclip-cli.md` § board commands |

### → Slice 3: ree-paperclip-instance-admin

| Líneas fuente | Sección | Razón |
|---|---|---|
| 188-189 | "Instance health: UI 500 while the API is healthy" | Reparación de instancia (payload UI) |
| 192-198 | "Deployment mode awareness" | Configuración de modos de despliegue |
| 200-213 | "Agent join-request approval and the no active CEO error" | Admin de compañía/agentes |
| 215-224 | "Disposition contract" | Mecánica de handoff que es parte del runtime Paperclip |
| 226-229 | "Monitoring Paperclip from a Hermes cron job" | Monitoreo de instancia |
| 238-242 | "Skills home: one owner per name" | Gestión de skills home (directorio host-wide) |
| ref | `references/instance-repair.md` | Reparación de instancia |
| ref | `references/skills-and-instructions.md` | Gestión de skills |

## 4. Estructura canónica (patrón Reevolutiva)

```
---                              ← frontmatter YAML
## When to Use                   ← triggers + no usar
## How to Run                    ← requisitos, contexto, flags y límites de seguridad
## Quick Reference               ← tabla de síntoma, lecturas y evidencia
## Procedure                     ← 6 procedimientos acotados
### P1 — Triage inicial: clasificar la causa (5 pasos)
### P2 — Configurar OpenCode adapter para Paperclip
### P3 — Native runner ENOENT triage (opencode.exe)
### P4 — Diagnosticar y corregir secreto Hermes desalineado
### P5 — Diagnosticar run Hermes gateway trabado (9 pasos)
### P6 — Triage de `Model unavailable`
## Jev Integration Points        ← 6 gates noul/choice
## Pitfalls                      ← bullets, una trampa por bullet
## Verification                  ← evidencia comprobable por procedimiento
```

## 5. Procedimientos principales

### P1 — Triage inicial: clasificar la causa (5 pasos)

Objetivo: En cinco lecturas, clasificar si el problema es adapter payload,
provider/model, auth, host path o instancia. Sin mutaciones.

Comandos:
1. `paperclipai agent runtime-state <agentId> --json` → lastRunId, lastRunStatus, lastError, sessionId, updatedAt.
2. `paperclipai issue active-run <issueId> --json` y `paperclipai issue runs <issueId> --json`.
3. `paperclipai agent configuration <agentId> --json` y `paperclipai agent config-revisions <agentId>` → adapterConfig.model, apiBaseUrl, referencia de secret.
4. `paperclipai secrets usage <secretId> --json` si existe secretId.
5. Clasificar: adapter payload, provider/model, auth, host path/ENOENT, o instancia (UI 500 con API saludable → derivar a Slice 3).

Criterio de salida: clasificación provisional con IDs (agentId, runId, secretId) y timestamps; no se muta.

### P2 — Configurar OpenCode adapter para Paperclip

Objetivo: Definir dónde reside cada pieza y validar de forma segura que Paperclip
pueda resolver comando, provider, credenciales y modelo. La configuración efectiva
varía por versión; inspeccionar primero el paquete instalado.

1. Inspeccionar `paperclipai --version`, el target de `~/.paperclip/cli/current` y el paquete `@paperclipai/adapter-opencode-local` instalado.
2. Separar configuración: provider OpenCode en `~/.config/opencode/opencode.json` bajo la clave superior `provider`; credencial del provider en el `.env` que consume OpenCode o en el entorno efectivo del run.
3. Para providers inyectados por Paperclip, revisar `PAPERCLIP_OPENCODE_PROVIDERS` como JSON con la forma `provider` de OpenCode en el entorno del servidor Paperclip; `{env:VAR}` se resuelve del entorno del run o del proceso servidor, no es una lectura de secreto desde el cliente.
4. Verificar que `adapterConfig.model` sea `provider/model`; con IDs anidados, solo el primer segmento es el provider y el resto el model ID.
5. Revisar `adapterConfig.command` y `cwd`. La UI/test-environment usa `command` (default `opencode`); el execute path también puede atender `PAPERCLIP_OPENCODE_COMMAND`, por lo que un run correcto no demuestra que el test comparta el mismo PATH.
6. Revisar `PAPERCLIP_OPENCODE_SMALL_MODEL` si fallan tareas auxiliares de título/resumen.
7. La prueba del adapter es activa: solo invocar test-environment o iniciar un run con autorización, pues puede lanzar procesos y tráfico hacia el provider.

Criterio de salida: matriz command/provider/credential/model y diferencias entre test y execute documentadas; ningún secreto expuesto y ningún cambio persistente sin aprobación.

### P3 — Native runner ENOENT triage (opencode.exe)

Objetivo: Determinar si el ENOENT pertenece al empaquetado del native runner o
a `opencode_local`, antes de proponer un puente local.

1. Confirmar que la ruta fallida incluye `@paperclipai/server/dist/vendor/node_modules/opencode-ai/bin/opencode.exe` y que el error es `native_session_interrupted`.
2. `paperclipai --version` y localizar la instalación activa.
3. Inspeccionar el código instalado que resuelve la ruta (`runnerd-codex-transport.js` y `native-session-executor.js`) y comprobar existencia del path exacto.
4. No parchear el paquete instalado como diagnóstico. Proponer symlink/copia o hook pre-start solo con aprobación explícita, documentando que una actualización puede recrear el vendor tree.
5. Tras remediación autorizada, verificar el path y ejecutar el procedimiento de prueba aprobado.

Criterio de salida: atribución al runtime nativo o adapter local respaldada por versión, código y path; remedio persistente no aplicado implícitamente.

### P4 — Diagnosticar y corregir secreto Hermes desalineado

Objetivo: Confirmar discrepancia entre la clave live del gateway y la referencia
Paperclip. La rotación es una mutación con gate explícito.

Diagnóstico de solo lectura:
1. Confirmar 401 del run y alinear timestamps con logs Hermes de `POST /v1/runs`.
2. `agent config-revisions <agentId>` → localizar `afterConfig.adapterConfig.apiKey.secretId` (o el campo de referencia equivalente en la versión instalada).
3. `secrets usage <secretId>` → comprobar referencias activas; nunca leer ni imprimir el valor almacenado.
4. Validar endpoint efectivo y diferenciar API de health exporter/UI; `test-environment: pass` comprueba liveness, no autenticación válida de creación de runs.
5. Comparar localmente la clave efectiva con la fuente de verdad usando metadatos/resultado booleano, sin imprimir valores; no hacer un `POST /v1/runs` que cree un run salvo aprobación explícita.

Remediación (solo tras autorización):
6. `paperclipai secrets rotate <secretId> --value-env <ENV_VAR>` con la variable inyectada de forma segura; no usar `--value` en texto visible.
7. Capturar estado previo y luego `paperclipai agent runtime-state:reset-session <agentId>`.
8. `paperclipai agent heartbeat:invoke <agentId>` solo si se autorizó ejecutar un run; comprobar que la invocación realmente inició.
9. Verificar nuevo lastRunId, progreso y eventos; un `errorReason` antiguo puede persistir hasta que haya un run exitoso.

Criterio de salida: discrepancia confirmada y registrada; si se autorizó corregirla, nuevo run muestra progreso sin 401. Sin autorización, detenerse antes de rotar/resetear/invocar.

### P5 — Diagnosticar run Hermes gateway trabado (9 pasos)

Objetivo: Distinguir admission-state corruption, payload del adapter, problema de
modelo o auth, correlacionando Paperclip, Hermes y timestamps. No limpiar estado
ni detener runs como parte del diagnóstico.

1. `paperclipai agent runtime-state <agentId> --json`: registrar lastRunId, lastRunStatus, lastError y `sessionParamsJson.hermesRunId` si existe.
2. Leer `~/.paperclip/instances/<instanceId>/data/run-logs/<companyId>/<agentId>/<paperclipRunId>.ndjson`; comparar una ejecución fallida con una exitosa.
3. Consultar `GET <apiBaseUrl>/v1/runs/<hermesRunId>` con credencial segura; registrar status, admission_id y longitud/output disponible, nunca el token ni contenido sensible.
4. Inspeccionar `~/.hermes/state.db` en modo de solo lectura: `session_admissions`, correlacionando target_session_id, status, owner_epoch y generation.
5. Documentar admissions antiguas/orphaned. No borrar filas, parar runs ni reiniciar dispatch sin backup, plan y autorización.
6. Si se autoriza una nueva ejecución, registrar IDs nuevos y verificar progreso simultáneo en Paperclip, Hermes y activity; no invocar como parte del diagnóstico pasivo.
7. Si Hermes está `started` sin eventos, buscar admissions duplicadas (`started` más `queued`/`unknown`) para el mismo target_session_id.
8. Correlacionar filas `sessions` de `paperclip:run:` y verificar `model`/`model_config` no nulos.
9. Inspeccionar `buildRunBody()` del adapter instalado en `hermes-paperclip-adapter/dist/gateway/server/execute.js`; comparar campos enviados con el contrato Hermes de la versión desplegada. Si falta model, clasificar como defecto de payload; no inferirlo solo por versión.

Criterio de salida: hipótesis/causa con evidencia de los tres planos (Paperclip logs, Hermes run, admissions/model) y remediación propuesta separada de acciones ejecutadas.

### P6 — Triage de `Model unavailable`

Objetivo: Distinguir ID/provider mal configurado, catálogo cacheado y modelo
incompatible con la forma de request.

1. Leer `adapterConfig.model`; debe ser `provider/model`. Para `litellm/azure_ai/gpt-6-luna`, provider=`litellm` y model ID=`azure_ai/gpt-6-luna`.
2. Confirmar que `opencode.json` define el provider bajo `provider` y su `models` contiene el ID exacto; revisar también `PAPERCLIP_OPENCODE_PROVIDERS` si Paperclip inyecta provider config.
3. Ejecutar `opencode models` como lectura. `opencode models --refresh` altera la caché local del CLI; usarlo solo en el host/contexto correcto y autorizado.
4. El adapter consulta una lista cacheada y refresca ante miss; `OPENCODE_ALLOW_ALL_MODELS=true` puede omitir el availability probe, pero no evita que OpenCode rechace el modelo al resolverlo (`getModel()`). No presentar el flag como arreglo general.
5. Si listado y hello probe pasan pero llamadas con herramientas responden 400 (p. ej. `reasoning_effort` no aceptado), clasificar compatibilidad de request/upstream, no auth. Para LiteLLM Reevolutiva, derivar ajuste de router/deployment a `litellm-azure-foundry-config`.

Criterio de salida: causa confirmada como provider shape, ID/cache o incompatibilidad de request, con comando/resultado registrado y sin cambio permanente implícito.

## 6. Conocimiento técnico a incorporar de la fuente

Estas reglas de `paperclip-opencode-litellm` § "Rules learned the hard way" y
adyacentes deben estar en la skill (ya parcialmente en el borrador actual):

| Regla | Ya en borrador | Destino en skill |
|---|---|---|
| Provider block debe ser key `provider`, no wrapper personalizado | No | P5 / Pitfalls |
| `OPENCODE_ALLOW_ALL_MODELS=true` skips probe pero no bypassa `getModel()` | No | P5 / Pitfalls |
| `PAPERCLIP_OPENCODE_PROVIDERS` soporta `{env:VAR}` placeholders | No | P5 / How to Run |
| Model ids con `/` anidados (e.g. `litellm/azure_ai/gpt-6-luna`) parsean provider=leftmost | No | P5 |
| `PAPERCLIP_OPENCODE_SMALL_MODEL` requerido para session titles | No | P5 / Pitfalls |
| Test path ignora `PAPERCLIP_OPENCODE_COMMAND`; execute path lo honra | No | P2 / Pitfalls |
| Systemd drop-in para PATH del adapter (`10-path.conf`) | No | P2 / How to Run |
| `paperclipai service restart` es hot restart; preserva runs activos | No | Pitfalls (cross-ref Slice 3) |
| `dotenv`-loaded vars no aparecen en `/proc/<pid>/environ` | No | Pitfalls |
| `opencode serve --service` daemon ignora XDG_CONFIG_HOME del cliente | No | P5 / Pitfalls |
| Gateway model compatibility: hello probe puede pasar mientras tool calls 400s | No | P5 / Pitfalls |
| `hermes_gateway` no implementa skill sync (`supported=false`) | No | P4 (nota en step 1) |

## 7. Referencias

| Referencia | Contenido | Estado actual |
|---|---|---|
| `references/adapter-config.md` | Provider shape, env vars, secretId trace, model id rules | Borrador (31 líneas) — necesita expandir con reglas de la fuente |
| `references/gateway-run-diagnostics.md` | Correlación run IDs, logs NDJSON, admissions, API probes | Borrador (23 líneas) — necesita expandir con los 9 pasos + código real |

## 8. Límites con otras skills

| Situación | Skill correcta |
|---|---|
| "El run no avanza y el error es `Model unavailable`" | `ree-paperclip-adapter-diagnosis` P1+P5 |
| "El run no avanza y no hay error claro de adapter" | `ree-paperclip-board-ops` P4 → si apunta a adapter, derivar aquí |
| "La UI da 500 en todas las páginas pero /api/health OK" | `ree-paperclip-instance-admin` (Slice 3) |
| "Necesito crear un agente gateway nuevo" | `ree-paperclip-adapter-diagnosis` P3 (referencia) |
| "El agente terminó pero el issue no cambió de estado" | `ree-paperclip-board-ops` P3 (disposition contract) |

## 9. Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta |
|---|---|---|---|
| P1 — Triage inicial | Clasificación correcta | `noul` | "¿La evidencia (runId, logs, config) soporta la clasificación adapter/provider/auth/instance?" |
| P2 — Configurar adapter | Piezas ubicadas | `noul` | "¿Están identificados command, provider, credencial y model con las diferencias test/execute?" |
| P3 — ENOENT triage | Atribución correcta | `noul` | "¿El path y el código instalado confirman que el ENOENT es del native runner y no de opencode_local?" |
| P4 — Secret fix | Suficiencia de evidencia | `noul` | "¿El secretId aparece en config-revision y usage antes de cualquier mutación?" |
| P5 — Gateway run diag | Causa raíz identificada | `noul` | "¿Los tres planos (Paperclip logs, Hermes run, admissions/model) confirman la hipótesis?" |
| P6 — Model unavailable | Causa distinguida | `noul` | "¿La causa es provider shape, ID/caché o incompatibilidad de request, con evidencia del comando ejecutado?" |

## 10. Gate de diseño (Jev Score)

Niveles: `incompleto`, `minimo_viable`, `completo`, `sobreconstruido`.

Este Design Spec apunta a `completo`: seis procedimientos, clasificación explícita
de las secciones relevantes de la fuente entre los tres slices, seis Jev gates,
referencias mapeadas a entregables de Slice 2c, y límites claros con las skills
hermanas. El conocimiento técnico de la fuente está identificado y asignado a
procedimientos concretos; incorporarlo en la skill y sus referencias requiere
aprobación de este diseño y corresponde a la Fase 2c.