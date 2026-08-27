# Changelog

All notable changes to the public Folklore MCP adapter are documented here.

## Unreleased

- Reject unissued pagination cursors with JSON-RPC `-32602` on the static
  `tools/list`, `resources/list` and `prompts/list` methods, with a first-party
  regression test covering all three public list surfaces.
- Added a Biorouter BRXT extension that bridges Biorouter's local stdio MCP
  interface to the hosted Folklore Clinical Variant Interpretation MCP endpoint.
- Added a Biorouter skill that preserves explicit outcome branching, stops on
  ambiguous variants, excludes patient and case context, and requires qualified
  professional review.
- Added BRXT packaging tests and a live smoke test for the five published tools
  and fail-closed ambiguity behavior.
- Added a reproducible BRXT builder, locked dependencies, a Biorouter-compatible
  install verification and an immutable release-asset workflow with SHA-256.
- Added a tested Biomni configuration that connects to Folklore Clinical
  Variant Interpretation MCP through a digest-pinned, restricted stdio bridge.
- Added a live smoke test for tool discovery, the strict public input contract,
  and explicit preservation of an ambiguous public variant result.

## 1.4.0 - 2026-08-27

- Added the read-only, empty-input `support_helena` discovery helper for agents
  that explicitly ask how to support or spread Helena's free public scientific
  infrastructure.
- Kept all four scientific tools and their evidence, ranking, clinical and
  privacy contracts unchanged; support discovery makes no scientific gateway
  call and is never inserted into scientific results.
- Synchronized runtime, Official MCP Registry, client recipes, Biorouter and
  Biomni tool inventories to the exact five-tool surface.
- Archived the immutable public adapter release in Zenodo as
  [`10.5281/zenodo.22119447`](https://doi.org/10.5281/zenodo.22119447).

## 1.3.3 - 2026-08-25

- Made opaque scientific text an explicit security invariant: marker-like strings
  remain data and cannot, by themselves, prove transport transformation.
- Added variant-contract, publication-gateway and MCP regressions for a payload
  containing a tool-result trimming marker.
- Preserved all scientific behavior, public inputs, output shapes and clinical
  safety boundaries.
- Archived the immutable public adapter release in Zenodo as
  [`10.5281/zenodo.22102783`](https://doi.org/10.5281/zenodo.22102783).

## 1.3.2 - 2026-08-25

- Added parameter-specific descriptions to the input schemas for all four tools,
  including the GRCh38 boundary, the distinction between variant `query` and
  literature `question`, cursor reuse, PMID format, and reusable Folklore
  `canonical_key` syntax.
- Scoped publication-detail misses to Folklore's current PubMed-derived genetics
  corpus while preserving the existing non-retryable `publication_not_found`
  error contract.
- Refined semantic literature instructions so agents pass known PMID, DOI, or
  PMCID identifiers as exact anchors inside the question.
- Preserved every input constraint, response shape, retrieval/ranking rule,
  professional-review boundary, and the public/private source boundary.
- Prepared package, Registry, citation, and Zenodo metadata for release `1.3.2`.
  No version DOI is claimed before the immutable Zenodo archive exists; the
  concept DOI continues to identify the release series.

## 1.3.1 - 2026-08-25

- Added `search_literature_corpus`, a fourth read-only tool for bounded semantic
  search across the public Folklore Literature Corpus.
- Added exact PMID, DOI and PMCID anchors, cursor pagination, deterministic
  sorting, semantic-degradation reporting and source-linked article entities to
  the public response contract.
- Synchronized the public adapter, Official Registry metadata, directory copy,
  citation metadata and discovery contract with the verified hosted server.
- Added a pinned, tag-triggered GitHub OIDC workflow for immutable publication
  to the Official MCP Registry.
- Archived the release in Zenodo as
  [`10.5281/zenodo.22093164`](https://doi.org/10.5281/zenodo.22093164).

## 1.2.2 - 2026-08-13

- Published the Folklore MCP adapter as a standalone Apache-2.0 project.
- Added complete discovery metadata for the hosted MCP endpoint and its three tools.
- Documented the MCP 2026-07-28 Streamable HTTP transport and the intentional absence of an `initialize` method.
- Replaced private service-to-service integrations with calls to the public Folklore APIs at `https://api.helena.bio`.
- Added distribution metadata, container packaging, locked dependencies, CI, security policy, and contribution guidance.
- Preserved the existing pinned registry bridge and added standalone adapter packaging separately as `Dockerfile.adapter`.
- Submitted Folklore to three specialized medical and bioinformatics directories and recorded the pending editorial states under `registry/`.
- Added citation and Zenodo deposition metadata for a versioned, DOI-backed software archive.
- Excluded backend interpretation logic, internal routing and authentication, deployment manifests, private data, credentials, and private Git history.
