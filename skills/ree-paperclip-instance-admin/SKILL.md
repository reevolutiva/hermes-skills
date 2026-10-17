---
name: ree-paperclip-instance-admin
description: "Administra Paperclip: servicio, backup y reparación."
version: 0.1.0
author: Hermes
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [paperclip, instance, service, backup, repair, admin]
    related_skills: [ree-paperclip-board-ops, ree-paperclip-adapter-diagnosis, ree-hermes-paperclip-method]
---

# ree-paperclip-instance-admin — Administración de la instancia Paperclip

Administra la instancia Paperclip como servicio de sistema: control de ciclo de vida del proceso, respaldo y verificación de base de datos, reparación de payload, diagnóstico de salud, bootstrap de CEO en modo autenticado, configuración de canales de release y resolución de colisiones en el skills home compartido.

No opera el board (→ `ree-paperclip-board-ops`) ni diagnostica adapters/gateways (→ `ree-paperclip-adapter-diagnosis`).

## When to Use

- La UI responde 500 pero `/api/health` devuelve 200.
- Necesitás reiniciar Paperclip sin perder runs activos (hot restart).
- Querés crear un backup manual y verificar su integridad.
- Un agente nuevo no puede joinear: "no active CEO" o join request bloqueada.
- Un directorio real en `~/.claude/skills` sombrea skills gestionados.
- Querés cambiar el canal de release o diagnosticar la versión instalada.

### No usar para

- Seguir issues, revisar PRs o diagnosticar runs de agentes: `ree-paperclip-board-ops`.
- Diagnosticar `Model unavailable`, 401 de gateway o ENOENT de adapter: `ree-paperclip-adapter-diagnosis`.
- Crear delegaciones desde cero: `ree-hermes-paperclip-method`.

## How to Run

`paperclipai` es una instalación gestionada (managed install). NUNCA uses `npx paperclipai`.

Precondiciones:
1. `paperclipai --version` confirma la instalación activa (`managed npm pinned; payload …`).
2. `paperclipai service status --json` confirma `active: true` antes de cualquier mutación en el servicio.
3. Antes de restaurar un backup, crear un backup fresco adicional y obtener autorización explícita.
4. No exponer secretos, tokens ni valores de `Secret.data` en logs, archivos o comentarios.
5. Las mutaciones que afectan runs activos (restart, stop) requieren verificación previa de que no hay trabajo crítico en vuelo.

## Quick Reference

| Síntoma | Lectura | Acción | Evidencia |
|---|---|---|---|
| UI 500, API OK | `journalctl --user -u paperclipai.service` | `npm install` en payload path | `curl /` → 200 |
| Necesito reiniciar | `service status --json` | `service restart --json` | `hot-restart-report.json`, nuevo PID |
| Sin backups recientes | `health --json` → `databaseBackup` | `db:backup --json` | `gzip -t <path>`, ruta y tamaño |
| "no active CEO" | `health --json` → `deploymentMode` | `auth bootstrap-ceo --force` | Invite URL (solo authenticated) |
| Join request bloqueada | `GET /api/companies/<id>/agents` | `PATCH agent role=ceo` → approve → restaurar | Agente con rol original, request approved |
| Skills external | `skills agent list … --json` | `rm -rf` directorio real → `sync --mode add` | `state=installed managed=true` |
| Versión incorrecta | `channels --json`, `install.json` | Cambiar canal si aplica | `health --json` → `serverVersion` |

## Procedure

### P1 — Chequeo de salud de la instancia

Solo lectura: determina si la instancia está sana, requiere atención o está degradada, sin reiniciar ni reparar.

1. `paperclipai health --json`: `status`, `version`, `serverVersion`, `deploymentMode`, `bootstrapStatus`, `databaseBackup.status`, `databaseBackup.latestBackup.ageHours`.
2. `paperclipai service status --json`: `active`, `pid`, `health.ok`.
3. `paperclipai doctor`: identificar checks con `FAIL` o `WARN`; registrar cuáles.
4. `paperclipai channels --json`: confirmar canal (`stable`, `beta`, `nightly`, `canary`) y versión activa.
5. No ejecutar `db:backup` como chequeo de salud. Solo verificar `databaseBackup.status` y `latestBackup.ageHours`.

