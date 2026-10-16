---
name: ree-hermes-paperclip-method
description: "Hermes Paperclip intake, review, aprendizaje"
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [method, paperclip, intake, delegation, verification, review, learning]
    related_skills:
      - ree-learn
      - ree-intake
      - sdlc-review
      - github-pr-workflow
---

# ree-hermes-paperclip-method — Método Hermes→Paperclip

Orquestador del ciclo completo: Hermes recibe y clarifica la solicitud, Paperclip
coordina su ejecución delegada, y Hermes verifica resultados y captura aprendizajes
reutilizables. Cubre intake, handoff, ejecución segura, revisión independiente y cierre.

## When to Use

- Ante cualquier pedido que requiera ejecución delegada a agentes Paperclip.
- "delegar esto a paperclip", "crear tarea en Paperclip", "ejecutar con agente",
  "revisar resultado de agente".
- Como paso intake→handoff cuando se detecta que el trabajo excede una sola
  respuesta de Hermes.

### Don't use for

- Tareas que Hermes puede ejecutar directamente en su propia sesión.
- Cambios en producción o hosts sin gate humano explícito (G2 del intake).
- Delegar sin haber completado el contrato de intake (S1).

## Quick Reference

| Fase | Responsable | Acción principal |
|---|---|---|
| Intake (S1) | Hermes (perfil default) | Completar contrato con 13 campos obligatorios + 1 opcional y 5 gates |
| Handoff (S2) | Hermes | Crear goal → proyecto → issue asignado en Paperclip |
| Ejecución | Agente Paperclip | Recibir issue → ejecutar → marcar in_review |
| Verificación (S3) | Hermes | Checklist de revisión + sdlc-review lenses |
| Aprendizaje | Hermes | `ree-learn` (error/aprender/actualizar) según resultado |

## Procedure

### Fase 1 — Intake (contrato Hermes)

Antes de tocar Paperclip, todo pedido se normaliza con estos campos:

| Campo | Obligatorio | Descripción |
|---|---|---|
| `outcome` | Sí | Resultado observable esperado (máximo 2 frases). |
| `context` | Sí | Proyecto, repositorio, branch, workspace, SSOT paths/URLs. |
| `scope` | Sí | Qué sí y qué no se incluye. |
| `non_goals` | Sí | Límites explícitos para evitar scope creep. |
| `requester` | Sí | Quién pide (humano o sistema). |
| `risks` | Sí | Riesgos conocidos y política de rollback. |
| `permissions` | Sí | Dónde puede escribir el agente y qué necesita aprobación humana. |
| `deliverables` | Sí | Archivos, commits, endpoints, configs esperados. |
| `acceptance_criteria` | Sí | Condiciones verificables (tests, curls, health checks). |
| `anti_regression` | Opcional | Qué no debe romperse (endpoints, CI, configs). |
| `secrets_policy` | Sí | Sin secretos en texto plano; solo AKV, env vars o referencias por nombre. |
| `owner` | Sí | Agente Paperclip responsable de la ejecución. |
| `review_policy` | Sí | Quién revisa y qué evidencia se requiere para aprobar. |
| `disposition` | Sí | Estado esperado al terminar: `in_review`, `done`, `blocked`. |

#### Gates del intake

| Gate | Condición | Falla |
|---|---|---|
| G1 — Claridad | `outcome`, `context` y `acceptance_criteria` existen y no son ambiguos. | Pedir al usuario que refine. |
| G2 — Seguridad | Cero secretos visibles; permisos y rollback explícitos. | Bloquear y pedir definición antes de crear issue. |
| G3 — Ejecutabilidad | SSOT accesible; skills/herramientas disponibles para el agente. | Marcar bloqueo y listar herramientas faltantes. |
| G4 — Delegabilidad | Agente, proyecto, company y repositorio Paperclip identificados; estado de salida definido. | No crear issue hasta resolver. |
| G5 — Testabilidad | Cada AC tiene verificación observable. | Marcar `incomplete` y pedir evidencia concreta. |

