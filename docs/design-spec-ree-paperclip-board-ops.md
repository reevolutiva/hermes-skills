# Design Spec — Slice 1: `ree-paperclip-board-ops`

## 1. Alcance

Crear la skill corporativa `ree-paperclip-board-ops` en
`skills/ree-paperclip-board-ops/SKILL.md`. Responsabilidad: operar el board de
Paperclip desde el terminal en el día a día. Delegación, seguimiento de issues
en vuelo, revisión de PRs y troubleshooting rápido de runs trabados.

Todo el conocimiento de este documento proviene del CLI instalado
(`paperclipai` v2026.1012.0), de la skill existente
`paperclip-opencode-litellm` (especialmente `references/paperclip-cli.md` y
`references/delegation-and-org-model.md`) y de la skill validada
`ree-hermes-paperclip-method`.

## 2. Responsabilidad única

Gestionar el board Paperclip desde el CLI: consultar estado global, delegar
trabajo a agentes, hacer steering de issues en vuelo, revisar PRs de agentes
y diagnosticar runs trabados.

NO cubre:
- Configuración de adapters (→ Slice 2: ree-paperclip-adapter-diagnosis)
- Administración de la instancia (→ Slice 3: ree-paperclip-instance-admin)
- Método completo intake→handoff→verificación (→ ree-hermes-paperclip-method)
- Configuración de providers/modelos LiteLLM (→ litellm-azure-foundry-config)

## 3. Estructura canónica (patrón Reevolutiva)

```
---                              ← frontmatter YAML
## When to Use                   ← triggers + don't-use
## How to Run                    ← autenticación, context, --help flags comunes
## Quick Reference               ← 4 tablas (board check, issue steering, PR review, run diag)
## Procedure                     ← 4 secciones, una por procedimiento principal
### Procedure 1 — Daily Board Check
### Procedure 2 — Issue Steering
### Procedure 3 — PR Review & Merge
### Procedure 4 — Run Diagnosis
## Jev Integration Points        ← tabla de gates (choice/noul)
## Pitfalls                      ← bullets, una trampa por bullet
## Verification                  ← bullets, cada uno comprobable
```

## 4. Procedimientos principales

### P1 — Daily Board Check (~20 pasos, 3 min)

Objetivo: Un comando por grupo para saber exactamente qué está pasando y si hay
que actuar.

Comandos:
1. `paperclipai health --json` → deploymentMode, serverVersion
2. `paperclipai whoami --json` → identidad activa
3. `paperclipai company list --json` → companies visibles
4. `paperclipai dashboard get -C <companyId> --json` → stats
5. `paperclipai agent list -C <companyId> --json` → agents, status, role
6. `paperclipai activity list -C <companyId> --agent-id <id>` para cada agente activo
7. `paperclipai issue list -C <companyId> --json` + filtro de issues abiertos
8. `paperclipai approval list -C <companyId> --json` → aprobaciones pendientes
9. `paperclipai cost summary -C <companyId> --json` → gasto del período
10. `paperclipai org get -C <companyId>` → cadena de mando

Criterio de salida: Dashboard leído, issues abiertos identificados, aprobaciones
pendientes detectadas, agentes con status ≠ running señalados.

### P2 — Issue Steering (~15 pasos, 5 min por issue activo)

Objetivo: Verificar que un issue en `in_progress` avanza, y si no, dar
instrucción concreta.

Comandos:
1. `paperclipai issue get <IDENTIFIER> --json` → status, assignee, goal
2. `paperclipai issue comments <issueId> --json` → últimos comentarios
3. `paperclipai activity list -C <companyId> --agent-id <id>` → audit trail
4. `paperclipai agent runtime-state <agentId> --json` → lastRunId, lastRunStatus
5. `gh pr list` + `gh pr diff` → evidencia de progreso real
6. Si ~60 min sin progreso: `paperclipai issue comment <issueId> --body "…"`
7. Re-wake solo si idle + issue abierto: `paperclipai agent heartbeat:invoke <agentId>`

Criterio de salida: Issue con progreso medible en artifacts O instrucción
concreta publicada + agente re-wakeado si corresponde.

### P3 — PR Review & Merge (~18 pasos, 5-10 min por PR)

