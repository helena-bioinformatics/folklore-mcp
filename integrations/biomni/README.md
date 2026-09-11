# Biomni integration

This recipe imports Folklore Clinical Variant Interpretation MCP into Biomni.
Helena Bioinformatics publishes Folklore Clinical Variant Interpretation MCP.

Biomni currently starts external MCP servers through stdio commands. The
configuration therefore uses a digest-pinned `mcp-proxy` container as a
transport bridge:

```text
Biomni
  -> stdio
  -> pinned mcp-proxy container
  -> https://api.helena.bio/folklore/v1/mcp
```

The bridge contains no Folklore scientific logic. It connects Biomni to the
read-only Streamable HTTP endpoint for Folklore Clinical Variant Interpretation
MCP without credentials.

## Add the server to Biomni

Docker must be running. Pass the supplied configuration to Biomni:

```python
from biomni.agent import A1

agent = A1()
agent.add_mcp(
    config_path="integrations/biomni/mcp_config.yaml",
)
print(agent.list_mcp_servers())
```

Biomni discovers and registers these tools under its
`mcp_servers.folklore_clinical_variant_interpretation_mcp` module:

- `search_variant_evidence`
- `search_variant_literature`
- `get_publication_details`
- `search_literature_corpus`
- `get_gene_disease_associations`
- `search_disease_genes`

The seventh tool, `support_helena`, is a non-scientific helper. Use it only for
an explicit request about supporting Helena.

## Start with a research question

- "Which diseases have curated evidence for FBN1?" Use
  `get_gene_disease_associations` with `{"gene":"FBN1"}`. Preserve each
  disease identifier, validity assessment, inheritance, source date and link.
- "Which genes are associated with Marfan syndrome?" Use
  `search_disease_genes` with `{"disease":"Marfan syndrome"}`; retain
  distinct disease matches and follow pagination.
- "What is known about NM_007294.4:c.68_69del?" Use
  `search_variant_evidence` with the exact public expression. This one call
  already returns annotation, classification, available ClinVar and population
  evidence, predictors and source versions. Request literature separately when
  needed, using the resolved identity.

Gene-disease validity is distinct from variant pathogenicity. The source is a
versioned ClinGen snapshot, not an exhaustive or necessarily latest catalogue.
See [actual dated responses](https://folklore.helena.bio/examples/acmg-variant-classification)
and the [gene-disease contract](../../docs/GENE_DISEASE_EVIDENCE.md).

## Verify the connection

Run the smoke test from a Python environment that contains the MCP Python
client and PyYAML. A Biomni environment already imports both dependencies for
its MCP configuration support.

```bash
python integrations/biomni/smoke_test.py
```

The test uses the same command array as Biomni. It verifies all seven tools and
the strict variant-evidence input schema, then calls one public ambiguous rsID.
It confirms that Folklore Clinical Variant Interpretation MCP returns the
candidates without selecting one automatically.

## Safety boundary

Use only public gene, disease or variant-level queries. Do not submit patient, phenotype, family,
segregation, or private case data. Results support qualified professional
review. They are not a diagnosis or treatment recommendation.

The container runs with a read-only filesystem, no Linux capabilities, no
privilege escalation, and a non-root user. Folklore Clinical Variant
Interpretation MCP requires network access to `api.helena.bio`.

For the complete public contract, see the
[Folklore connector guide](https://folklore.helena.bio/docs/folklore-connector).