### Fase 2 — Handoff a Paperclip

Con el contrato aprobado, preparar la delegación en Paperclip:

1. **Goal company**: crear si no existe (`goal create -C <companyId> --level company --status active`).
2. **Child goals**: uno por workstream (`--level task --parent-id <companyGoalId>`), con DoD verificable en `--description`.
3. **Proyecto**: verificar que existe y está en status válido (`backlog|planned|in_progress`). Status `completed|cancelled` requiere reactivar o crear otro. Si corresponde, vincular goals con `project update <id> -C <companyId> --goal-ids <companyGoalId>,<childGoalId>`; Paperclip valida que pertenezcan a la misma company.
4. **CEO/orquestación**: comprobar que el agente CEO está sano si se espera que proponga estrategia o distribuya subtareas. Si está en `error`/`paused`, no asumir fan-out; usar asignación directa solo si el diseño aprobado lo permite o dejar bloqueado para decisión humana.
5. **Issue**: `issue create -C <companyId> --project-id <id> --assignee-agent-id <id> --title ... --description "$(cat brief.md)" --status todo --priority high --goal-id <childGoalId>`. La asignación despierta al agente en su próximo heartbeat; una issue sin assignee prepara backlog sin despertar.


#### RACI por capa

| Capa | Responsable | Actor Paperclip |
|---|---|---|
| **Intake** | Hermes (MacBook, perfil `default`) | Crear issue, goal, proyecto; no ejecuta. |
| **Orquestación** | CEO Paperclip | Despierta en heartbeat: lee goals, propone estrategia, asigna tareas a reports. |
| **Ejecución** | Agentes leaf (opencode_local o hermes_gateway) | Reciben issue asignado, ejecutan, marcan `in_review`. |
| **Verificación** | Hermes | Verifica artifacts, decide approve/request_changes/block. |

#### Reglas de handoff

- **Goals antes que issues**: el modelo de Paperclip es goal-driven.
- **Asignación = wake**: `issue create --assignee-agent-id <id>` despierta al agente en su próximo heartbeat. No llamar a `heartbeat:invoke` como sustituto.
- **Un issue por entregable**, no uno por síntoma.
- **El brief aprobado se copia al `--description`**, sin secretos.
- **Stage sin despertar**: crear issue sin `--assignee-agent-id` para preparar backlog.

### Fase 3 — Ejecución segura

#### Pre-handoff checklist

| N° | Check | Comando |
|---|---|---|
| E1 | Brief completo con todos los campos | Checklist contra esquema S1 |
| E2 | Agente asignable (status ≠ error/paused, org chain healthy) | `paperclipai agent get <id> --json` + `org get -C <companyId>` |
| E3 | Proyecto en status válido | `paperclipai project get <id> -C <companyId> --json` |
| E4 | Goal company activo con child goal(s) | `paperclipai goal list -C <companyId> --json` |
| E5 | Issue creado con assignee, goal, project y description completo | `paperclipai issue get <identifier> --json` |
| E6 | Workspace no compartido con otro agente activo | `paperclipai agent runtime-state <agentId>` |
| E7 | Skills managed en estado `installed` (no `external`) | `paperclipai skills agent list <agentId> -C <companyId>` |
| E8 | Si es hermes_gateway, apiBaseUrl accesible | `curl -sS http://<apiBaseUrl>/health` |
| E9 | `instructionsFilePath` válido; `dangerouslySkipPermissions` documentado | `paperclipai agent configuration <agentId>` |
| E10 | Agente no edita su propio instruction bundle | Verificar que el task no implica `.opencode/agents/*.md` |

#### Monitoreo durante el run (steering loop)

Cada 30 min mientras el issue está `in_progress`:

