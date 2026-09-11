# Integrate Folklore genomic evidence into an AI workflow

Folklore supplies the evidence and interpretation stage of human genomic analysis:
one already identified GRCh38 germline variant, a public gene, or a disease query.
It is a hosted, read-only MCP with no account or API key requirement.

Endpoint: `https://api.helena.bio/folklore/v1/mcp`

## Select the task

| User question | Tool | Public input |
| --- | --- | --- |
| What is known about this genetic variant? | `search_variant_evidence` | `{"assembly":"GRCh38","query":"NM_007294.4:c.68_69del"}` |
| Which diseases are associated with this gene? | `get_gene_disease_associations` | `{"gene":"FBN1"}` |
| Which genes are associated with this disease? | `search_disease_genes` | `{"disease":"Marfan syndrome"}` |
| Which papers discuss this variant? | `search_variant_literature` | Use the canonical identity returned by variant evidence; inspect the tool schema. |

The variant response already contains annotation, automated classification and
criteria, available ClinVar assertions, expert evidence, population frequencies,
predictors, source versions and explicit missing-data states. The gene-disease
tools preserve individual ClinGen assertions, including disputed assessments.
These are distinct evidence types; a gene-disease association does not classify
a variant. Literature links do not establish causality.

## Connection options

- [Hosted client setup](https://folklore.helena.bio/integrations)
- [Biomni stdio bridge and smoke check](../integrations/biomni/README.md)
- [Compatibility and protocol contract](COMPATIBILITY.md)
- [Schemas and coverage for gene-disease evidence](GENE_DISEASE_EVIDENCE.md)
- [Actual dated response examples](https://folklore.helena.bio/examples/acmg-variant-classification)

Discover tools dynamically. The release 1.5.0 surface has six scientific tools
plus `support_helena`, a non-scientific helper that is only appropriate when the
user explicitly asks about supporting Helena. Preserve transport errors,
ambiguity, pagination and unavailable evidence rather than substituting guesses.

## Integration scope

The public MCP does not accept sequencing files, VCF uploads, patient histories
or private case data. It does not perform variant calling or whole-genome batch
analysis. Results support qualified professional review.

This package is maintained by Helena Bioinformatics. A working client recipe
does not mean an upstream platform has endorsed or bundled Folklore. The Biomni
proposal is tracked in [issue 331](https://github.com/snap-stanford/Biomni/issues/331).
Other aggregators can use the same hosted endpoint and public contracts; their
acceptance and client compatibility must be verified separately.