Criterio de salida: clasificación (`healthy`/`needs_attention`/`degraded`), con checks fallidos citados y recomendación. Sin mutaciones.

### P2 — Reparar UI 500 (payload corrupto)

Restaura el payload npm cuando la UI responde 500 (`ENOENT … ui-dist/index.html`) pero la API está sana.

1. Confirmar síntoma: `curl -sS http://127.0.0.1:3100/` → 500; `curl -sS http://127.0.0.1:3100/api/health` → 200.
2. `journalctl --user -u paperclipai.service --since "5 min ago" | grep ENOENT`: buscar `@paperclipai/server/ui-dist/index.html`.
3. Leer `~/.paperclip/cli/install.json`: extraer `payloadPath` y `version`.
4. Verificar si el payload existe: `ls <payloadPath>/node_modules/@paperclipai/server/ui-dist/index.html`.
5. Si falta: `mkdir -p "<payloadPath>" && npm install --prefix "<payloadPath>" --no-audit --no-fund --prefer-offline paperclipai@<version>`.
6. Verificar: `curl -sS http://127.0.0.1:3100/` → 200. No se requiere restart: los módulos API están en memoria, `index.html` se lee por request.
7. Causa raíz: revisar `~/.paperclip/cli/update-check.json` e `install.json`; documentar discrepancia de versión si existe. El payload puede desaparecer por un update interrumpido.

Criterio de salida: UI responde 200, payload restaurado, causa documentada.

### P3 — Hot restart del servicio

Reinicia el proceso Paperclip preservando runs activos.

1. `paperclipai service status --json`: confirmar `active: true`, registrar `pid`.
2. `paperclipai service restart --json`: capturar `newServerPid`, `lostRunIds`.
3. Si se requiere versión específica: `--expected-version <version>`.
4. Verificar post-restart: `paperclipai service status --json` → `active: true` con nuevo `pid`.
5. Leer `~/.paperclip/instances/<id>/hot-restart-report.json`: `previousServerVersion`, `newServerVersion`, `previousServerPid`, `newServerPid`, `lostRunIds`.
6. `paperclipai health --json`: confirmar que `status` y `serverVersion` son correctos.
7. Si `doctor` reporta `Service version: Running unknown` tras restart exitoso: verificar `hot-restart-report.json` y `service status`. `doctor` puede dar false-negative cuando `/api/health` omite `serverVersion`.

Criterio de salida: nuevo PID, health OK, `hot-restart-report.json` registrado, runs preservados (sin `lostRunIds` inesperados).

### P4 — Backup manual y verificación

Crea un backup puntual y verifica su integridad. No restaura.

1. `paperclipai db:backup --json`: capturar `path`, `sizeBytes`, `name`.
2. `paperclipai health --json` → `databaseBackup`: confirmar backup automático habilitado (`enabled`), último backup (`latestBackup`), `ageHours`, sin `lastFailure`.
3. Verificar integridad: `gzip -t <backupPath>` (no comprime en vivo, solo verifica estructura gzip).
4. Listar backups existentes: `ls -lh <backupDir>/` (por defecto `~/.paperclip/instances/<id>/data/backups/`).
5. Configuración de backup automático: `config.json → database.backup.{enabled,intervalMinutes(60),retentionDays(30),dir}`. También visible en `instance settings:general → backupRetention`.
6. No restaurar desde un backup sin plan de recuperación probado, backup fresco adicional y autorización explícita. El CLI v2026.1012.0 no ofrece `db:restore`; si se necesita recuperar la base, detenerse y preparar un procedimiento específico para el modo de base de datos, con prueba aislada y rollback antes de tocar producción.

