# Design Spec — Slice 3: `ree-paperclip-instance-admin`

## 1. Alcance

Crear la skill corporativa `ree-paperclip-instance-admin` en
`skills/ree-paperclip-instance-admin/SKILL.md`. Responsabilidad: administrar la
instancia Paperclip como servicio — arranque, reinicio caliente, respaldo y
restauración de base de datos, reparación de payload, diagnóstico de salud,
bootstrap CEO, desbloqueo de join requests, y verificación de canales de
release.

Todo el conocimiento proviene de:
- `paperclip-opencode-litellm` (secciones clasificadas como Slice 3 en los specs
  anteriores: Instance health UI 500, Deployment mode awareness, Join request
  unblock, Skills home, Monitoring cron)
- `references/instance-repair.md` y `references/skills-and-instructions.md` de
  la skill fuente
- CLI `paperclipai` v2026.1012.0 verificado (`service`, `instance`, `db:backup`,
  `configure`, `admin`, `channels`, `doctor`, `auth`)
- Datos reales de instancia (`config.json`, `install.json`, `health --json`,
  `doctor`, `service status --json`) recolectados durante la investigación

## 2. Responsabilidad única

Administrar la instancia Paperclip como servicio de sistema: control de
ciclo de vida del proceso (start/stop/restart), respaldo y verificación de
base de datos, reparación de payload corrupto o faltante, diagnóstico de salud
con `doctor`, bootstrap de CEO en modo autenticado, y configuración de canales
de release.

NO cubre:
- Operación diaria del board (→ `ree-paperclip-board-ops`)
- Diagnóstico de adapters y gateways (→ `ree-paperclip-adapter-diagnosis`)
- Método completo intake→handoff (→ `ree-hermes-paperclip-method`)

## 3. Clasificación de la skill fuente (Fase 3a entregable)

### → Slice 3: ree-paperclip-instance-admin

| Líneas fuente | Sección | Razón |
|---|---|---|
| 188-189 | "Instance health: UI 500 while the API is healthy" | Reparación de payload: UI ENOENT mientras API responde |
| 192-198 | "Deployment mode awareness" | Modos de despliegue (`local_trusted` vs `authenticated`), `bootstrap-ceo` |
| 200-213 | "Agent join-request approval and the 'no active CEO' error" | Admin de compañía: roles de agente, unblock de join requests |
| 215-224 | "Disposition contract" | Mecánica de handoff del runtime Paperclip (skill paperclip, steps, timeout) |
| 226-229 | "Monitoring Paperclip from a Hermes cron job" | Monitoreo de instancia desde cron (heredoc en cron mode) |
| 238-242 | "Skills home: one owner per name" | Gestión de skills home (`~/.claude/skills`, colisiones de directorio, import) |
| N/A | `references/instance-repair.md` (70 líneas) | Instalación gestionada, reparación de payload, DB/backups, cross-company FK |
| N/A | `references/skills-and-instructions.md` (31 líneas) | Instructions bundles, skills library, materialización, aislamiento |

### → Ya extraído a Slice 1 (board-ops)

| Líneas fuente | Sección |
|---|---|
| 138-159 | "Delegating work to an agent (board ops)" |
| 161-173 | "Driving a long-running issue to completion (steering loop)" |
| 175-186 | "Reviewing and merging an agent's PR" |
| ref | `references/delegation-and-org-model.md` |
| ref | `references/paperclip-cli.md` § board commands |

### → Ya extraído a Slice 2 (adapter-diagnosis)

| Líneas fuente | Sección |
|---|---|
| 25-49 | "Where each piece goes" + "Native runner ENOENT triage" |
| 50-63 | "Rules learned the hard way" |
| 64-95 | Gateway auth + secret misalignment fix |
| 96-101 | OpenCode background service gotchas |
| 102-113 | Verification (adapter-side) |
| 114-137 | Hermes gateway run diagnostics |
| 231-248 | Creating gateway agents + model compatibility |

## 4. Inventario CLI de instancia (Fase 3a)

### Grupo I — Service (systemd)
- `service install/uninstall/start/stop/restart/status/logs`
- `restart` es hot restart: preserva runs activos, imprime `newServerPid`/`lostRunIds`, escribe `hot-restart-report.json`
- `status` muestra `platform: systemd`, `active`, `enabled`, `pid`, `health.ok`
- `logs` acepta `--follow`, `--lines <N>`

