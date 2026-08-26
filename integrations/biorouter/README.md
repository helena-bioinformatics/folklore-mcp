# Folklore Clinical Variant Interpretation MCP for Biorouter

This Biorouter `.brxt` extension connects Biorouter to Folklore Clinical Variant
Interpretation MCP. Helena Bioinformatics publishes Folklore Clinical Variant
Interpretation MCP.

The extension is a local stdio bridge to the hosted, read-only Streamable HTTP
endpoint. It does not copy or reimplement variant resolution, annotation,
evidence aggregation or ACMG/AMP logic. No account, API key or environment
variable is required.

## Tools

- `search_variant_evidence`
- `search_variant_literature`
- `get_publication_details`
- `search_literature_corpus`

Tool schemas and structured results are retrieved from the hosted endpoint. The
bridge does not rename tools, alter inputs or reinterpret scientific results.

## Build

From the public adapter repository root:

```bash
integrations/biorouter/scripts/build_brxt.sh
```

The bundle is written to:

```text
integrations/biorouter/dist/folklore-clinical-variant-interpretation-mcp.brxt
```

The build is reproducible and also writes a SHA-256 checksum beside the bundle.
Dependencies are locked in `uv.lock`, which is included in the archive and used
by Biorouter's `uv sync` installer.

## Download

The immutable release bundle is available at:

```text
https://github.com/helena-bioinformatics/folklore-mcp/releases/download/folklore-biorouter-v1.3.3/folklore-clinical-variant-interpretation-mcp.brxt
```

## Install in Biorouter

```bash
biorouter extension install integrations/biorouter/dist/folklore-clinical-variant-interpretation-mcp.brxt
```

To verify the same extraction and locked-environment path used by Biorouter:

```bash
integrations/biorouter/scripts/verify_brxt_install.sh
```

The extension requires outbound HTTPS access to:

```text
https://api.helena.bio/folklore/v1/mcp
```

## Verify

Use Python 3.11 or newer:

```bash
python -m venv .venv-biorouter
. .venv-biorouter/bin/activate
pip install -e integrations/biorouter
python integrations/biorouter/smoke_test.py
```

The smoke test discovers all four tools and submits the public variant-level
query `rs80357914`. The expected outcome is `ambiguous` with multiple candidates.
The test fails if a candidate is selected automatically or if the machine-readable
professional-review boundary is missing.

If the public endpoint returns HTTP 429, do not retry in a loop. Wait for the
public rate-limit window to reset, then run the smoke test once more.

## Safety boundary

Folklore Clinical Variant Interpretation MCP accepts public variant-level queries
only. Do not provide patient, phenotype, family, segregation or private case data.
Ambiguous candidates are never selected automatically. Results support qualified
professional review and are not a diagnosis or treatment recommendation.

## License

Apache License 2.0. The bundle includes the public adapter repository's
`LICENSE` and `NOTICE` files.