Criterio de salida: backup creado, integridad gzip verificada, ruta y tamaño registrados.

### P5 — Bootstrap CEO y desbloqueo de join requests

Crea el primer admin en modo `authenticated` y aprueba join requests bloqueadas.

**Bootstrap:**
1. `paperclipai health --json` → `deploymentMode`: solo aplica en `authenticated`. En `local_trusted`, `bootstrap-ceo` imprime "only required for authenticated mode" y sale.
2. `paperclipai auth bootstrap-ceo --force --expires-hours 24 --base-url <url>` (ej. `https://paperclip.coyote-paridae.ts.net`).
3. El invite es one-time; compartir solo con el destinatario autorizado.

**Unblock join request (solo con autorización explícita):**
1. `GET /api/companies/<companyId>/agents`: identificar candidato con `reportsTo: null`; registrar su `role` original y verificar que la compañía/request sean las correctas.
2. El gate de aprobación busca un agente con `role === "ceo"`, no `title`.
3. Si no hay CEO y existe un candidato adecuado, guardar el estado original y `PATCH /api/agents/<agentId>` con `{"role": "ceo"}` (cambio temporal autorizado).
4. `POST /api/companies/<companyId>/join-requests/<requestId>/approve`.
5. Restaurar inmediatamente `role` original con `PATCH /api/agents/<agentId>`; releer el agente y la join request para verificar ambos estados.
6. Si falla el approve, restaurar igualmente el rol temporal. Si no se puede confirmar la restauración, detenerse y escalar; no continuar con más cambios.
7. `PATCH /api/companies/<companyId>/members/<principalId>` con `{"membershipRole": "ceo"}` no funciona: `ceo` no es membership role humano válido (solo `owner`, `admin`, `operator`, `viewer`).

Criterio de salida: invite creado (o unreachable en `local_trusted`); join request aprobada y rol de agente restaurado.

### P6 — Gestión de skills home y colisiones

Diagnostica y resuelve colisiones en el directorio compartido `~/.claude/skills`.

1. `paperclipai skills agent list <agentId> -C <companyId> --json`: revisar `state`, `managed`, `desired`, `origin`.
2. `state=external managed=false` con `origin=company_managed` indica colisión: un directorio real ocupa el nombre que Paperclip quiere gestionar como symlink.
3. Respaldar con ruta única: `backup="$target.backup.$(date +%Y%m%d%H%M%S)"; cp -a -- "$target" "$backup"`; revisar el backup y confirmar que contiene el contenido esperado.
4. Antes de quitarlo, verificar que `$target` sigue siendo el directorio real previsto (no symlink), que el backup se puede leer, y tener autorización explícita. Solo entonces: `rm -r -- "$target"`.
5. `paperclipai skills agent sync <agentId> -C <companyId> --skill <ref> --mode add`.
6. Verificar: `skills agent list` muestra `state=installed managed=true`.
7. Importar desde Source: `paperclipai skill import --payload-json '{"source":"<repo-url>"}' -C <companyId>`.
8. Reglas de aislamiento:
   - Solo symlinks en `~/.claude/skills`.
   - Skills project-specific en `.agents/skills/` del repo.
   - Skills company-private con prefijo para evitar colisiones cross-company.
   - Nunca copiar un skill org en un repo de proyecto.

Criterio de salida: skills en `state=installed managed=true`, sin directorios reales colisionando, importación desde Source verificada.

## Jev Integration Points

| Procedimiento | Gate | Primitivo | Pregunta |
|---|---|---|---|
| P1 — Health check | Clasificación correcta | `noul` | "¿La clasificación (healthy/needs_attention/degraded) está respaldada por los checks de doctor, health y service status?" |
| P2 — UI 500 repair | Causa confirmada | `noul` | "¿El error ENOENT en journalctl coincide con el path del payload faltante?" |
| P3 — Hot restart | Verificación post-restart | `noul` | "¿El nuevo PID, health y hot-restart-report.json confirman que el restart fue exitoso?" |
| P4 — Backup | Integridad verificada | `noul` | "¿El backup se creó, su integridad gzip se verificó, y su ruta/tamaño están registrados?" |
| P5 — Bootstrap/unblock | Operación revertida | `noul` | "¿El rol del agente se restauró a su valor original tras aprobar el join request?" |
| P6 — Skills home | Sin colisiones | `noul` | "¿Todos los skills en `~/.claude/skills` están en state=installed managed=true?" |