| N° | Check | Evidencia |
|---|---|---|
| D1 | Issue pasó de `todo` → `in_progress` | `paperclipai issue get <id>` |
| D2 | Lease adquirido | `paperclipai activity list -C <companyId> --agent-id <agentId>` → `environment.lease_acquired` |
| D3 | Progreso medible en artifacts | `gh pr list --repo <repo>` + `git log --oneline origin/main..<branch>` |
| D4 | Si hay ~60 min sin progreso observable, publicar una instrucción concreta en el issue; re-wake solo si el assignee está idle y la issue sigue abierta | `paperclipai issue comment <id> --body "..."`; `paperclipai agent heartbeat:invoke <agentId>` (solo bajo ambas condiciones) |
| D5 | Claims del agente coinciden con artifacts | Nunca marcar `done` sin verificación independiente |

### Fase 4 — Revisión independiente

Cuando el agente marca `in_review`, ejecutar revisión con metodología `sdlc-review`:

| N° | Check | Herramienta |
|---|---|---|
| R1 | Leer spec original + comentarios + PR/handoff | `paperclipai issue get <id> --json` + `issue comments <id>` |
| R2 | Mapear cada AC a evidencia concreta | Tabla criterio→evidencia |
| R3 | **Artifact lens (ronda 1)**: diff antes del resumen del agente | `gh pr diff <N> -R <owner>/<repo>` + `read_file` |
| R4 | **Execution lens (ronda 2)**: checkout, build, test, probes | `terminal` + `kubectl exec` (si aplica) |
| R5 | **Contract lens (ronda 3+)**: brief original + todas las `request_changes` previas | Re-leer body del issue + comentarios |
| R6 | Security scan en diff | `gh pr diff <N> -R <owner>/<repo> | grep -iE 'password\|token\|api_key\|secret\|stringData\|PRIVATE KEY'` |
| R7 | Agente no reescribió su instruction bundle sin autorización | `git show <sha> -- .opencode/agents/*.md` |
| R8 | `dangerouslySkipPermissions`: verificar que `permission:` (singular) existe y las reglas `deny` están activas | `opencode debug config` |
| R9 | Disposition contract cumplido: issue no quedó en `in_progress` tras `succeeded` | `paperclipai activity list -C <companyId> --entity-id <issueId>` |
| R10 | Todo `in_review` tiene siguiente acción/reviewer explícito; request-changes vuelve a owner sin disposición ambigua | `paperclipai issue get <id> --json` + `paperclipai issue approvals <id>` |

#### Veredictos

Los estados válidos del issue en la instancia son `backlog`, `todo`, `in_progress`, `in_review`, `done`, `blocked`, `cancelled`. `request_changes` **no es un estado**: registra la solicitud en un comentario accionable y devuelve la tarea a `todo` (o `in_progress` solo si ya tiene checkout/run activo). `in_review` requiere un reviewer/acción siguientes explícitos; no es un estado terminal por sí solo.

| Veredicto | Cuándo | Acción Paperclip |
|---|---|---|
| **Approve** | R1–R10 pasan, artifacts coherentes | `issue update <id> --status done --comment "Aprobado: <evidencia>"` |
| **Request changes** | Defectos corregibles específicos; registrar criterio incumplido, cambio esperado y owner | `paperclipai issue comment <id> --resume --body "Cambios requeridos: …; owner: <agente>"`; comprobar que el issue reabre y el assignee queda como siguiente responsable |
| **Block** | Decisión humana o dependencia externa necesaria | `issue update <id> --status blocked --comment "Bloqueado: <razón y owner del desbloqueo>"` |

### Fase 5 — Captura de aprendizaje

Tras el cierre, ejecutar `ree-learn` según el resultado:

- **Issue cerrado `done` sin incidentes**: `ree-learn aprender` si surgió un patrón nuevo digno de preservar, o `ree-learn actualizar` si el proceso reveló mejoras a una skill existente.
- **Issue con `request_changes` que requirieron corrección del agente**: `ree-learn error` si el error fue del agente y tiene fuente raíz corregible.
- **Issue bloqueado por falta de herramienta/skill**: `ree-learn aprender` para construir la capacidad faltante.
- **Issue cerrado `done` con anti-regresión**: `ree-learn actualizar` sobre la skill que casi se rompió, añadiendo el pitfall correspondiente.

