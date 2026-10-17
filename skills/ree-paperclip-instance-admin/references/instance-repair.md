# Paperclip instance repair runbook

Read-only diagnosis first; every fix below is reversible and needs no restart unless stated.

## 1. How the CLI is installed (and how to invoke it)

`paperclipai` is a **managed install**, not a plain global package:

| Piece | Path |
|---|---|
| Command on PATH | `~/.local/bin/paperclipai` — a shim that execs `node ~/.paperclip/cli/current/node_modules/paperclipai/dist/index.js` |
| Version switch | `~/.paperclip/cli/current` → `installs/npm/<version>` |
| Install metadata | `~/.paperclip/cli/install.json` — `source`, `version`, `channel` (`pinned`), `payloadPath` |
| Payload | `~/.paperclip/cli/installs/npm/<version>/node_modules/@paperclipai/*` (adapters, server, embedded postgres binary) |

Invoke it as `paperclipai` (or the resolved `node …/current/node_modules/paperclipai/dist/index.js`). **Never `npx paperclipai`** — that resolves a different, unmanaged copy whose version need not match the running server.

## 2. Symptom pair: CLI `Cannot find module` + every UI route 500

Both at once means the **payload directory is gone** while the processes keep running from it:

- CLI: `Error: Cannot find module '~/.paperclip/cli/current/node_modules/paperclipai/dist/index.js'`; `readlink -f ~/.paperclip/cli/current` prints nothing (dangling symlink); `ls ~/.paperclip/cli/installs/` is empty.
- Server: `{"error":"Internal server error"}` on `/`, `/chat`, `/<COMPANY>/projects/...` while `/api/health` and `/api/companies` return 200. `journalctl --user -u paperclipai.service` shows `ENOENT … @paperclipai/server/ui-dist/index.html`.

Why the split: the API modules are already loaded in memory, but the UI `index.html` is read **per request** (`readBrandedStaticHtml`), so only the UI path touches the deleted tree.

## 3. Repair

```bash
D=$(python3 -c "import json;print(json.load(open('$HOME/.paperclip/cli/install.json'))['payloadPath'])")
mkdir -p "$D"
npm install --prefix "$D" --no-audit --no-fund --prefer-offline paperclipai@<version from install.json>
```

Verify: `ls "$D/node_modules/@paperclipai/server/ui-dist/index.html"`, then `paperclipai --version` (prints `… (managed npm pinned; payload …)`), then re-request `/` — **200 without restarting the service**, so an in-flight agent run is not disturbed. The embedded-postgres binary lives under the same payload: restore it *before* any restart, or the next start fails to find its postgres binary.

Why a payload can vanish: an interrupted or failed auto-update. `~/.paperclip/cli/update-check.json` records the `latest` version while `install.json` stays `channel: pinned`; `instances/<id>/hot-restart-report.json` records the last hot restart (`previousServerPid`, `newServerPid`, `lostRunIds`). Treat a version change as a deliberate operation: install, then `paperclipai service restart` (hot restart preserving active runs) at a quiet moment.

## 4. Database and backups

`instances/<id>/config.json` is the source of truth: `database.mode = embedded-postgres`, `embeddedPostgresDataDir`, `embeddedPostgresPort` (e.g. 54329), plus `database.backup.{enabled,intervalMinutes,retentionDays,dir}`. Backups land as `paperclip-<YYYYMMDD-HHMMSS>.sql.gz` under `instances/<id>/data/backups/`.

For read-only inspection prefer the HTTP API on `127.0.0.1:3100` — no auth in `local_trusted` mode: `/api/health`, `/api/companies`, `/api/companies/<companyId>/projects`, `/api/projects/<id>`.

`psql` also works when you need a set-based check the API does not expose: the embedded instance accepts the package's **default `paperclip` role and password** over `127.0.0.1:<embeddedPostgresPort>` (export `PGPASSWORD`; `pg_hba.conf` demands a password on every local and host connection). That credential is not in the server env (`/proc/<pid>/environ` carries no PG/DATABASE vars) nor in `config.json`, so use the default and never print it.