Sin Jev disponible, registrar `[hermes-judgment]` con nivel de confianza y escalar decisiones al usuario.

## Pitfalls

- **UI 500 + API 200 = payload ENOENT**, no corrupción de base de datos. Reparar con `npm install`, sin restart. El binario de embedded-postgres vive en el mismo payload: restaurarlo antes de cualquier restart, o el próximo start falla.
- **`deploymentMode: local_trusted` no necesita `bootstrap-ceo`**. `bootstrap-ceo` imprimirá "only required for authenticated mode" — no es un error.
- **El gate de aprobación de join request busca `role === "ceo"`**, no `title`. Un agente con `title: "CEO"` pero `role: "operator"` no desbloquea nada.
- **`membershipRole: "ceo"` es rechazado**. Membership roles válidos: `owner`, `admin`, `operator`, `viewer`. Para desbloquear join requests, cambiar el `role` del agente, no el membership.
- **`doctor` puede dar false-negative `Service version: Running unknown`**. Si `service status --json` y `health --json` reportan la versión correcta, el false-negative es inofensivo.
- **Hot restart preserva runs activos**. `--wait` drena runs antes de reiniciar; sin `--wait`, los adopta. `hot-restart-report.json` es la fuente de verdad post-restart.
- **No hay comando `db:restore` en el CLI**. No improvisar un restore con `psql`/`gzip` en producción: requiere plan probado para el modo de base de datos, copia adicional, aislamiento y rollback aprobados.
- **Una join request no justifica cambiar roles sin permiso.** Capturar el rol original y restaurarlo también si el approve falla; confirmar la lectura posterior.
- **`~/.claude/skills` debe contener solo symlinks**. Un directorio real → `state=external managed=false` y Paperclip deja de gestionar ese skill.
- **No hay composite FK `(company_id, project_id)`**. Issues pueden referenciar proyectos de otra compañía silenciosamente. Detectar con: `select i.identifier, i.company_id, p.company_id from issues i join projects p on p.id = i.project_id where i.project_id is not null and i.company_id <> p.company_id;`.
- **`dotenv`-loaded vars no aparecen en `/proc/<pid>/environ`**. Usar `paperclipai agent configuration` o `instance settings:general` para inspeccionar, no el entorno del proceso.
- **El payload puede desaparecer por un update interrumpido**. `update-check.json` registra `latest`; `install.json` queda en `channel: pinned`. Verificar ambos si un update reciente falló.
- **Disposition contract**: `successful_run_missing_state` ocurre cuando un run termina `succeeded` pero la issue sigue `in_progress`. Corresponde a board ops, no a instancia — derivar a `ree-paperclip-board-ops`.

## Verification

1. Health check clasifica correctamente sin mutar estado.
2. UI 500 reparada: `curl /` → 200, payload restaurado, causa documentada.
3. Hot restart: nuevo PID, health OK, `hot-restart-report.json` confirma preservación de runs.
4. Backup: `gzip -t <path>` pasa, ruta y tamaño registrados.
5. Bootstrap/unblock: join request aprobada, rol de agente restaurado a original aun si el approve falla; estado final releído.
6. Skills home: `skills agent list` muestra `state=installed managed=true` para todos los skills; backup legible y eliminación solo tras autorización.
7. Restauración: no se ejecuta en producción sin procedimiento específico probado, backup adicional, rollback y autorización.
8. Comandos validados contra `paperclipai --help` real (v2026.1012.0).

Las referencias técnicas están en `references/instance-repair.md`.