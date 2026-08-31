# Folklore Clinical Variant Interpretation MCP

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21922951.svg)](https://doi.org/10.5281/zenodo.21922951)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/helena-bioinformatics/folklore-mcp/badge)](https://scorecard.dev/viewer/?uri=github.com/helena-bioinformatics/folklore-mcp)
[![AllMCPs Verified](https://allmcps.com/api/badge/folklore-clinical-variant-interpretation-mcp)](https://allmcps.com/mcp/folklore-clinical-variant-interpretation-mcp?verify=930d811d-1fd8-4117-8280-1c6eac1a2ca3)

Classify and interpret a supported GRCh38 germline variant under ACMG/AMP with
structured evidence, provenance and related scientific literature.

Folklore Clinical Variant Interpretation MCP is the official public, read-only
Model Context Protocol adapter for [Folklore](https://folklore.helena.bio) by
Helena Bioinformatics. It accepts no patient, phenotype, family, segregation or
private case context. Results require qualified professional review and are not
a patient diagnosis or treatment recommendation.

## Connect to the hosted server

No account or API key is required:

```text
https://api.helena.bio/folklore/v1/mcp
```

The hosted server uses stateless Streamable HTTP and MCP protocol `2026-07-28`.
Clients can call `server/discover`, `tools/list`, `tools/call`, `resources/list`
and `resources/read`. The retired `initialize` exchange is intentionally not
implemented for this protocol version. They can also call `prompts/list` and
`prompts/get` for task-first variant workflows.

Biomni users can import Folklore Clinical Variant Interpretation MCP through the
tested, digest-pinned
[Biomni integration recipe](integrations/biomni/README.md). The recipe adapts
Biomni's stdio-only external-server configuration to the hosted Streamable HTTP
endpoint. Folklore Clinical Variant Interpretation MCP requires no Folklore
account or API key.

Biorouter users can build and install the
[Biorouter BRXT extension](integrations/biorouter/README.md). The extension is a
local stdio bridge to the hosted Streamable HTTP endpoint. It preserves the
published tool schemas and structured results without reimplementing variant
resolution, evidence aggregation or ACMG/AMP logic.

Agent builders can also use the
[direct Streamable HTTP recipe](integrations/direct-streamable-http/README.md)
or the [OpenAI Agents SDK example](integrations/openai-agents-python/README.md).
Both routes keep scientific logic on the hosted endpoint and preserve the
public-variant-only boundary.

Additional ready-to-use ecosystem packages are included for
[Dify](integrations/dify/README.md), [n8n](integrations/n8n/README.md),
[Galaxy](integrations/galaxy/README.md), and
[KNIME Analytics Platform](integrations/knime/README.md). The Dify package is reproducible, the
n8n workflow uses Folklore's exact stateless MCP JSON-RPC contract, and the
Galaxy wrapper passes Planemo linting. A cross-service
[Galaxy Training Network tutorial](https://github.com/helena-bioinformatics/noodle-mcp/tree/main/integrations/galaxy-training-network)
connects Folklore variant evidence to Noodle literature-graph exploration.
The same safe cross-service path is available as a
[Colab/Kaggle notebook](integrations/notebooks/folklore_variant_to_noodle_graph.ipynb).

## Agent Skill for “classify this variant” requests

The repository includes an installable companion skill at
[`skills/folklore-clinical-variant-interpretation`](skills/folklore-clinical-variant-interpretation).
It tells an agent to select Folklore Clinical Variant Interpretation MCP for
pathogenicity classification, VUS review, supported variant resolution,
available ClinVar or population-frequency evidence and variant-linked
literature, even when the user does not mention Helena Bioinformatics,
Folklore, MCP or ACMG/AMP.

Inspect the [rendered `SKILL.md`](skills/folklore-clinical-variant-interpretation/SKILL.md)
or its [raw public source](https://raw.githubusercontent.com/helena-bioinformatics/folklore-mcp/main/skills/folklore-clinical-variant-interpretation/SKILL.md).

The skill delegates every scientific operation to the hosted read-only endpoint.
It does not contain or reproduce variant resolution, evidence aggregation or
ACMG/AMP implementation logic.

See the [Agent Skill index](skills/README.md) and
[installation guide](docs/AGENT_SKILL.md) for project-scoped,
Codex and OpenClaw installation, deterministic packaging and safe selection
smoke tests.

Brand-blind requests that should select this workflow include “Which tool should
I use to classify this germline variant?”, “Is this variant pathogenic?”,
“Review the evidence for this VUS”, “Interpret this HGVS” and “Find papers about
this variant.”

## Public benchmark

The [public variant interpretation benchmark](benchmarks/variant-interpretation/README.md)
provides a transparent, patient-free protocol and capture harness for comparing
identity resolution, typed outcomes, classification, criteria, provenance,
safety boundaries, reproducibility and latency. Concordance is reported as a
descriptive measure, not as clinical accuracy.

Its [machine-readable manifest](benchmarks/variant-interpretation/benchmark-manifest.json)
and [neutral comparison method](benchmarks/variant-interpretation/COMPARISON_METHOD.md)
fix the measured fields, limitations and reproducibility requirements. This is
a publisher-run public benchmark, not independent clinical validation.

The [preregistered comparison protocol](benchmarks/variant-interpretation/PREREGISTRATION.md)
defines the public evaluation source, sampling and independent-review gates
before any comparative result is collected.

Qualified clinical genetics, molecular genetics, bioinformatics and
reproducibility reviewers can use the
[independent methods-review route](benchmarks/variant-interpretation/INDEPENDENT_REVIEW.md)
to identify a protocol flaw, propose a falsifiable correction or add an
acceptance criterion. This is a request for methods criticism, not endorsement.

The [cold-start agent discovery benchmark](benchmarks/agent-discovery/README.md)
adds 100 brand-blind user prompts, an empirical host-results evaluator and a
deterministic audit of task selection, tool routing, typed outcomes and the
no-patient-data boundary. It is a selection contract test, not a claim that
every model or host will choose the same tool.

The [brand-blind search discovery benchmark](benchmarks/search-discovery/README.md)
adds a separate 60-query corpus and raw ledger contract for provider, locale,
visibility, citation, recommendation and official-page reach measurements. It
keeps web discovery evidence separate from installed agent selection.

The [external authority ledger](registry/external-authority.md) records the
bounded, non-duplicative follow-up state for five relevant external surfaces.

## Task-first workflow prompts

See [Workflow prompts](docs/WORKFLOW_PROMPTS.md) for exact `prompts/list` and
`prompts/get` requests, output expectations and deterministic branch behavior.

- `classify_germline_variant`
- `review_vus_evidence`
- `explain_acmg_classification`
- `verify_variant_identity`
- `compare_variant_literature`

Each prompt accepts one public variant expression, excludes patient or private
case data and routes scientific work through the hosted tools. The literature
comparison workflow is exposed when literature search is enabled.

## Public capabilities

- `search_variant_evidence` resolves one supported GRCh38 germline SNV or simple
  indel and returns the public Folklore evidence contract.
- `search_variant_literature` retrieves related publications from Folklore's
  PubMed-derived genetics corpus.
- `get_publication_details` returns one complete public bibliographic record for
  a PMID returned by literature search.
- `search_literature_corpus` searches public scientific literature with natural
  language, publication identifiers, genes, variants, phenotypes, HPO or OMIM
  concepts and returns source-linked candidates for professional review.
- `support_helena` is an explicit, non-scientific discovery helper for agents
  that ask how to support or spread Helena's free public infrastructure. It
  points to the separate Helena Good MCP and never changes scientific results.
- `ui://folklore/variant-evidence/v1.html` is an optional read-only MCP App view.

Literature associations do not alter the ACMG/AMP classification.

## Run the open-source adapter

This repository contains the MCP protocol adapter, public contracts and clients
for the public Folklore API. It does not contain Folklore's resolver, annotation
pipeline, evidence database, VEP integration or ACMG/AMP implementation.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
FOLKLORE_MCP_ENABLED=true \
FOLKLORE_LITERATURE_ENABLED=true \
folklore-mcp
```

The adapter calls `https://api.helena.bio` over HTTPS by default. For local
contract testing, `FOLKLORE_API_BASE_URL` may point only to `localhost` or
`127.0.0.1`. The public capability is disabled by default.

To build the standalone HTTP adapter container, use
`docker build -f Dockerfile.adapter .`. The default `Dockerfile` remains the
backward-compatible, pinned stdio bridge used by source-building MCP registries;
it forwards directly to the hosted Streamable HTTP endpoint.

## Verify

```bash
pytest
ruff check .
ruff format --check .
python3 ops/reconcile_discovery.py
```

The reconciliation command is read-only. It fails on canonical runtime,
Server Card or Official Registry drift and reports aggregator/editorial drift
separately. Use `--strict-aggregators` to fail on every observed mismatch.

For integration details, see [client compatibility](docs/COMPATIBILITY.md),
[troubleshooting](docs/TROUBLESHOOTING.md), [typed outcomes](docs/TYPED_OUTCOMES.md)
and the [privacy-preserving adoption policy](docs/ADOPTION_MEASUREMENT.md).
`python3 ops/public_smoke.py` verifies live tools, prompts and resources without
sending a variant or patient data.

Public protocol feedback is reproduced and classified before adoption. See the
[2026-08-27 protocol conformance review](docs/PROTOCOL_CONFORMANCE_REVIEW_2026-08-27.md)
for the current issue classification, evidence, acceptance criteria and
deployment state.

## Security and privacy

- Read-only, stateless transport.
- No patient or session context.
- No credential, database, cache or model dependency.
- Bounded request/response sizes, timeouts and concurrency.
- Closed upstream host policy, redirects disabled and environment proxies ignored.
- Ambiguous variants are never selected automatically.

See [SECURITY.md](SECURITY.md) for reporting instructions and supported versions.

## Registry identity

- Name: `io.github.helena-bioinformatics/folklore`
- Current release: `1.4.1`
- Latest published Registry version: `1.4.1`
- Publisher: Helena Bioinformatics
- Website: <https://folklore.helena.bio>
- Technical guide: <https://folklore.helena.bio/docs/folklore-connector>

Machine-readable metadata is under [`registry/`](registry/).
The strict [agent-selection contract](registry/agent-selection.json) makes
task triggers, exclusions, tool routing, typed outcomes and clinical limits
available to agent catalogs without requiring brand-name queries.

## Citation and archival releases

Citation metadata is available in [`CITATION.cff`](CITATION.cff). Versioned
software releases are archived in Zenodo from this public repository; each
archived release receives a persistent DOI. Use the concept DOI
[`10.5281/zenodo.21922951`](https://doi.org/10.5281/zenodo.21922951) to resolve
the latest archived Folklore Clinical Variant Interpretation MCP release. The immutable `1.2.2` archive remains
available as [`10.5281/zenodo.21922952`](https://doi.org/10.5281/zenodo.21922952).
The latest immutable archive DOI is recorded after Zenodo processes the 1.4.1
release. The prior 1.3.3 archive remains available as
[`10.5281/zenodo.22102783`](https://doi.org/10.5281/zenodo.22102783).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