### Grupo J — Instance settings
- `instance settings:general` (lectura: `censorUsernameInLogs`, `feedbackDataSharingPreference`, `backupRetention`)
- `instance settings:general:update --payload-json`
- `instance settings:experimental` / `settings:experimental:update`
- `instance scheduler-heartbeats`
- `instance database-backup`

### Grupo K — Database
- `db:backup` (one-off, soporta `--dir`, `--retention-days`, `--filename-prefix`, `--json`)
- Backup automático: `config.json → database.backup.{enabled,intervalMinutes(60),retentionDays(30),dir}`
- Backups en `data/backups/paperclip-<YYYYMMDD-HHMMSS>.sql.gz`

### Grupo L — Doctor & configure
- `doctor` (15+ checks: config, deployment mode, JWT secret, secrets adapter, storage, DB, LLM, logs, port, Node.js, managed install, service)
- `doctor --repair --yes` (reparación automática)
- `configure --section <llm|database|logging|server|storage|secrets>` (interactivo)

### Grupo M — Auth & admin
- `auth bootstrap-ceo --force --expires-hours --base-url`
- `auth login/logout/revoke-current/whoami`
- `admin user list/promote/demote/company-access/company-access:update`

### Grupo N — Channels
- `channels --json`: `stable`, `beta`, `nightly`, `canary` con versiones y audiencia

## 5. Estructura canónica (patrón Reevolutiva)

```
---                              ← frontmatter YAML
## When to Use                   ← triggers + no usar
## How to Run                    ← requisitos, contexto, flags y límites de seguridad
## Quick Reference               ← tabla de síntoma, comando y evidencia
## Procedure                     ← 6 procedimientos
### P1 — Chequeo de salud de la instancia
### P2 — Reparar UI 500 (payload corrupto)
### P3 — Hot restart del servicio
### P4 — Backup manual y verificación
### P5 — Bootstrap CEO y desbloqueo de join requests
### P6 — Gestión de skills home y colisiones
## Jev Integration Points        ← 6 gates noul/choice
## Pitfalls                      ← bullets, una trampa por bullet
## Verification                  ← evidencia comprobable por procedimiento
```

## 6. Procedimientos principales

### P1 — Chequeo de salud de la instancia

Objetivo: Un chequeo de solo lectura que determina si la instancia está sana,
requiere atención o está degradada, sin reiniciar ni reparar.

1. `paperclipai health --json`: `status`, `version`, `serverVersion`,
   `deploymentMode`, `bootstrapStatus`, `databaseBackup.status`.
2. `paperclipai service status --json`: `active`, `pid`, `health.ok`.
3. `paperclipai doctor`: revisar checks fallidos y warnings.
4. `paperclipai channels --json`: confirmar canal activo y versión.
5. `paperclipai db:backup` no es un chequeo de salud diario; solo verificar
   `databaseBackup.status` y `latestBackup.ageHours` desde `/health`.

Criterio de salida: clasificación `healthy`/`needs_attention`/`degraded` con
checks fallidos citados y recomendación sin mutaciones.

### P2 — Reparar UI 500 (payload corrupto)

Objetivo: Restaurar el payload npm cuando la UI responde 500 (`ENOENT …
ui-dist/index.html`) pero la API está sana.

1. Confirmar síntoma: `curl -sS http://127.0.0.1:3100/` → 500; `/api/health` → 200.
2. `journalctl --user -u paperclipai.service --since "5 min ago"` → buscar `ENOENT`
   en `@paperclipai/server/ui-dist/index.html`.
3. Leer `~/.paperclip/cli/install.json`: `payloadPath`, `version`.
4. Verificar que el payload existe: `ls <payloadPath>/node_modules/@paperclipai/server/ui-dist/index.html`.
5. Si falta: `mkdir -p "<payloadPath>" && npm install --prefix "<payloadPath>" --no-audit --no-fund --prefer-offline paperclipai@<version>`.
6. La UI se recupera sin restart porque los módulos API están en memoria pero
   `index.html` se lee por request. Verificar: `curl -sS http://127.0.0.1:3100/` → 200.
7. Causa raíz: update interrumpido o fallido. Revisar `update-check.json` e
   `install.json`; documentar la discrepancia de versión si existe.

Criterio de salida: UI responde 200, payload restaurado, causa documentada.

### P3 — Hot restart del servicio

Objetivo: Reiniciar el proceso Paperclip preservando runs activos.

