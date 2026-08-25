# Folklore Clinical Variant Interpretation MCP

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21922951.svg)](https://doi.org/10.5281/zenodo.21922951)

The official public, read-only Model Context Protocol adapter for
[Folklore](https://folklore.helena.bio) by Helena Bioinformatics.

Folklore Clinical Variant Interpretation MCP gives AI clients structured access to public germline variant
evidence, automated ACMG/AMP decision support, provenance and related literature.
It accepts no patient, phenotype, family or case context and must not be used as
a patient diagnosis or treatment recommendation.

## Connect to the hosted server

No account or API key is required:

```text
https://api.helena.bio/folklore/v1/mcp
```

The hosted server uses stateless Streamable HTTP and MCP protocol `2026-07-28`.
Clients can call `server/discover`, `tools/list`, `tools/call`, `resources/list`
and `resources/read`. The retired `initialize` exchange is intentionally not
implemented for this protocol version.

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
- Release candidate: `1.3.3`
- Latest published Registry version: `1.3.2`
- Publisher: Helena Bioinformatics
- Website: <https://folklore.helena.bio>
- Technical guide: <https://folklore.helena.bio/docs/folklore-connector>

Machine-readable metadata is under [`registry/`](registry/).

## Citation and archival releases

Citation metadata is available in [`CITATION.cff`](CITATION.cff). Versioned
software releases are archived in Zenodo from this public repository; each
archived release receives a persistent DOI. Use the concept DOI
[`10.5281/zenodo.21922951`](https://doi.org/10.5281/zenodo.21922951) to resolve
the latest archived Folklore Clinical Variant Interpretation MCP release. The immutable `1.2.2` archive remains
available as [`10.5281/zenodo.21922952`](https://doi.org/10.5281/zenodo.21922952).
The latest published immutable archive is historical version `1.3.1`, available
as [`10.5281/zenodo.22093164`](https://doi.org/10.5281/zenodo.22093164).
Release candidate `1.3.3` does not have a version DOI yet; its exact DOI will be
recorded only after Zenodo creates the immutable archive.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
