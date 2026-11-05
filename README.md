# Folklore Clinical Variant Interpretation MCP

One hosted MCP server for public scientific queries and authenticated case workflows.

Endpoint: https://api.helena.bio/folklore/v1/mcp

Version 2.0.0

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/helena-bioinformatics/folklore-mcp/badge)](https://scorecard.dev/viewer/?uri=github.com/helena-bioinformatics/folklore-mcp)
[![AllMCPs Verified](https://allmcps.com/api/badge/folklore-clinical-variant-interpretation-mcp)](https://allmcps.com/mcp/folklore-clinical-variant-interpretation-mcp?verify=930d811d-1fd8-4117-8280-1c6eac1a2ca3)

Connect your MCP client directly to this Streamable HTTP endpoint. No local
Folklore server is required. Anonymous callers receive 11 public tools.
Send your Folklore API key in the Authorization Bearer header to access 18
additional case, source and result tools at the same endpoint. Invalid supplied
credentials fail authentication; they do not select the anonymous catalog.

Create a key in your Folklore account for the selected account and sources.
Keep it in your client's secret store, never in prompts, tool arguments or URLs.
The selected account's native subscription capabilities, usage limits and
eligible credits govern processing. A key does not grant funded compute.

See [case workflows](docs/CASE_WORKFLOWS.md), the
[18 authenticated tool schemas](registry/authenticated-tools.json) and the
[public task recipes](registry/task-contracts.json).

## Classify a variant

Connect your MCP client to:

```text
https://api.helena.bio/folklore/v1/mcp
```

Access is anonymous. Call `classify_germline_variant`:

```json
{"name":"classify_germline_variant","arguments":{"assembly":"GRCh38","query":"NM_007294.4:c.68_69del"}}
```

Input: one public GRCh38 nuclear germline SNV or simple indel smaller than 50 bp.
Accepted notation includes supported HGVS, SPDI, rsID and genomic coordinates.
Preserve transcript versions and reference alleles.

A resolved identity with successful interpretation includes automated ACMG/AMP
classification, reported criteria, annotations, source evidence and provenance.
Submitted ClinVar assertions retain their own source attribution alongside the
Folklore classification. A VUS is a classification outcome.

| Status | Next step |
| --- | --- |
| `resolved` | Read interpretation status, then classification and evidence. |
| `ambiguous` | Present candidates for an explicit allele choice. |
| `not_found` | Report the source-scoped miss. |
| `invalid_request` | Supply a corrected supported expression. |
| `unsupported` | Select a workflow for the requested variant type or assembly. |
| `resolution_unavailable` | Inspect the typed error and retry policy. |

Interpretation status is `success` or `unavailable`. Transport, JSON-RPC, MCP
and adapter errors have separate fields. See [typed outcomes](docs/TYPED_OUTCOMES.md).

## Scientific tools

| Tool | Operation |
| --- | --- |
| `classify_germline_variant` | Resolve, classify and assess one supported germline variant. |
| `search_variant_literature` | Retrieve publications linked to a resolved variant. |
| `get_publication_details` | Retrieve the bibliographic record and abstract for a PMID. |
| `search_literature_corpus` | Search publications by scientific question or public identifier. |
| `get_gene_disease_associations` | Retrieve ClinGen assertions for an exact gene symbol or HGNC identifier. |
| `search_disease_genes` | Retrieve ClinGen assertions by MONDO identifier or disease-name substring. |
| `resolve_gene` | Resolve a human gene symbol, alias or stable identifier. |
| `get_gene_profile` | Read the selected HGNC gene at its returned snapshot. |
| `get_gene_section` | Continue one profile section using its cursor. |
| `search_gene_literature` | Retrieve a separate live publication capture for the selected gene. |

ClinGen results preserve assertion-level disease identity, inheritance, validity
assessment, panel, date and source links. Profile sections retain provider,
assembly, release, units and pagination. Gene literature has its own capture
identity. Follow [gene-disease](docs/GENE_DISEASE_EVIDENCE.md) and
[gene-profile](docs/PUBLIC_GENE_PROFILES.md) contracts for exact inputs.

`support_helena` provides links to the separate Helena Good service when the
user asks about supporting Helena. An optional MCP App renders variant results.

## Connect an agent or application

The hosted server uses stateless Streamable HTTP and MCP `2026-07-28`.
Requests carry matching protocol metadata and routing headers. Supported methods
include `server/discover`, `tools/list`, `tools/call`, `prompts/list`,
`prompts/get`, `resources/list` and `resources/read`.

- [Direct Streamable HTTP](integrations/direct-streamable-http/README.md)
- [OpenAI Agents SDK](integrations/openai-agents-python/README.md)
- [Biomni](integrations/biomni/README.md)
- [Biorouter](integrations/biorouter/README.md)
- [Dify](integrations/dify/README.md), [n8n](integrations/n8n/README.md),
  [Galaxy](integrations/galaxy/README.md), [KNIME](integrations/knime/README.md)
- [Notebook workflow](integrations/notebooks/README.md)

The [compatibility guide](docs/COMPATIBILITY.md) records protocol/client
observations. All clients sharing egress use the [same rate budget](docs/RATE_LIMITS.md).

## Agent Skill and workflow prompts

Install the [portable Agent Skill](skills/folklore-clinical-variant-interpretation/SKILL.md)
using the [installation guide](docs/AGENT_SKILL.md). It routes pathogenicity,
VUS, ClinVar, population-frequency, gene-disease and literature tasks to the
hosted tools. The skill source includes OpenAI interface metadata.

[Workflow prompts](docs/WORKFLOW_PROMPTS.md) compose tool operations for
classification, VUS assessment, ACMG/AMP explanation, identity verification and
variant-literature comparison. Each accepts one public variant expression.

## Run the adapter

The Apache-2.0 adapter implements MCP transport, public API clients and validated
response projection. Folklore's scientific authorities produce normalization,
annotation, evidence aggregation and classification.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
FOLKLORE_MCP_ENABLED=true \
FOLKLORE_LITERATURE_ENABLED=true \
FOLKLORE_GENE_DISEASE_ENABLED=true \
FOLKLORE_PUBLIC_GENE_ENABLED=true \
folklore-mcp
```

Capabilities are enabled through the flags above. Gene literature requires both
public-gene and literature capabilities. The default upstream is
`https://api.helena.bio`; local contract tests support `localhost` and
`127.0.0.1`. The standalone HTTP image uses `Dockerfile.adapter`; `Dockerfile`
provides the pinned stdio bridge.

## Verify and measure

```bash
pytest
ruff check .
ruff format --check .
python3 ops/reconcile_discovery.py
```

The read-only reconciler compares runtime, Server Card and Official Registry
state, with separate aggregator observations. `python3 ops/public_smoke.py`
checks discovery, prompts and resources.

Public measurement sources:
[variant interpretation](benchmarks/variant-interpretation/README.md),
[100-case agent discovery](benchmarks/agent-discovery/README.md),
[60-query search discovery](benchmarks/search-discovery/README.md) and
[genomic discovery cohort](benchmarks/genomic-discovery/v1/README.md).

## Registry and citation

- Registry name: `io.github.helena-bioinformatics/folklore`
- Publisher: Helena Bioinformatics
- Website: <https://folklore.helena.bio>
- [Task routing metadata](registry/agent-selection.json)
- [Per-tool task contracts](registry/task-contracts.json)
- [Security reporting](SECURITY.md)
- [Source boundary](docs/PUBLIC_SOURCE_BOUNDARY.md)
- [Citation metadata](CITATION.cff)

The immutable MCP adapter 1.6.0 archive is
[10.5281/zenodo.23817704](https://doi.org/10.5281/zenodo.23817704), from signed tag
`folklore-mcp-v1.6.0` at `55a332c6dd6bd4650e921c12ac145b8e0f90476a`.
The Biorouter-tag archive is
[10.5281/zenodo.23818207](https://doi.org/10.5281/zenodo.23818207).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Automated variant classifications support qualified professional review and are not patient diagnoses or treatment recommendations.
