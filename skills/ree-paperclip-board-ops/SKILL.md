---
name: ree-paperclip-board-ops
description: "Gestiona el board Paperclip con procedimientos CLI."
version: 0.1.0
author: Hermes
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [paperclip, board, issues, agents, review, cli]
    related_skills: [ree-hermes-paperclip-method]
---

# ree-paperclip-board-ops — Operación diaria del board Paperclip

Usa esta skill para inspeccionar el board, seguir issues activos, revisar entregas de agentes y diagnosticar runs sin progreso. No reemplaza la metodología intake→handoff de `ree-hermes-paperclip-method`, la configuración de adapters ni la administración de la instancia.

## When to Use

- Revisar el estado diario de una compañía Paperclip y sus agentes.
- Hacer seguimiento o steering de un issue activo.
- Revisar un PR entregado por un agente y registrar el veredicto.
- Diagnosticar un run de issue que no progresa.

### No usar para

- Configurar OpenCode, LiteLLM o Hermes adapters: usar el flujo de diagnóstico de adapters cuando esté disponible.
- Cambiar configuración del servidor, reparar UI, actualizar o respaldar la instancia: requiere el procedimiento de administración de instancia.
- Crear una delegación desde cero sin intake aprobado: iniciar con `ree-hermes-paperclip-method`.

## How to Run

Ejecuta los comandos mediante `terminal`. Antes de leer o mutar datos:

1. Comprueba conectividad e identidad con `paperclipai health --json` y `paperclipai whoami --json`.
2. Confirma el `companyId` dueño de los recursos; no infieras el company por el prefijo de un issue.
3. Para comandos de compañía, pasa `-C <companyId>` explícitamente. `issue get` y varios subcomandos de issue resuelven por ID global y no aceptan `-C`.
4. Usa `--json` para inspección/procesamiento y revisa `paperclipai <grupo> --help` antes de comandos cuya sintaxis o efecto no esté documentado aquí.
5. Distingue lecturas de mutaciones. No apruebes, cierres, reabras, despiertes agentes ni fusiones PRs sin la autorización aplicable al trabajo.

Las credenciales se obtienen del contexto local autorizado. No copies tokens a comandos visibles, archivos, comentarios ni salida de terminal.

## Quick Reference

| Necesidad | Comandos principales | Evidencia mínima |
|---|---|---|
| Chequeo diario | `health`, `whoami`, `dashboard get`, `issue list`, `agent list`, `approval list`, `activity list` | Estado del servidor, issues activos, agentes, aprobaciones y eventos |
| Seguir issue | `issue get`, `issue comments`, `issue runs` / `live-runs` / `active-run`, `agent runtime-state`, `activity list` | Estado + run + actividad + artefactos externos |
| Revisar entrega | `issue get`, `issue comments`, `issue work-products`, `gh pr view`, `gh pr diff`, tests del repo | Criterio→artefacto→prueba, más disposición acordada |
| Run trabado | `issue active-run`, `issue runs`, `agent runtime-state`, `agent configuration`, `activity issue` | Correlación de issue, run, lease y progreso observable |

Referencia de sintaxis y guardarraíles: `references/paperclip-cli-commands.md`. Modelo de objetivos, árbol org y delegación: `references/delegation-model.md`.

## Procedure

### 1. Chequeo diario del board

1. Ejecuta `paperclipai health --json`; registra si la API responde y los campos de versión/modo que realmente estén presentes. No infieras la salud de la UI solo de `/health`.
2. Ejecuta `paperclipai whoami --json` y confirma si operas como board user o agente. Si no es la identidad esperada, detente antes de mutar.
3. Lista las compañías visibles con `paperclipai company list --json`; selecciona explícitamente la compañía objetivo.
4. Lee `paperclipai dashboard get -C <companyId> --json` para localizar señales que requieran inspección.
5. Lee `paperclipai issue list -C <companyId> --status in_progress,in_review,blocked --json` y `paperclipai approval list -C <companyId> --status pending --json`. Confirma los valores de estado con `--help`/respuesta real si la versión difiere.
6. Lista agentes con `paperclipai agent list -C <companyId> --json`; para los agentes relacionados con trabajo abierto, consulta `agent runtime-state` y `activity list`.
7. Inspecciona `paperclipai org get -C <companyId> --json` si hay un problema de asignación, cadena jerárquica o CEO/orquestación.
8. Consulta `paperclipai cost summary -C <companyId> --json` solo cuando presupuesto/gasto sea relevante; un chequeo diario no implica autorización para modificar presupuestos.
9. Resume hallazgos como: normal, requiere atención o bloqueado; cita identificadores y evidencia. No hagas cambios de estado durante una revisión de solo lectura.