Schema trap worth auditing: there is **no composite FK** on `(company_id, project_id)` (nor on goals), so an issue can reference another company's project and link **silently**. Detect with:

```sql
select i.identifier, i.company_id, p.company_id
  from issues i join projects p on p.id = i.project_id
 where i.project_id is not null and i.company_id <> p.company_id;
```

Expect 0 rows. A 500 with `23503` on `issues_project_id_projects_id_fk` instead means the referenced id does not exist at all.

Before any risky company/project surgery, confirm a fresh backup exists in `data/backups/` and note its filename in the report.

## 5. Company/project scoping diagnostics

```bash
P="node $HOME/.paperclip/cli/current/node_modules/paperclipai/dist/index.js"
$P company list                                  # all companies + ids
$P project list -C <companyId>                   # scoped list; without -C it errors "Company ID is required"
$P project get <name|id> -C <companyId>          # without -C: API error 500 / 404
curl -sS http://127.0.0.1:3100/api/companies/<companyId>/projects
curl -sS http://127.0.0.1:3100/api/projects/<projectId>
```

A project that appears in one scope and fails in another is a scoping artifact, not a corrupt row. Activating a greenfield project is then just `project update <id> -C <companyId> --status in_progress --lead-agent-id <agentId>` plus attaching its issues with `issue update --project-id <id>` (`issue get`/`issue update` take no `-C` — the issue carries its company).

## 6. Auth, API tokens, and permissions

- `auth login` starts a local sign-in flow; `auth whoami`
- `auth revoke-current` invalidates the current session
- The default instance in `local_trusted` mode serves the API bound to `127.0.0.1:3100`. In `authenticated` mode, the API is exposed on the public port and requires auth via `API_KEY` or JWT
- `admin user list/promote/demote` operates on platform-level users
- `admin user company-access` shows which companies a user belongs to; `company-access:update --payload-json` modifies it

## 7. Hot restart details

`paperclipai service restart`:
- Preserves active agent runs; the new server process adopts their state
- `--wait` drains active runs before shutting down (safer, slower)
- `--expected-version <version>` verifies the restarted server reports the expected version
- Writes `instances/<id>/hot-restart-report.json` with full before/after state
- `lostRunIds` lists runs that could not be preserved (should be empty in normal conditions)

## 8. Channels and version management

`paperclipai channels --json` shows available channels: `stable`, `beta`, `nightly`, `canary`. Each entry includes version and audience info.

Version is managed through the install channel. A version change is a deliberate operation:
1. `paperclipai health --json` → current `serverVersion`
2. `paperclipai channels --json` → available versions
3. Change channel if needed (requires restart to take effect)
4. `paperclipai service restart` after channel change

## 9. Doctor checks reference

`paperclipai doctor` runs diagnostic checks including:
- Config file validity
- Deployment mode check
- JWT secret presence (authenticated mode)
- Secrets adapter availability
- Storage path permissions
- Database connectivity
- LLM configuration
- Log directory permissions
- Port accessibility
- Node.js version
- Managed install verification
- Service status

`--repair --yes` attempts automatic repair for fixable issues. Use cautiously and verify post-repair.

## 10. Skills home isolation rules

The shared skills home (`~/.claude/skills` for OpenCode, `~/.hermes/skills` for Hermes) must follow strict isolation:

| Scope | Home | Rule |
|---|---|---|
| org-wide | tap → company library → shared home symlinks | one copy, versioned, refreshable |
| project-specific | `.agents/skills/` inside repo | scoped to project directory |
| company-private | shared home with prefixed name | avoids cross-company collisions |
| user / Hermes-only | `~/.hermes/skills` | never in `~/.claude/skills` |

Only symlinks in `~/.claude/skills`. A directory → `state=external` and Paperclip stops managing it. Collisions with the same hash are benign; different content under one name is the real leak.