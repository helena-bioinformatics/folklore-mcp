# Changelog

All notable changes to the public Folklore MCP adapter are documented here.

## 1.2.2 - 2026-08-13

- Published the Folklore MCP adapter as a standalone Apache-2.0 project.
- Added complete discovery metadata for the hosted MCP endpoint and its three tools.
- Documented the MCP 2026-07-28 Streamable HTTP transport and the intentional absence of an `initialize` method.
- Replaced private service-to-service integrations with calls to the public Folklore APIs at `https://api.helena.bio`.
- Added distribution metadata, container packaging, locked dependencies, CI, security policy, and contribution guidance.
- Preserved the existing pinned registry bridge and added standalone adapter packaging separately as `Dockerfile.adapter`.
- Submitted Folklore to three specialized medical and bioinformatics directories and recorded the pending editorial states under `registry/`.
- Excluded backend interpretation logic, internal routing and authentication, deployment manifests, private data, credentials, and private Git history.
