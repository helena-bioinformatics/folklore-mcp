# Folklore Clinical Variant Interpretation MCP

Folklore Clinical Variant Interpretation MCP is the official public, read-only MCP server from [Helena Bioinformatics](https://helena.bio). It interprets supported GRCh38 germline variants using structured Folklore evidence, automated ACMG/AMP variant-level decision support, transparent provenance and related scientific literature.

The server does not provide patient diagnoses or treatment recommendations. Its results are intended for review by qualified genetics professionals.

The service accepts genomic, coding, and protein HGVS expressions. It normalizes the query to GRCh38 and returns the resolved variant, gene and consequence, automated classification, applied evidence codes, ClinVar assertions, population frequency, in-silico and splice predictions, source versions, provenance, limitations, and a link to the public Folklore Variant Details record.

## Connect

- **Endpoint:** `https://api.helena.bio/folklore/v1/mcp`
- **Transport:** Streamable HTTP
- **Authentication:** None
- **Tools:** `search_variant_evidence`, `search_variant_literature`, `get_publication_details`

Example client configuration:

```json
{
  "mcpServers": {
    "folklore": {
      "url": "https://api.helena.bio/folklore/v1/mcp"
    }
  }
}
```

## Registry build

The `Dockerfile` in this repository is a small distribution bridge used by
registries that build and inspect MCP servers from source. It runs a pinned
version of [`mcp-proxy`](https://github.com/sparfenyuk/mcp-proxy) and connects
its standard-input transport to the public Folklore Streamable HTTP endpoint.

The bridge contains no Folklore backend implementation, private data, secrets,
or patient information. Clients that support Streamable HTTP should use the
public endpoint above directly.

## Query

Send one supported germline variant. For example:

```text
ENST00000226413.5:c.317A>G
```

The same variant may be submitted as a supported genomic or protein HGVS expression.

## Response

The tool returns structured, source-backed data suitable for machine use and a rendered Variant Details view for compatible chat clients. Results may include:

- input resolution status and warnings;
- GRCh38 genomic, coding, and protein HGVS;
- gene, transcript, consequence, exon, and identifiers;
- automated ACMG/AMP classification and evidence codes;
- ClinVar significance, review status, and associated conditions;
- gnomAD population frequency;
- in-silico, splice, conservation, and gene-constraint evidence;
- classifier and source-data versions;
- provenance, limitations, and a public Folklore record URL.

## Scope and safety

Folklore provides computational decision support, not a diagnosis. Results must be reviewed by a qualified genetics professional in the relevant clinical context.

The public service accepts one variant query at a time. It does not accept patient records, expose private Helena Bioinformatics systems, or publish backend source code or implementation details.

## Official links

- [Folklore](https://folklore.helena.bio)
- [Helena Bioinformatics](https://helena.bio)
- [Official MCP Registry](https://registry.modelcontextprotocol.io/?q=io.github.helena-bioinformatics%2Ffolklore)
- [Product demonstration](https://www.youtube.com/watch?v=nOrn43cmZLs)

## Contact

[contact@helena.bio](mailto:contact@helena.bio)
