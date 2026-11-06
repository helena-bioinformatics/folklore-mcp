# Folklore Clinical Variant Interpretation MCP for Biorouter

This Biorouter `.brxt` extension connects Biorouter to Folklore Clinical Variant
Interpretation MCP. Helena Bioinformatics publishes Folklore Clinical Variant
Interpretation MCP.

The 2.0.0 extension connects Biorouter to the hosted Folklore MCP 2.0.0
endpoint over Streamable HTTP. Biorouter discovers the eleven public tools
through the anonymous stdio bridge. Scientific results come from the hosted
service. Keep patient and private case data out of this connection.

For case analysis, the hosted service offers eighteen additional tools to
clients configured with a Folklore Bearer API key. Use the
[Folklore MCP setup guide](https://folklore.helena.bio/integrations/mcp)
to configure an authenticated client.

## Tools

- `classify_germline_variant`
- `search_variant_literature`
- `get_publication_details`
- `search_literature_corpus`
- `support_helena`
- `get_gene_disease_associations`
- `search_disease_genes`
- `resolve_gene`
- `get_gene_profile`
- `get_gene_section`
- `search_gene_literature`

The bridge relays published tool schemas and structured results.

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

The smoke test checks eleven tools and submits the public variant-level
query `rs80357914`. The expected outcome is `ambiguous` with multiple candidates.
The test checks that the ambiguous outcome and returned candidates are preserved.

If the public endpoint returns HTTP 429, do not retry in a loop. Wait for the
public rate-limit window to reset, then run the smoke test once more.

## Inputs and gene profiles

Folklore MCP accepts public variant, gene and disease identifiers and scientific
literature questions. Ambiguous candidates require an explicit selection.

For gene profiles, resolve the identity first and use the selected HGNC gene_id
with the returned identity_snapshot_id as snapshot_id. Keep section continuation
bound to that gene and snapshot; restart resolution after a snapshot conflict.
Preserve each source assertion, coverage and count unit. Live gene literature is
a separate query-matched capture. See [public gene profiles](../../docs/PUBLIC_GENE_PROFILES.md).

## License

Apache License 2.0. The bundle includes the public adapter repository's
`LICENSE` and `NOTICE` files.


## Optional journey context

Optional analytics configuration: [journey context](../JOURNEY_CONTEXT.md).

## Shared request budget

Metadata and scientific POSTs share a six-request burst, refilling one request
per 10.1 seconds within each bridge process. This keeps discovery within
Biorouter's ten-second tool-list timeout while bounding subsequent requests.
A 429 stops later POSTs in that process without automatic replay. Honor
Retry-After before an explicit later reconnect. Separate processes behind the
same egress IP must coordinate their shared allowance. Tool calls can wait
for refill; a limiter is not a guarantee of upstream admission.