Salida: lista trazable de issues y aprobaciones que requieren atención, agentes afectados y bloqueos; sin mutaciones implícitas.

### 2. Steering de un issue activo

1. Inspecciona `paperclipai issue get <IDENTIFIER> --json`; registra estado, assignee, proyecto, goal, blockers y timestamps relevantes.
2. Lee comentarios recientes con `paperclipai issue comments <issueId> --order desc --limit 20 --json` y ejecución con `paperclipai issue active-run <issueId> --json`, `issue live-runs` y `issue runs`.
3. Correlaciona `paperclipai agent runtime-state <agentId> --json` con `paperclipai activity list -C <companyId> --agent-id <agentId> --json` o `activity issue <issueId> --json`. La actividad de un agente no prueba por sí sola progreso de este issue.
4. Verifica progreso en artefactos del repo: PRs y diffs, commits, archivos y pruebas. No tomes un comentario o `lastRunStatus=succeeded` como DoD.
5. Si hay avance, no interrumpas: registra qué criterio avanzó y cuál falta.
6. Si está estancado (sin progreso observable durante aproximadamente 60 minutos, ajustando por la política del equipo), confirma que no haya un run activo útil. Publica una instrucción breve, accionable y verificable mediante `paperclipai issue comment <issueId> --body "…"`.
7. Usa `--resume` solo para solicitar explícitamente follow-up y despertar al assignee cuando el trabajo sea reanudable. `agent heartbeat:invoke` encola un run adicional; úsalo solo si el agente está idle, el issue sigue abierto y la asignación no produjo el wake esperado.
8. Vuelve a leer issue, actividad y artefactos después de la intervención. No cierres el issue: entrega la recomendación/veredicto a quien tenga autoridad de disposición.

Salida: evidencia de avance o bloqueo, instrucción publicada si aplicó y dueño del siguiente paso.

### 3. Revisión de PR de agente

1. Recupera el brief aprobado, criterios, comentarios y work products con `issue get`, `issue comments` y `issue work-products`.
2. Identifica el PR y su repo; inspecciona estado y diff con `gh pr view <N> --repo <owner>/<repo>` y `gh pr diff <N> --repo <owner>/<repo>`. Examina artefactos antes del resumen del agente.
3. Relaciona cada criterio de aceptación con archivos/diff y evidencia de prueba. Ejecuta tests pertinentes desde el checkout limpio/aislado del repo; no confíes solo en CI verde o en el mensaje final.
4. Revisa riesgos de seguridad y secretos sin imprimir datos sensibles. Comprueba que un agente no haya debilitado sus propias instrucciones/guardrails (`.opencode/agents/*.md`, permisos efectivos) sin aprobación.
5. Elige exactamente una salida, de acuerdo con permisos:
   - Aprobable: registra evidencia y recomienda aprobación. Mergear requiere permiso explícito; no lo infieras del estado `in_review`.
   - Cambios corregibles: deja criterio incumplido, cambio esperado y owner mediante comentario accionable. `request_changes` no es un estado de issue; `issue comment --resume` es un mecanismo de follow-up, no un veredicto universal.
   - Bloqueado: registra dependencia/decisión externa, owner del desbloqueo y condición de reanudación.
6. Tras un merge autorizado, verifica el PR merged, commit en la rama base y tests; limpia branches/worktrees solo si son propiedad del flujo y es seguro hacerlo. Actualiza el issue con evidencia y disposición acordada.
7. No declares terminado si el cambio no está mergeado cuando el DoD exige merge, o si el runtime funcional contradice el claim.

Salida: veredicto auditable criterio→evidencia, acción autorizada y estado siguiente explícito.

### 4. Diagnóstico inicial de run trabado

Este procedimiento identifica si el problema pertenece al estado Paperclip o requiere derivar al diagnóstico especializado de adapter/gateway.