1. `paperclipai service status --json`: confirmar `active: true`, registrar `pid`.
2. `paperclipai service restart --json`: capturar `newServerPid`, `lostRunIds`.
3. Si se requiere versión específica: `--expected-version <version>`.
4. Verificar post-restart: `paperclipai service status --json` → `active: true`.
5. Leer `instances/<id>/hot-restart-report.json`: `previousServerVersion`,
   `newServerVersion`, `previousServerPid`, `newServerPid`, `lostRunIds`.
6. `paperclipai health --json`: confirmar `serverVersion` coincide.
7. Si `doctor` reporta `Service version: Running unknown` tras restart exitoso:
   verificar `hot-restart-report.json` y `service status`; `doctor` puede dar
   false-negative cuando `/api/health` omite `serverVersion`.

Criterio de salida: nuevo PID, health OK, `hot-restart-report.json` registrado,
runs preservados (sin `lostRunIds` inesperados).

### P4 — Backup manual y verificación

Objetivo: Crear un backup puntual y verificar su integridad, sin restaurar.

1. `paperclipai db:backup --json`: capturar `path`, `sizeBytes`, `name`.
2. `paperclipai health --json` → `databaseBackup`: confirmar backup automático
   habilitado, último backup, `ageHours`, sin `lastFailure`.
3. Verificar integridad: `gzip -t <backupPath>` (no comprime en vivo, solo
   verifica estructura gzip).
4. Listar backups existentes: `ls -lh <backupDir>/`.
5. La configuración de retención está en `config.json → database.backup` y en
   `instance settings:general → backupRetention`.
6. No restaurar sin plan de rollback, backup fresco adicional y autorización
   explícita. La restauración no es un procedimiento de rutina.

Criterio de salida: backup creado, integridad gzip verificada, ruta y tamaño
registrados.

### P5 — Bootstrap CEO y desbloqueo de join requests

Objetivo: Crear el primer admin en modo `authenticated` y aprobar join requests
bloqueadas por falta de CEO.

**Bootstrap:**
1. `paperclipai health --json` → `deploymentMode`: solo aplica en `authenticated`.
   En `local_trusted`, `bootstrap-ceo` imprime "only required for authenticated
   mode" y sale.
2. `paperclipai auth bootstrap-ceo --force --expires-hours 24 --base-url <url>`.
3. El invite es one-time; compartir solo con el destinatario autorizado.

**Unblock join request:**
1. `GET /api/companies/<companyId>/agents`: identificar agente con `reportsTo: null`.
2. El gate de aprobación busca `role === "ceo"`, no `title`.
3. `PATCH /api/agents/<agentId>` con `{"role": "ceo"}` (temporal).
4. `POST /api/companies/<companyId>/join-requests/<requestId>/approve`.
5. `PATCH /api/agents/<agentId>` con `{"role": "<original>"}`.
6. `PATCH /api/companies/<companyId>/members/<principalId>` con
   `{"membershipRole": "ceo"}` **no funciona**: `ceo` no es membership role
   válido (solo `owner`, `admin`, `operator`, `viewer`).

Criterio de salida: invite creado (o unreachable en `local_trusted`); join
request aprobada y rol de agente restaurado.

### P6 — Gestión de skills home y colisiones

Objetivo: Diagnosticar y resolver colisiones en el directorio compartido de
skills (`~/.claude/skills`), sin perder contenido.

1. `paperclipai skills agent list <agentId> -C <companyId>`: revisar `state`,
   `managed`, `desired`.
2. `state=external managed=false` con `origin=company_managed` indica colisión:
   un directorio real ocupa el nombre que Paperclip quiere gestionar.
3. Respaldar con ruta única y verificar: `backup="$HOME/.claude/skills/<name>.backup.$(date +%Y%m%d%H%M%S)"; cp -a -- "$HOME/.claude/skills/<name>" "$backup"`; confirmar que el backup contiene el contenido esperado.
4. Antes de quitarlo, verificar que es un directorio real (no symlink), que el backup es legible, y tener autorización explícita. Solo entonces: `rm -r -- "$HOME/.claude/skills/<name>"`.
5. `paperclipai skills agent sync <agentId> -C <companyId> --skill <ref> --mode add`.
6. Verificar: `skills agent list` muestra `state=installed managed=true`.
7. Para importar desde Source: `paperclipai skill import --payload-json '{"source":"<repo-url>"}' -C <companyId>`.
8. Reglas de aislamiento: solo symlinks en `~/.claude/skills`; skills
   project-specific en `.agents/skills/` del repo; company-private con prefijo.

