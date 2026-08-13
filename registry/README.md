# Folklore MCP registry metadata

This directory contains the public discovery metadata for Folklore Clinical
Variant Interpretation MCP.

- `server.json` is the Official MCP Registry document.
- `discovery-contract.json` is the exact desired state used by the read-only
  reconciliation command.
- `directory-submission.md` contains reviewed directory copy and safety claims.
- `packages/` and `platforms/` contain public client configuration examples.

Run from the repository root:

```bash
python3 ops/reconcile_discovery.py
```

The command reads public surfaces only and never submits or changes directory
entries.
