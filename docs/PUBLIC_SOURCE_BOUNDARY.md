# Public source boundary

This repository contains only the public Folklore MCP adapter. It is a thin,
one-way interface to the public Folklore APIs and does not contain the Folklore
clinical interpretation backend.

## Included

- MCP discovery and JSON-RPC request handling
- Input validation and bounded public API clients
- The three documented MCP tools and one MCP resource
- Health, readiness, and metrics endpoints
- Tests, container packaging, CI, and public documentation

## Intentionally excluded

- Variant normalization, resolution, annotation, evidence aggregation, and ACMG logic
- Private datasets, caches, models, patient data, or case data
- Internal hostnames, network topology, service authentication, or credentials
- Production deployment manifests and operational configuration
- Private repository history and unrelated platform code

The hosted service may evolve independently of this adapter. Consumers should
use discovery metadata rather than relying on undocumented behavior.

## Data handling

The adapter accepts variant-level queries. It must not be used to submit names,
medical-record identifiers, full patient records, or other direct identifiers.
Self-hosted instances send tool inputs to the public Folklore API described in
the README; operators remain responsible for their own logs and retention.

## Release review

Before each public release, maintainers should:

1. run the full test and lint suite;
2. scan the tracked tree and commit range for credentials and internal markers;
3. verify that example payloads are synthetic and contain no patient context;
4. confirm the public API and discovery contracts; and
5. publish from a clean repository without importing private Git history.
