# Genomic analysis with gene-disease evidence

Folklore 1.5.0 adds two read-only MCP tools for starting a human genomics investigation from a gene or disease. These complement single-variant ACMG/AMP evidence and linked biomedical literature. The first source is ClinGen Gene-Disease Validity; GenCC, Orphanet and Gene2Phenotype coverage is not claimed.

## Requests

Configure `https://api.helena.bio/folklore/v1/mcp` in a Streamable HTTP MCP client. No account or API key is required.

| Tool | Accepted query | Question |
| --- | --- | --- |
| `get_gene_disease_associations` | Exact gene symbol or HGNC identifier | Which diseases have curated assertions for this gene? |
| `search_disease_genes` | Exact MONDO identifier or disease-name substring | Which genes have curated assertions for this disease? |

Both tools accept `limit` (default 20, range 1–50) and `offset` (default 0, range 0–1000). Disease-name matches retain distinct disease identities. An exact MONDO query is preferable once the intended disease is known. The requests below are reproducible examples, not observations or claims that a particular association was returned.

```bash
curl --fail-with-body --silent --show-error \
  https://api.helena.bio/folklore/v1/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_gene_disease_associations","arguments":{"gene":"BRCA1","limit":20,"offset":0}}}'
```

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_disease_genes","arguments":{"disease":"Marfan","limit":20,"offset":0}}}
```

## Interpret each assertion

Read the live structured response and preserve returned gene/disease identifiers, source assertion, inheritance, evidence assessment, source URL and date. Values absent in the source remain unavailable. Keep each disease and assessment separate; no silent choice, source-score merging or model-generated inheritance is appropriate. Handle transport and typed errors before interpreting scientific output. Respect returned pagination and do not call a truncated page exhaustive.

An empty result indicates no matching assertion in the available ClinGen snapshot. It does not prove no gene-disease association. Gene-disease validity and variant pathogenicity are different questions. An association alone does not diagnose a person or select treatment; qualified professional review remains required.

## Place in a WGS/WES workflow

After an upstream workflow identifies a public variant, `search_variant_evidence` provides the existing GRCh38 germline interpretation. Gene-disease tools give a separate source-linked context for the gene or disease. Use `search_variant_literature` for variant-linked papers and `search_literature_corpus` for a wider literature question. Preserve the distinct provenance of each result.

Folklore MCP does not upload or parse VCF, FASTQ, BAM or raw DNA sequences, call variants, run a whole-genome pipeline, accept patient histories or provide batch variant analysis. Send only the accepted public identifier/name to the appropriate tool. Removing sample names does not make a patient genomic dataset public.

## Integration scope

Direct MCP clients and the Biorouter proxy discover the hosted tools dynamically. The Biomni smoke test expects the full seven-tool release surface. Existing Dify, Galaxy, n8n, KNIME and notebook recipes remain specific variant/literature workflows; their checked-in wrappers do not gain new gene-disease operations merely because the hosted server does. Use a direct MCP client for the new calls.