Al completar el cierre y los checks de auditoría posteriores al merge, consolidar lo aprendido sin copiar dumps de sesión, MEMORY/USER ni datos profile-only. El aprendizaje hereda los mismos controles de seguridad y la ubicación profile_or_tap vs project_local debe determinarse antes de escribir.

Registrar en bitácora: issue ID, run ID, veredicto, aprendizajes capturados, skills creadas/actualizadas.

## Jev Integration Points

| Fase | Punto | Primitivo | Pregunta / Opciones |
|---|---|---|---|
| 1 — Intake | Completitud del contrato | `choice` | `proceed_all`, `proceed_with_caveats`, `incomplete` |
| 2 — Handoff | Gate de seguridad pre-delegación | `noul` | "Are all pre-handoff checks satisfied? (agent assignable, project valid, goal linked, no secrets, permissions documented)" |
| 2 — Orquestación | Selección de ruta cuando CEO está caído | `choice` | `direct_assignment_if_approved`, `blocked_for_human_decision` |
| 3 — Ejecución | Gate de evidencia suficiente | `noul` | "Does the agent's handoff provide sufficient evidence to proceed to artifact review?" |
| 4 — Verificación | Calidad del cierre | `choice` | `approve`, `request_changes`, `block` (R1–R10; aprobar solo con evidencia) |
| 5 — Aprendizaje | Decisión de acción | `choice` | `error` (corregir fuente), `aprender` (skill nueva), `actualizar` (skill existente), `nada` (sin acción) |

## Pitfalls

- **Delegar sin contrato**: si el brief no tiene los 13 campos, el agente opera sin spec y el resultado no es verificable.
- **Crear issue antes del goal**: Paperclip es goal-driven; sin goal el CEO no puede rutear el trabajo.
- **Usar `heartbeat:invoke` como trigger**: la asignación es el wake; `heartbeat:invoke` solo encola un run extra y no reemplaza el flujo normal.
- **Aceptar `done` sin verificación independiente**: un agente puede cerrar un issue cuyo fix no está mergeado o cuyo workload falla. Verificar artifacts reales.
- **Permissions en plural (`permissions:`)**: OpenCode ignora `permissions:` (lista) y solo aplica `permission:` (objeto). Verificar con `opencode debug config`.
- **`dangerouslySkipPermissions: true` sin documentar**: el agente sobreescribe cualquier `deny` de su archivo de instrucciones. Debe ser una elección consciente y documentada.
- **`in_review` necesita un camino de acción**: asignar explícitamente reviewer/approval siguiente; un run exitoso no equivale a aprobación. `request_changes` es un veredicto, no un estado Paperclip. Para pedir rework, usar `issue comment --resume` y comprobar que la issue reabre al assignee; no asignar `in_progress` desde el board ni dejarlo sin siguiente dueño.
- **No consolidar tras merge**: borrar branches locales y remotas, remover worktrees, devolver checkout a `main`, postear comment consolidado en el issue.
- **Papel de Hermes en la verificación**: Hermes no ejecuta — verifica. Si el agente necesita cambios, los pide; no los implementa.

## Verification

1. Un intake de prueba produce un contrato con los 13 campos y pasa los 5 gates.
2. `paperclipai goal list -C <companyId> --json` muestra el goal company activo y sus child goals con DoD.
3. `paperclipai issue get <identifier> --json` muestra assignee, goal, project y status `todo`/`in_progress`.
4. La checklist de revisión (R1-R10) se ejecuta y produce un veredicto con evidencia.
5. `python3 scripts/validate-skills-catalog.py` pasa (13 skills tras agregar esta).
6. Sin `TYPESAFE_API_KEY`, los gates funcionan en modo fallback `[hermes-judgment]`.
