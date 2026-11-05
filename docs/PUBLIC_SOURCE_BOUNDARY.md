# Public adapter source

This repository implements the Folklore MCP protocol layer and public API
clients. Folklore API services perform normalization, annotation, evidence
aggregation and ACMG/AMP classification.

## Distribution contents

- MCP discovery, JSON-RPC handling, input validation and bounded API clients
- Adapter 2.0.0: eleven anonymous tools and eighteen authenticated case, source
  and result tools, with the existing scientific prompts and App resource
- Self-hosted capability gates and enabled-tool discovery metadata
- Health, readiness and metrics endpoints
- Tests, container packaging, CI and documentation

Private authority implementations, datasets, caches, models, service credentials,
production configuration and unrelated platform source remain in their owning
repositories. Discovery metadata describes the enabled hosted surface.

## Data flow

Anonymous tool schemas define variant, gene, disease and literature arguments.
Authenticated schemas define admitted case/source/result operations. Literature
queries include public phenotype, HPO and OMIM terms. API clients send those
arguments to the public Folklore endpoints. Self-hosted operators configure
logging and retention for their own instances.

## Release checks

1. Run the test and lint suite.
2. Scan tracked source and the commit range for credentials and internal markers.
3. Validate example payloads against the public schemas and reference fixtures.
4. Verify API and discovery contracts.
5. Publish the clean public adapter source and its required license notices.

## Hosted 2.0 adapter

The Apache adapter includes hosted authentication, bounded case API clients, schemas, encrypted recovery journals and deterministic frozen-export queries. These are transport/result-access functions, not scientific annotation or classification. Exported packets omit private source paths and operational provenance. Synthetic tests contain no actual clinical records. Private production configuration, datasets, receipts and history remain excluded. No local Folklore server is required.
