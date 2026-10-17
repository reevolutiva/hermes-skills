# Modelo de delegación y organización de Paperclip

Referencia de operación del board: objetivos, proyectos, árbol organizativo,
guardarraíles y traspaso entre Hermes y los agentes de Paperclip. No cubre la
configuración de adapters ni la administración de la instancia.

## Requisitos para cada delegación

1. **Guardarraíles específicos**: matriz de permisos/denegaciones,
   `blockedByIssueIds` y DoD explícita en el issue. No des por supuestos los
   límites.
2. **Validación empírica**: una prueba que pueda fallar antes y pasar después, o
   una comprobación funcional del objetivo real. El resumen del agente no basta.
3. **Alcance quirúrgico**: el cambio mínimo que satisface el criterio de
   aceptación. Resuelve ambigüedades en el issue y cierra `in_review`; ampliar
   alcance sin permiso es un defecto.

## Forma objetivo del árbol organizativo

```
Agente Hermes Intake = CEO     ← recibe el pedido en la raíz del árbol
├── manager de implementación     ← coordina a los ejecutores
│   ├── agente OpenCode por repo  ← ejecutor, definido en .opencode/agents/<name>.md
│   └── ...
└── ...
```

- El agente Intake tiene `role: ceo` y debe ser único. Un agente auxiliar con
  adapter `process` y rol `ceo` en mitad del árbol es un defecto.
- Cada ejecutor tiene exactamente un manager. No dejes agentes sin manager.
- `reportsTo: null` y `role != ceo` implica una cadena organizativa inválida;
  corrígela antes de delegar.

## Flujo de delegación guiado por objetivos

1. El board crea un **objetivo de compañía** (`goal create -C <companyId> --level company --status active`).
2. El CEO despierta por heartbeat, lee los objetivos y propone una estrategia;
   el board la **aprueba**.
3. El CEO crea tareas como objetivos hijos y las asigna a sus reportes.
4. Asignar un issue a un agente es el trigger de wake (`source: assignment`).
5. El agente informa avances en comentarios del issue y termina con una disposición
   explícita.
6. El board verifica los artefactos y dispone el issue (`done`, `blocked` o
   entrega de feedback).

## Reglas del árbol org (aplicadas por Paperclip)

- Árbol estricto: cada agente, excepto el CEO, tiene exactamente un manager.
- El enrutamiento usa `role` (`ceo`, `cto`, `cmo`, `engineer`, `designer`,
  `general`), no `title`.
- Aprobar una solicitud de incorporación de agente requiere un agente activo con
  `role: ceo` y `reportsTo: null`.
- Forma de actualización: `agent update <agentId> --payload-json '{"role":"ceo"}'`
  o `'{"reportsTo":"<managerId>"}'`.
- Inspecciona con `agent list -C <companyId> --json` (role, adapterType y
  reportsTo) y `org get -C <companyId> --json`.

## Goals

```text
goal create -C <companyId> --title "…" --description "…" --level company --status active [--parent-id <id>] [--owner-agent-id <id>]
goal update <goalId> --parent-id … --status …
goal list -C <companyId>
goal get <goalId>
```

- Enum de `level`: `company | team | agent | task`.
- Enum de `status`: `planned | active | achieved | cancelled`.
- Escribe el **DoD verificable** en la descripción del goal hijo. Paperclip
  incluye ese contexto en el issue de ejecución.
- Vincula el proyecto a sus goals con `project update <id> -C <companyId> --goal-ids <csv>`.
- La CLI valida que los goals vinculados pertenezcan a la misma compañía.

## Projects

```text
project list|get|create|update|delete
```

- Enum de estado: `backlog | planned | in_progress | completed | cancelled`.
  `active` **no** es un estado válido de project y será rechazado.
- `project create` no crea un workspace; son recursos independientes.
- `project delete` falla mientras haya issues que lo referencien, incluidos
  algunos issues eliminados previamente. Borra primero los issues y después el
  proyecto, solo con autorización.
- `project update <id> --description "$(cat brief)"` puede guardar contexto
  permanente del proyecto.
- Usa `-C <companyId>` en cada comando de project.

## Issues

```text
issue create -C <companyId> --project-id <id> --assignee-agent-id <id> --title "…" --description "$(cat brief)" --status todo --priority high --goal-id <childGoalId>
issue get <id|IDENTIFIER>          # resolución global; no acepta -C
issue update <id> --status done --comment "Aprobado: <evidence>"
issue comment <id> --resume --body "Cambios requeridos: …; responsable: <agent>"
issue force-release <id>           # liberar checkout atascado; requiere evidencia y permiso
```

- Asignar un issue despierta al agente en su siguiente heartbeat. Crear un issue
  sin `--assignee-agent-id` prepara trabajo en backlog sin despertarlo.
