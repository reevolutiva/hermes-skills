# Adapter config reference (Paperclip adapters)

This file captures the adapter config shape and the safe checks to read it.

## Common fields

- adapterConfig.model: string (expected `<provider>/<modelId>`)
- adapterConfig.apiBaseUrl: string (expected base URL for gateway)
- adapterConfig.command: optional string (native runner command)
- adapterConfig.cwd: working directory for runs
- adapterConfig.apiKey.secretId: secret reference stored by Paperclip

## Safe inspection

- Use `paperclipai agent configuration <agentId> --json` (redacted) to inspect adapter config.
- Use `agent config-revisions <agentId>` to find the revision that added/changed the secret.
- `paperclipai secrets usage <secretId>` lists references; do not attempt to read the secret value.

## Provider shape

- Providers usually declare a `provider` key with `models` map. Wrong wrapping (e.g. top-level `{"LiteLLM": {...}}`) causes `Model unavailable`.

## Model id rules

- Must contain `/` (e.g. `litellm/gpt-6-luna`).
- If the model uses nested provider notation (e.g. `litellm/azure_ai/gpt-6-luna`) treat the leftmost as the provider and the rest as model id.

## Notes

- Do not rotate secrets without evidence. Use `secrets usage` to confirm references.
- Document any config edits in agent config revision history and create rollbacks when applying quick fixes.
