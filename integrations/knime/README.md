# Folklore for KNIME Analytics Platform

This integration turns a table of supported public GRCh38 germline variants
into automated ACMG/AMP classifications, reported criteria and source evidence.
The node calls the hosted classifier for each row.

## Build the workflow

1. Create a one-column input table named `variant`; HGVS, supported rsID, or
   GRCh38 genomic notation can be used.
2. Add a **Python Script** node and connect the table to input port 0.
3. Configure a KNIME Python environment with `pyarrow`; the remaining imports
   are from Python's standard library.
4. Paste `knime_node.py` into the node and execute it.
5. Expand or parse the `folklore_result_json` output column downstream.

Access is anonymous. Input is one public GRCh38 variant expression and assembly.

The script uses MCP protocol `2026-07-28` and
`https://api.helena.bio/folklore/v1/mcp`.

## Optional journey context

Optional analytics configuration: [journey context](../JOURNEY_CONTEXT.md).