- Formato del identifier: `<COMPANY_PREFIX>-<n>` (por ejemplo, `REE-1`).
- Estados válidos de issue: `backlog | todo | in_progress | in_review | done |
  blocked | cancelled`. `request_changes` **no** es un estado de issue; usa un
  comentario con instrucciones y define el siguiente responsable.

## Ejecución y estado runtime del agente

```text
agent runtime-state <agentId>   # lastRunId, lastRunStatus, sessionId, token counts, lastError
agent runtime-state:reset-session <agentId>  # restablece la sesión; captura evidencia primero
agent configuration <agentId>   # adapterConfig redactada: cwd, model, command, instructionsFilePath
agent config-revisions <agentId> | agent config-revision:get <agentId> <revId>
agent heartbeat:invoke <agentId>   # encola UN heartbeat adicional; devuelve status=queued
```

## Activity (registro de auditoría)

```text
activity list -C <companyId> [--agent-id <id>] [--entity-type <type>] [--entity-id <id>]
activity issue <issueId>
```

Eventos útiles:

- `issue.comment_added`: salida del agente en el issue.
- `environment.lease_acquired` / `environment.lease_released`: adquisición y
  liberación del lease durante una ejecución.
- `issue.successful_run_handoff_required`: el run terminó sin disponer el issue.

## Ciclo de vida de aprobaciones

```text
approval list -C <companyId> [--status pending]
approval get <approvalId>
approval approve|reject|request-revision|resubmit|comment
```

La aprobación de la estrategia del CEO es un bloqueo frecuente. El board aprueba;
rechazar requiere un motivo y pedir revisión debe especificar los cambios
solicitados. La aprobación y el estado del issue son independientes: un issue
puede avanzar mientras su aprobación vinculada sigue abierta, y el CEO no puede
asignar subtareas hasta aprobar la estrategia.

## Mecánica de delegación

- **Motivos de wake**: `issue_assigned`, `issue_commented`,
  `issue_comment_mentioned`, `issue_reopened_via_comment`,
  `issue_blockers_resolved` (todos los issues de `blockedBy` pasan a `done`; los
  `cancelled` no cuentan), `issue_children_completed`, `issue_monitor_due` y
  `finish_successful_run_handoff`.
- Delega usando el grafo: `parentId`, `goalId`, `blockedByIssueIds`. El parent por
  sí solo **no** bloquea; solo `blockedByIssueIds` genera
  `issue_blockers_resolved`.
- Los issues delegados deben ser **autocontenidos**: copia criterios y material
  necesario en la descripción o indica rutas relativas al repo. Puede que el
  delegado no pueda leer documentos del issue padre.
- **No hay watchers**: el único chequeo recurrente usa `monitorNextCheckAt` y
  `executionPolicy.monitor`, con un assignee, sin assignee usuario y con el issue
  en `in_progress` o `in_review`. Describir un watcher en texto no lo crea.
- Un run `opencode_local` (`runtimeMode: legacy`) no puede inferir su disposición;
  el agente debe llamar explícitamente a `issue update --status …`.
- **Contrato de disposición**: un run exitoso con el issue aún en `in_progress`
  dispara `successful_run_missing_state`. Paperclip espera que el agente disponga
  el issue (`in_review`, `done`, `blocked`) o que intervenga el board.

## Guardarraíles de delegación entre agentes

- Se rechaza asignar a un agente **paused**: `Cannot assign work to a paused agent.`
- Se rechazan ciclos de delegación con código `delegation_cycle`: un agente crea
  un hijo asignado al creador de un ancestro abierto. Los ancestros cerrados en
  `done` o `cancelled` no activan esta regla.
- **Cadena de escalamiento pausada**: el worker puede ejecutar trabajo, pero
  reporta a un agente pausado (directa o indirectamente). Reactiva el manager o
  reestructura el árbol.
- Una actualización del agente (incluso un `reportsTo` simple) puede rechazarse
  con `422 ai_connection_default_missing` si su binding es `responsible_user` y
  el usuario no tiene una conexión de IA personal marcada como predeterminada.

## Skills e instrucciones

- Para `opencode_local`, las skills se materializan en `~/.claude/skills` (ruta
  compartida por el host). Mantén allí las skills org-wide; las específicas de
  proyecto van en `.agents/skills/` dentro del repo.
- Un directorio real en el home de skills compartido hace que Paperclip trate la
  skill como `state=external, managed=false` y deje de gestionarla.
- `hermes_gateway` no implementa sincronización de skills: devuelve
  `supported=false`. Las instrucciones del agente deben viajar en su bundle.
  Comprueba `skills agent list` antes de diseñar un agente que dependa de recibir
  skills por sincronización.
