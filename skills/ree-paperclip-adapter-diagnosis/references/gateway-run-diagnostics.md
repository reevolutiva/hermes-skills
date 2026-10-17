# Gateway run diagnostics reference

Correlate Paperclip run IDs with Hermes `/v1/runs` and admissions recorded
in Hermes state. Use this when a run never emits progress (stuck in `started`
with no events).

1. From Paperclip: `paperclipai agent runtime-state <agentId>` → `lastRunId`,
   `lastRunStatus`, `sessionId`.
2. From Paperclip: `paperclipai issue runs <issueId>` and local run-logs at
   `~/.paperclip/instances/default/data/run-logs/<companyId>/<agentId>/<paperclipRunId>.ndjson`.
3. From Hermes: `GET /v1/runs/<hermesRunId>` (authenticated) → capture `status`,
   `admission_id`, `output`.
4. Inspect `~/.hermes/state.db` table `session_admissions` for rows that match
   `target_session_id` or `admission_id`. Look for `queued|started|unknown` rows
   for the same target — duplicates indicate admission-state corruption.
5. If duplicates/hung admissions exist, discuss cleanup with an operator. The
   safe partial remediation is epoch-bump / restart of dispatch or targeted
   deletion of orphan admissions after creating DB backups.

Verification:
- New run emits events sequentially in Paperclip logs.
- Hermes `/v1/runs` shows progression and `output` grows.
- `activity list` shows `environment.lease_acquired` and comment events for the issue.
