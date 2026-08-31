# Folklore for KNIME Analytics Platform

This integration turns a table of supported public GRCh38 germline variants
into structured Folklore evidence results. It delegates all resolution,
evidence aggregation and ACMG/AMP logic to the canonical public service.

## Build the workflow

1. Create a one-column input table named `variant`; HGVS, supported rsID, or
   GRCh38 genomic notation can be used.
2. Add a **Python Script** node and connect the table to input port 0.
3. Configure a KNIME Python environment with `pyarrow`; the remaining imports
   are from Python's standard library.
4. Paste `knime_node.py` into the node and execute it.
5. Expand or parse the `folklore_result_json` output column downstream.

No account or API key is required. Do not submit patient, phenotype, family or
private case data. Results require qualified professional review and are not a
diagnosis or treatment recommendation.

The script uses MCP protocol `2026-07-28` and
`https://api.helena.bio/folklore/v1/mcp`.
