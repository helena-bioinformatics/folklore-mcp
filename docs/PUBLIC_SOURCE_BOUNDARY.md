# Public adapter source

This repository implements the Folklore MCP protocol layer and public API
clients. Folklore API services perform normalization, annotation, evidence
aggregation and ACMG/AMP classification.

## Distribution contents

- MCP discovery, JSON-RPC handling, input validation and bounded API clients
- Adapter 1.7.0: ten scientific tools, an optional support helper, five workflow
  prompts and an optional MCP resource
- Self-hosted capability gates and enabled-tool discovery metadata
- Health, readiness and metrics endpoints
- Tests, container packaging, CI and documentation

Private authority implementations, datasets, caches, models, service credentials,
production configuration and unrelated platform source remain in their owning
repositories. Discovery metadata describes the enabled hosted surface.

## Data flow

Tool schemas define variant, gene, disease and literature arguments. Literature
queries include public phenotype, HPO and OMIM terms. API clients send those
arguments to the public Folklore endpoints. Self-hosted operators configure
logging and retention for their own instances.

## Release checks

1. Run the test and lint suite.
2. Scan tracked source and the commit range for credentials and internal markers.
3. Validate example payloads against the public schemas and reference fixtures.
4. Verify API and discovery contracts.
5. Publish the clean public adapter source and its required license notices.
