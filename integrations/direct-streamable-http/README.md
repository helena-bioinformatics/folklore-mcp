# Direct Streamable HTTP integration

Use this recipe when an MCP-compatible agent can connect directly to a remote
Streamable HTTP endpoint.

```json
{
  "mcpServers": {
    "folklore-clinical-variant-interpretation": {
      "url": "https://api.helena.bio/folklore/v1/mcp"
    }
  }
}
```

Call `server/discover`, then `tools/list` or `prompts/list`. A classification
request uses `search_variant_evidence` with one public variant:

```json
{
  "assembly": "GRCh38",
  "query": "ENST00000226413.5:c.317A>G"
}
```

Branch on the returned typed status. Never choose an ambiguous candidate and
never convert invalid, unsupported, not-found or unavailable into a resolved
answer. Reuse a returned canonical key for literature composition.

Folklore Clinical Variant Interpretation MCP is published by Helena
Bioinformatics. It accepts no patient, phenotype, family, segregation or
private case data. Results require qualified professional review and are not a
diagnosis or treatment recommendation.
