# Paperclip CLI: referencia operativa del board

Esta referencia cubre la superficie necesaria para chequeos del board, issues,
agentes, objetivos/proyectos, activity, approvals y trazabilidad de ejecuciones.
No es un inventario completo de todos los comandos instalados. La superficie
depende de la versión; la salida obtenida con `paperclipai <grupo> --help` en
2026.1012.0 confirma los comandos de esta sección. Revalida antes de copiar una
sintaxis a otro release.

## Contexto y autenticación

- Comprueba el servidor con `paperclipai health --json` y la identidad con
  `paperclipai whoami --json` antes de operar.
- La CLI puede autenticar como board user (`auth login`) o como agente
  (`--api-key`, `PAPERCLIP_API_KEY`). Para trabajo del board, usa identidad board;
  no pases a agent auth como arreglo genérico de un 401.
- Si un login board exitoso coincide con `401 Agent token did not verify`, revisa
  precedencia de `PAPERCLIP_API_KEY`, `PAPERCLIP_AGENT_API_KEY` y
  `PAPERCLIP_BOARD_API_KEY`; quítalas solo en el proceso de shell de prueba y
  usa `--api-base` explícito. No imprimas sus valores.
- Usa `-C/--company-id` explícito para comandos de compañía. `issue get` acepta
  UUID o identifier global y **no** tiene `-C`.
- `--json` pide salida raw estructurada en muchos comandos; confirma cada flag
  en el `--help` específico. No supongas que cada subcomando acepta JSON.
- `$P` puede usarse como alias para `paperclipai` en los ejemplos.

## Daily board check

```bash
$P health --json
$P whoami --json
$P company list --json
$P dashboard get -C <companyId> --json
$P issue list -C <companyId> --status in_progress,in_review,blocked --json
$P agent list -C <companyId> --json
$P approval list -C <companyId> --status pending --json
$P activity list -C <companyId> --entity-type issue --json
$P org get -C <companyId> --json
```

El dashboard es resumen, no stream. Para eventos y ejecución consulta `activity`,
`issue active-run`/`live-runs` y `agent runtime-state`.

## Issues

Superficie CLI verificada en este release (abreviada por intención):

```text
issue list|get|create|update|delete
issue comment|comments|comment:get|comment:delete
issue approvals|approval:link|approval:unlink
issue heartbeat-context|runs|live-runs|active-run|recovery-actions|recovery:resolve
issue child:create|checkout|release|force-release
issue work-products|work-product:create|work-product:update|work-product:delete
issue documents|document:get|document:put|document:delete|document:lock|document:unlock
issue document:revisions|document:restore
issue interactions|interaction:create|interaction:accept|interaction:reject
issue interaction:cancel|interaction:respond
issue tree-state|tree-preview|tree-holds|tree-hold:create|tree-hold:get|tree-hold:release
issue attachments|attachment:upload|attachment:download|attachment:delete
issue label:list|label:create|label:delete
issue feedback:votes|feedback:vote|feedback:list|feedback:export
issue read|unread|archive|unarchive
```

Uso típico:

- Filtrar abiertos: `issue list -C <companyId> --status in_progress,in_review,blocked --json`.
- Leer: `issue get <id|IDENTIFIER> --json`; no hay `-C`.
- Leer comentarios: `issue comments <id> --order desc --limit 20 --json`.
- Pedir seguimiento y wake si reanudable: `issue comment <id> --body "…" --resume`.
- Reabrir terminado: `issue comment <id> --body "…" --reopen`.
- Los tres comandos de runs muestran historial, runs queued/running y el run
  activo; pueden recibir ID o identifier.
- `issue force-release` es herramienta de recuperación para checkout atascado,
  no comando normal de steering. Reúne evidencia y permiso antes de usarlo.
- Work products, documents, interactions, attachments y tree holds son recursos
  distintos; no uses una mutación si solo querías revisar el hilo.

## Agents y ejecución

```text
agent me|inbox|inbox-mine|list|get|create|hire|update|delete
agent pause|resume|approve|terminate|wake|heartbeat:invoke|prompt|local-cli
agent configuration|config-revisions|config-revision:get|config-revision:rollback
agent runtime-state|runtime-state:reset-session|task-sessions
agent permissions:update|skills|skills:sync|instructions-path:update
agent instructions-bundle|instructions-bundle:update
agent instructions-file:get|instructions-file:put|instructions-file:delete
```

Lecturas clave:

- `agent runtime-state <agentId> --json`: último run, status/error/sesión según
  el runtime. Correlaciona con runs de issue y eventos.
- `agent configuration <agentId> --json`: configuración redactada; revisa cwd,
  model, command e instructions path. La redacción no reemplaza inspección segura.
- `agent config-revisions <agentId>` y `config-revision:get`: historial auditable.
- `agent task-sessions` separa sesiones por tarea.
- `agent skills`/`skills:sync` operan desired/runtime skills; `supported=false`
  puede significar que el adapter no implementa sync, no una falla transitoria.
- Asignar issue es el wake habitual. `heartbeat:invoke` agrega un heartbeat; su
  respuesta `queued` no demuestra ejecución.
- Antes de `runtime-state:reset-session`, pausa diagnóstica: captura estado/run
  ids y confirma que no se pierde trabajo activo.

## Goals, projects y modelo org

```text
goal list|get|create|update|delete
project list|get|create|update|delete
org get|svg|png
```

- Goals: enum de level documentado como `company|team|agent|task`, status
  `planned|active|achieved|cancelled`. Verifica los valores que acepte el servidor.
