# Folklore Galaxy wrapper

Credential-free Galaxy wrapper for the public Folklore Clinical Variant
Interpretation MCP. It preserves resolved, ambiguous, not-found, and bounded
error outcomes without inventing a classification.

Run `planemo lint folklore_mcp.xml` before a ToolShed release. Live use requires
outbound HTTPS access to `api.helena.bio`.

## Optional journey context

See [caller-owned journey context](../JOURNEY_CONTEXT.md) for support,
explicit opt-in, application-owned pseudonyms and conversation/run boundaries.
Connection-only configuration does not supply user identity automatically.