1. Lee `paperclipai issue get <IDENTIFIER> --json`, `issue active-run <issueId> --json` y `issue runs <issueId> --json`.
2. Lee `paperclipai agent runtime-state <agentId> --json`; correlaciona el run más reciente con `lastRunId`, `lastRunStatus`, `lastError` y sesión. No confundas una invocación encolada con run iniciado.
3. Inspecciona `paperclipai activity issue <issueId> --json` y actividad del agente. Busca lease adquirida/liberada, comentarios, handoff requerido y timestamps correlacionados.
4. Inspecciona configuración redactada con `paperclipai agent configuration <agentId> --json` y revisiones con `agent config-revisions`. No expongas secretos ni copies valores de adapter config.
5. Comprueba si hay avance funcional en el repo/PR, y si la issue está bloqueada por dependencias o no tiene dueño activo.
6. Si no hay run activo y el issue sigue abierto, decide si corresponde un comentario `--resume` o una invocación manual; no reinicies la instancia para un problema de ejecución de un agente sin evidencia de que el servidor sea la causa.
7. Si los datos apuntan a provider, modelo, autenticación o payload del adapter, conserva los IDs/tiempos y deriva a la skill de diagnóstico de adapters cuando esté disponible. No rotes secretos ni cambies configuración como paso diagnóstico.
8. Considera un run recuperado solo cuando haya un nuevo run correlacionado, actividad progresiva y/o artefacto funcional verificable.

Salida: clasificación provisional con evidencia (estado/run, dispatch/lease, progreso funcional), acción no destructiva sugerida y derivación si corresponde.

## Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta / Opciones |
|---|---|---|---|
| Chequeo diario | Atención del board | `choice` | `all_clear`, `needs_attention`, `critical`; justificar con issues, aprobaciones y agentes observados. |
| Steering | Progreso del issue | `noul` | “Is there recent, issue-specific progress in artifacts or verifiable activity, rather than only a successful run claim?” |
| Revisión PR | Veredicto | `choice` | `approve`, `request_changes`, `block`; aprobar solo con criterios originales y evidencia independiente. |
| Run trabado | Suficiencia de diagnóstico | `noul` | “Is the stalled-run classification supported by correlated issue, run, activity and artifact evidence?” |

Sin Jev disponible, registrar `[hermes-judgment]` y nivel de confianza; escalar decisiones de riesgo o autoridad al usuario.

## Pitfalls

- Asignar un issue despierta al agente; `heartbeat:invoke` agrega otra ejecución en cola y no es el trigger normal.
- `issue get` no acepta `-C`; confirma el company owner desde el recurso/contexto antes de acciones relacionadas.
- `activity list` es un registro de auditoría, no prueba por sí solo que el agente avanzó en el artefacto del issue.
- Un run `succeeded` sin disposición del issue no significa que la tarea esté completa; comprobar el disposition contract y la actividad `issue.successful_run_handoff_required`.
- `in_review` no es un estado terminal. Debe existir reviewer y siguiente acción claros.
- `request_changes` no es un estado Paperclip; usar feedback accionable y verificar que el follow-up se asignó/despertó como se espera.
- No todo run trabado es un problema de adapter, y reiniciar Paperclip no es una solución genérica. Correlaciona estado y eventos primero.
- Un agente no debe editar su propia definición o permisos; revisar diffs de instrucciones y permisos efectivos.
- `opencode_local` puede omitir sincronización de skills según el adapter; verifica capacidad `supported` antes de tratar una skill ausente como fallo de sync.
- La API/UI pueden divergir (por ejemplo, UI 500 mientras API está sana); el diagnóstico de servidor/instalación corresponde a administración de instancia.
- Los comandos y enums cambian entre releases. Usa `paperclipai <group> --help` y verifica lecturas de regreso antes de mutar.
- Nunca imprimas secretos, cuerpos de usuario que contengan tokens, `Secret.data/stringData`, ni API keys en logs o comentarios.

## Verification

1. El chequeo diario identifica compañía, identidad, issues abiertos, aprobaciones y agentes que necesitan atención sin mutar el board.
2. Un steering se respalda con issue/run/activity y evidencia del repo, y termina en progreso probado o una instrucción accionable con siguiente owner.
3. La revisión de PR mapea cada criterio a evidencia y separa recomendación de merge/disposición autorizados.
4. El diagnóstico de run correlaciona issue, run y actividad; no declara recuperación por `health` o `lastRunStatus` únicamente.
5. Los comandos mutantes solo se ejecutan con autorización y se confirma el estado resultante con una lectura posterior.
6. Los detalles CLI y org están en `references/paperclip-cli-commands.md` y `references/delegation-model.md`.