Objetivo: Revisar un PR de agente contra los 10 checks R1-R10 de
ree-hermes-paperclip-method, decidir approve/request_changes/block, consolidar
post-merge.

Comandos:
1. `paperclipai issue get <IDENTIFIER> --json` → spec original
2. `paperclipai issue comments <issueId>` → historia completa
3. `gh pr list --repo <repo>` + `gh pr diff <N>` → diff real
4. Security scan sobre diff: `grep -iE 'password|token|api_key|secret'`
5. `gh pr view <N> --json commits` → commits del agente
6. `git show <sha> -- .opencode/agents/*.md` → ¿reescribió su instruction bundle?
7. Si approve: `paperclipai issue update <id> --status done --comment "…"`
8. Si request_changes: `paperclipai issue comment <id> --resume --body "…"`
9. Si block: `paperclipai issue update <id> --status blocked --comment "…"`
10. Post-merge: `gh pr merge <N> --squash` + limpiar branches/worktrees + `paperclipai issue comment`

Criterio de salida: PR mergeado (si approve) + issue actualizado + branches/worktrees limpios.

### P4 — Run Diagnosis (~12 pasos, 3-5 min por run trabado)

Objetivo: Diagnosticar por qué un run no avanza: ¿adapter, gateway, model,
session?

Comandos:
1. `paperclipai agent runtime-state <agentId> --json` → lastRunId, lastRunStatus, lastError, sessionId
2. `paperclipai agent configuration <agentId> --json` → adapterConfig (cwd, model, command, instructionsFilePath)
3. `paperclipai agent config-revisions <agentId>` → última revisión de config
4. `paperclipai activity list -C <companyId> --agent-id <agentId>` → buscar `environment.lease_acquired/released`
5. `paperclipai issue get <IDENTIFIER> --json` → cross-check status vs run
6. Para hermes_gateway: `curl -sS http://<apiBaseUrl>/health` y `POST /v1/runs` con API key
7. `paperclipai secrets list -C <companyId>` + `paperclipai secrets usage <secretId>` → ¿secret desalineado?
8. Si secreto roto: `paperclipai secrets rotate <secretId> --value "<key>"` + `paperclipai agent runtime-state:reset-session <agentId>`
9. `paperclipai agent heartbeat:invoke <agentId>` → verificar que el nuevo run progresa
10. `paperclipai issue runs <issueId>` → historial de runs del issue

Criterio de salida: Causa raíz identificada O remedio aplicado + run verificado con heartbeat.

## 5. Referencias extraídas de paperclip-opencode-litellm

| Sección de paperclip-opencode-litellm | Destino en este slice |
|---|---|
| `references/paperclip-cli.md` (Projects, Issues, Agents, Activity, Secrets, Follow-up loop, Verifying a delegated run) | `references/paperclip-cli-commands.md` |
| `references/delegation-and-org-model.md` (Standing requirements, Target org shape, Intended flow, Org tree rules, Goals, Delegation mechanics, Guardrails) | `references/delegation-model.md` |
| SKILL.md "Delegating work to an agent (board ops)" | Integrado en Procedure P1/P2 |
| SKILL.md "Driving a long-running issue to completion (steering loop)" | Procedure P2 |
| SKILL.md "Reviewing and merging an agent's PR" | Procedure P3 |
| SKILL.md "Hermes gateway run diagnostics" (parcial — solo la parte de board ops, no adapter) | Procedure P4 |
| SKILL.md "Gateway authentication sanity checks" (solo verify desde el board) | Procedure P4 |
| SKILL.md "Disposition contract" | Pitfalls |
| SKILL.md "Skills home: one owner per name" | Pitfalls |

## 6. Secciones de paperclip-opencode-litellm que quedan FUERA de este slice (van a Slice 2 o 3)

