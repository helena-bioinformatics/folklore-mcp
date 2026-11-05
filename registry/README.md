# Folklore MCP distribution

Same endpoint: 11 anonymous public tools and 18 additional authenticated tools.
Supply a Folklore API key in the Authorization Bearer header. No local server
is required. See [case workflows](../docs/CASE_WORKFLOWS.md).

Title: `Folklore Clinical Variant Interpretation MCP`

Description: `ACMG/AMP germline variant classification, gene profiles, disease associations and literature.`

Registry name: `io.github.helena-bioinformatics/folklore`

Endpoint: `https://api.helena.bio/folklore/v1/mcp`

The anonymous catalog defines ten scientific tools and the separate `support_helena`
helper. `classify_germline_variant` resolves and assesses one supported public
GRCh38 nuclear germline SNV or simple indel smaller than 50 bp. The response
includes automated ACMG/AMP classification, reported criteria and source evidence.

Gene-disease tools return ClinGen assertion identities, validity assessments,
inheritance and pagination. Gene profiles use selected HGNC identities and
immutable snapshots. Gene literature returns a separate live capture.

## Distribution files

- `server.json`: Official Registry record.
- `discovery-contract.json`: desired runtime, Server Card and Registry state.
- `agent-selection.json`: task triggers, input scope and tool routes.
- `task-contracts.json`: per-tool inputs, response binding and source definitions.
- `directory-submission.md`: reusable catalogue copy.
- `platforms/client-configs.json`: connection recipes.

Current MCP schemas define executable arguments. Response-bound recipes use
identity, snapshot and cursor values selected from their source response.

## Reconcile and publish

```bash
python3 ops/reconcile_discovery.py
```

The read-only reconciler compares runtime discovery, tools, prompts, resources,
Server Card and Official Registry latest state. Aggregator observations are
reported separately; `--strict-aggregators` includes them in the failure gate.

Registry publication uses the signed tag `folklore-mcp-v<server.json version>`,
the pinned publisher and GitHub OIDC authentication.
The public adapter contains transport, API clients, schemas, tests and packaging.
Folklore scientific authorities own resolution, annotation and classification.
See [source boundary](../docs/PUBLIC_SOURCE_BOUNDARY.md),
[client compatibility](../docs/COMPATIBILITY.md) and
[integration guide](../docs/INTEGRATION_BRIEF.md).