Criterio de salida: skills en `state=installed managed=true`, sin directorios
reales colisionando, importación desde Source verificada.

## 7. Conocimiento técnico a incorporar de la fuente

| Regla | Destino en skill |
|---|---|
| UI 500 + API 200 = payload ENOENT; reparar con `npm install`, sin restart | P2 / Pitfalls |
| `deploymentMode`: `local_trusted` vs `authenticated`; `bootstrap-ceo` solo en authenticated | P5 / Pitfalls |
| `membershipRole=ceo` rechazado; roles humanos válidos son `owner`, `admin`, `operator`, `viewer` | P5 / Pitfalls |
| Hot restart preserva runs; `hot-restart-report.json` como fuente de verdad post-restart | P3 / Pitfalls |
| `doctor` puede false-negative `Service version: Running unknown`; verificar con `service status` y `health` | P1 / Pitfalls |
| `dotenv`-loaded vars no en `/proc/<pid>/environ` | Pitfalls |
| Backup automático: 60min interval, 30d retention, `data/backups/` | P4 / How to Run |
| `backupRetention` visible en `instance settings:general`, valores en `config.json → database.backup` | P4 |
| No composite FK `(company_id, project_id)`; cross-company links silenciosos | P1 (nota en health check) |
| `~/.claude/skills` debe ser solo symlinks; directorio real = `state=external` | P6 / Pitfalls |
| Import desde Source es JSON: `--payload-json '{"source":"<url>"}'` | P6 |
| Cron mode bloquea heredocs; usar comandos one-line | Pitfalls (monitoring) |
| `paperclipai` es managed install; nunca `npx paperclipai` | How to Run |
| Disposition contract: `successful_run_missing_state` cuando run succeeded pero issue sigue `in_progress` | Pitfalls (cross-ref board-ops) |
| `opencode_local` runtime legacy: no infiere disposition; agente debe escribirla | Pitfalls (cross-ref board-ops) |

## 8. Referencias

| Referencia | Contenido | Estado |
|---|---|---|
| `references/instance-repair.md` | Instalación gestionada, reparación payload, DB/backups, cross-company FK, scoping | Se adaptará de la skill fuente |

## 9. Límites con otras skills

| Situación | Skill correcta |
|---|---|
| "La UI da 500 en todas las páginas pero /api/health OK" | `ree-paperclip-instance-admin` P2 |
| "Necesito reiniciar Paperclip sin perder runs" | `ree-paperclip-instance-admin` P3 |
| "Un agente nuevo no puede joinear, dice 'no active CEO'" | `ree-paperclip-instance-admin` P5 |
| "Quiero crear un backup ahora" | `ree-paperclip-instance-admin` P4 |
| "El run no avanza y el error es `Model unavailable`" | `ree-paperclip-adapter-diagnosis` |
| "Necesito seguir un issue y ver si el agente avanzó" | `ree-paperclip-board-ops` |
| "Quiero cambiar el canal de release a beta" | `ree-paperclip-instance-admin` (channels) |

## 10. Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta |
|---|---|---|---|
| P1 — Health check | Clasificación correcta | `noul` | "¿La clasificación (healthy/needs_attention/degraded) está respaldada por los checks de doctor, health y service status?" |
| P2 — UI 500 repair | Causa confirmada | `noul` | "¿El error ENOENT en journalctl coincide con el path del payload faltante?" |
| P3 — Hot restart | Verificación post-restart | `noul` | "¿El nuevo PID, health y hot-restart-report.json confirman que el restart fue exitoso?" |
| P4 — Backup | Integridad verificada | `noul` | "¿El backup se creó, su integridad gzip se verificó, y su ruta/tamaño están registrados?" |
| P5 — Bootstrap/unblock | Operación revertida | `noul` | "¿El rol del agente se restauró a su valor original tras aprobar el join request?" |
| P6 — Skills home | Sin colisiones | `noul` | "¿Todos los skills en `~/.claude/skills` están en state=installed managed=true?" |

## 11. Gate de diseño (Jev Score)

Niveles: `incompleto`, `minimo_viable`, `completo`, `sobreconstruido`.

Este Design Spec apunta a `completo`: seis procedimientos, inventario CLI
completo de los grupos de instancia, clasificación de las 8 secciones fuente
pendientes, seis Jev gates, una referencia mapeada (`instance-repair.md`), y
límites claros con `ree-paperclip-board-ops` y `ree-paperclip-adapter-diagnosis`.