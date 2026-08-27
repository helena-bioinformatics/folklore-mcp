# Workflow prompts for public variant tasks

Folklore Clinical Variant Interpretation MCP publishes five task-first prompts:

- `classify_germline_variant`: resolve one public variant, retrieve current
  evidence and report automated ACMG/AMP decision support.
- `review_vus_evidence`: review uncertainty and available evidence without
  treating a VUS as pathogenic or benign.
- `explain_acmg_classification`: explain returned criteria and evidence without
  reconstructing unpublished logic.
- `verify_variant_identity`: resolve the identity and stop on ambiguity.
- `compare_variant_literature`: use a resolved identity to retrieve source-linked
  publications while keeping association separate from causality and
  pathogenicity.

Each prompt accepts one required `variant` argument containing a public HGVS,
SPDI, rsID or genomic-coordinate expression. Do not include patient, phenotype,
family, segregation or private case data.

## List the prompts

Send this public, read-only request to
`https://api.helena.bio/folklore/v1/mcp`:

```bash
curl --fail-with-body --silent --show-error \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: prompts/list' \
  --data '{"jsonrpc":"2.0","id":1,"method":"prompts/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}' \
  https://api.helena.bio/folklore/v1/mcp
```

## Render one prompt

Set `Mcp-Name` and the JSON-RPC prompt name to the same published name:

```bash
curl --fail-with-body --silent --show-error \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: prompts/get' \
  -H 'Mcp-Name: classify_germline_variant' \
  --data '{"jsonrpc":"2.0","id":2,"method":"prompts/get","params":{"name":"classify_germline_variant","arguments":{"variant":"ENST00000226413.5:c.317A>G"},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}' \
  https://api.helena.bio/folklore/v1/mcp
```

## Branch on the result

- Continue only when variant identity is `resolved`.
- For `ambiguous`, show the candidates and ask the user to choose.
- For `not_found`, `invalid`, `unsupported` or temporary unavailability, report
  the state directly and do not substitute a nearby variant or model-memory
  classification.
- Preserve the returned identity, applied criteria, source-linked evidence,
  provenance, data versions and limitations.
- End with the qualified-professional-review boundary. The output is not a
  diagnosis or treatment recommendation.