| Sección | Destino |
|---|---|
| "Where each piece goes" (provider config) | Slice 2 |
| "Native runner opencode.exe ENOENT triage" | Slice 2 |
| "Rules learned the hard way" (adapter config) | Slice 2 |
| "Gateway authentication sanity checks" (configuración) | Slice 2 |
| "OpenCode background service gotchas" | Slice 2 |
| "Verification (do this, don't guess)" (adapter-side) | Slice 2 |
| "Creating and testing gateway agents" | Slice 2 o 3 |
| "Gateway model compatibility" | Slice 2 |
| "Instance health: UI 500 while the API is healthy" | Slice 3 |
| "Deployment mode awareness" | Slice 3 |
| "Agent join-request approval and the no active CEO error" | Slice 3 |
| "Monitoring Paperclip from a Hermes cron job" | Slice 3 |
| "references/instance-repair.md" | Slice 3 |
| "references/skills-and-instructions.md" | Slice 3 |

## 7. Inventario CLI agrupado por caso de uso (Fase 1a deliverable)

### Grupo A — Board Check Diario (P1)
- `health`, `whoami`, `dashboard get`, `cost summary`, `company get`
- `agent list`, `activity list`, `issue list`, `approval list`
- `org get`

### Grupo B — Operaciones de Issue (P2 steering + P3 review)
- `issue get`, `issue update`, `issue comment`, `issue comments`
- `issue list`, `issue create`, `issue runs`, `issue live-runs`, `issue active-run`
- `issue force-release`, `issue approvals`
- `issue heartbeat-context`, `issue work-products`

### Grupo C — Operaciones de Agente (P2/P4)
- `agent get`, `agent list`, `agent update`, `agent pause`, `agent resume`
- `agent runtime-state`, `agent runtime-state:reset-session`
- `agent heartbeat:invoke`, `agent configuration`, `agent config-revisions`
- `agent permissions:update`, `agent skills`, `agent skills:sync`

### Grupo D — Goals y Proyectos (P1/P2)
- `goal list`, `goal get`, `goal create`, `goal update`
- `project list`, `project get`, `project create`, `project update`
- `project --goal-ids`

### Grupo E — Secrets (P4)
- `secrets list`, `secrets rotate`, `secrets usage`, `secrets access-events`

### Grupo F — Aprobaciones (P1/P3)
- `approval list`, `approval get`, `approval approve`, `approval reject`, `approval request-revision`, `approval resubmit`, `approval comment`

### Grupo G — Activity y Auditoría (P2/P3/P4)
- `activity list`, `activity issue`

### Grupo H — Board & Member Admin (P1)
- `member list`, `board prompt`, `inbox`, `invite list`, `join list`

### Grupos NO cubiertos en esta skill (van a Slice 2 o 3)
- `service`, `db:backup`, `configure`, `instance`, `admin`, `channels`, `doctor`, `auth bootstrap-ceo`, `adapter`, `feedback`, `pipelines`, `routine`, `routines`, `plugin`, `worktree`, `skills`, `skill`, `teams`, `available-skill`, `env-lab`, `environment`, `workspace`, `project-workspace`, `managed-agent`, `mcp`, `openclaw`, `llm`, `token`, `sidebar`, `context`, `profile`, `asset`

## 8. Reglas de handoff entre skills

- `ree-hermes-paperclip-method` → orquesta el ciclo completo. Delega a `ree-paperclip-board-ops` para operaciones concretas de board.
- `ree-paperclip-board-ops` → operaciones diarias. Si el diagnóstico revela problema de adapter, deriva a `ree-paperclip-adapter-diagnosis` (Slice 2). Si es problema de instancia, deriva a `ree-paperclip-instance-admin` (Slice 3).

## 9. Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta |
|---|---|---|---|
| P1 — Daily Check | Board status completo | choice | `all_clear`, `needs_attention`, `critical` |
| P2 — Issue Steering | Progreso suficiente | noul | "Has the issue made measurable progress in the last 60 minutes, with evidence in artifacts?" |
| P3 — PR Review | Calidad del veredicto | choice | `approve`, `request_changes`, `block` |
| P4 — Run Diagnosis | Causa raíz identificada | noul | "Has the root cause of the stalled run been identified with evidence from runtime-state and activity?" |

## 10. Gate de diseño (Jev Score)

Niveles: `incompleto`, `minimo_viable`, `completo`, `sobreconstruido`.

Este Design Spec apunta a `completo`: 4 procedimientos, 4 Jev gates, referencias
extraídas con adjudicación explícita, CLI inventariado y agrupado por caso de uso,
límites claros con Slice 2 y Slice 3.