- Project status real en la instancia observada: `backlog|planned|in_progress|
  completed|cancelled`; `active` no es válido para project.
- Antes de asociar issue y project confirma que ambos son de la misma company:
  el API ha aceptado referencias cross-company silenciosamente en algunos paths.
- Crear goal company → child goal por workstream; poner outcome, deuda/evidencia y
  DoD verificable en la descripción; asociar el project a goals cuando aplica.
- En fan-out, modela relación y blocker en el grafo (`parentId`, `goalId`,
  `blockedByIssueIds`); texto libre no crea dependencias ejecutables.
- Strict org tree: un CEO raíz; cada agente restante tiene un manager; sin ciclos.
  Asegura salud de CEO/manager antes de asumir que una estrategia delegará.
- Roles routable: `ceo`, `cto`, `cmo`, `engineer`, `designer`, `general`.
  `role`, no `title`, gobierna algunas comprobaciones de servidor.
- Agent-auth delegation tiene guardrails para paused assignee y ciclos. Un
  `@mention` no es una asignación ni un wake garantizado.

## Activity, approvals y decisiones

```text
activity list|create|issue
approval list|get|create|approve|reject|request-revision|resubmit|comment
```

- `activity list` usa `-C`, filtros opcionales `--agent-id`, `--entity-type`,
  `--entity-id`; esta versión no anuncia `--limit`.
- Eventos útiles: `issue.comment_added`, `environment.lease_acquired`,
  `environment.lease_released`, `issue.successful_run_handoff_required`.
- `activity issue <issueId>` inspecciona el audit trail de una issue.
- Revisa tipo, payload y autoridad antes de aprobar una aprobación; cambios de
  estrategia/hire pueden habilitar trabajo o gasto externo.
- `request_changes` es un veredicto de review, no estado de issue. Registra el
  cambio concreto y dueño; usa `--resume` solo cuando la continuación es válida.

## Secrets: metadatos, referencias y rotación

```text
secrets list|declarations|create|link|update|rotate|usage|access-events|delete
secrets doctor|providers|provider-configs|provider-config:create
secrets provider-config:discovery-preview|provider-config:get|provider-config:update
secrets provider-config:default|provider-config:health|provider-config:delete
secrets remote-import:preview|remote-import|migrate-inline-env
```

Para este slice, `list`, `usage` y `access-events` son lecturas de diagnóstico.
`rotate`, `create`, `link`, provider-config mutation, import/migration y `delete`
son operaciones sensibles, fuera del flujo diario. No se incluyen valores de
secrets en comentarios, comandos o reporte; valores gestionados son cifrados y
no se recuperan por API después de la creación. No rotes un secret solo porque un
run está trabado: primero confirma que es la causa y solicita autorización.

## Workspaces y environment

```text
workspace list|get|close-readiness|operations|update|runtime-service|runtime-command
environment list|capabilities|create|get|leases|lease|update|delete|probe|probe-config
project-workspace list|create|update|delete|runtime-service|runtime-command
```

Inspeccionar status, operations, close readiness y lease ayuda a localizar locks
sin intervenirlos. `runtime-command`, `runtime-service`, update, create y delete
pueden modificar entornos o ejecutar acciones fuera del board: no pertenecen al
steering habitual y requieren permiso/plan específicos. No tomar un lease por un
run Paperclip sin correlación de issue y agente.

## Comandos fuera del alcance board ops

La CLI instalada ofrece además:

- **Instancia/runtime**: `install`, `uninstall`, `update/upgrade`, `onboard`,
  `doctor`, `configure`, `db:backup`, `allowed-hostname`, `run`, `service`,
  `auth`, `instance`, `admin`, `channels`, `env`, `test-drive`, `worktree`.
  Diagnosticar/administrar en Slice 3; algunos son destructivos.
- **Adapters e integración**: `adapter`, `managed-agent`, `mcp`, `openclaw`,
  `connections`, `email`, `plugin`, `llm`, `agent-config`; adapters/modelos en
  Slice 2. No asumir que son parte de board ops.
- **Organización/administración**: `member`, `invite`, `join`, `profile`,
  `token`, `access`, `board-claim`, `asset`, `sidebar`, `inbox`, `teams`.
  Cambios de acceso/credenciales requieren autoridad específica.
- **Contenido/automatización**: `skill`, `skills`, `available-skill`, `routine`,
  `routines`, `pipelines`, `feedback`, `env-lab`, `heartbeat`.
  Son subsistemas con ciclo de vida propio; no son sinónimos de issues.
- **Finanzas y capacidad**: `finance`, `cost`, `budget`; lectura selectiva es
  pertinente al board, pero policy/budget/event writes requieren autorización.

Los nombres de grupo/top-level son los de `paperclipai --help`; cada grupo tiene
subcomandos adicionales. En v2026.1012.0 se observaron 53 grupos top-level. La
superficie de subcomandos cambia entre releases; no reportar un total de hojas
sin fijar y documentar el método de recuento.

## Fuentes

- Referencia CLI oficial por grupo: https://docs.paperclip.ing/reference/cli/
- Paperclip agent CLI: https://docs.paperclip.ing/reference/cli/agent/
- Issue CLI: https://docs.paperclip.ing/reference/cli/issue/
- Surface real verificada con `paperclipai --help` y `paperclipai <grupo> --help`,
  versión 2026.1012.0. La ayuda local prevalece para la instalación activa.
