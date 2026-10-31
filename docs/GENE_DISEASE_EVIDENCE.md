# Genomic analysis with gene-disease evidence

Folklore provides two read-only MCP tools for starting a human genomics investigation from a gene or disease. These complement single-variant ACMG/AMP evidence and linked biomedical literature. The source is ClinGen Gene-Disease Validity.

## Requests

Configure `https://api.helena.bio/folklore/v1/mcp` in a Streamable HTTP MCP client. No account or API key is required.

| Tool | Accepted query | Question |
| --- | --- | --- |
| `get_gene_disease_associations` | Exact gene symbol or HGNC identifier | Which diseases have curated assertions for this gene? |
| `search_disease_genes` | Exact MONDO identifier or disease-name substring | Which genes have curated assertions for this disease? |

Both tools accept `limit` (default 20, range 1–50) and `offset` (default 0, range 0–1000). Disease-name matches retain distinct disease identities. An exact MONDO query is preferable once the intended disease is known. The requests below show accepted arguments.

```bash
curl --fail-with-body --silent --show-error \
  https://api.helena.bio/folklore/v1/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' \
  -H 'Mcp-Name: get_gene_disease_associations' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"get_gene_disease_associations","arguments":{"gene":"BRCA1","limit":20,"offset":0}}}'
```

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"search_disease_genes","arguments":{"disease":"Marfan","limit":20,"offset":0}}}
```

## Interpret each assertion

Read the live structured response and preserve returned gene/disease identifiers, source assertion, inheritance, evidence assessment, source URL and date. Values absent in the source remain unavailable. Keep each disease and assessment separate; no silent choice, source-score merging or model-generated inheritance is appropriate. Handle transport and typed errors before interpreting scientific output. Respect returned pagination and do not call a truncated page exhaustive.

An empty result means no matching assertion in the queried ClinGen snapshot. Gene-disease validity assertions and variant pathogenicity classifications have separate contracts.

## Place in a WGS/WES workflow

After an upstream workflow identifies a public variant, `classify_germline_variant` provides the existing GRCh38 germline interpretation. Gene-disease tools give a separate source-linked context for the gene or disease. Use `search_variant_literature` for variant-linked papers and `search_literature_corpus` for a wider literature question. Preserve the distinct provenance of each result.

Variant tools accept one identified public GRCh38 nuclear germline SNV or simple indel smaller than 50 bp. Gene-disease tools accept a public identifier or disease-name substring.

## Integration scope

Direct MCP clients and the Biorouter proxy discover enabled tools dynamically.
The fully enabled source exposes ten scientific tools and a separate support
helper. Client recipes identify the operations exposed by each wrapper.
