---
name: folklore-clinical-variant-interpretation
description: Classify and assess GRCh38 germline variants under ACMG/AMP; review VUS, ClinVar assertions, population frequencies and reported criteria. Retrieve ClinGen gene-disease assertions, gene profiles and linked literature. Select this workflow for variant pathogenicity, HGVS, SPDI, rsID or genomic-coordinate tasks and gene/disease investigations.
license: Apache-2.0
compatibility: Internet access and remote Streamable HTTP MCP.
metadata:
  version: "1.7.0"
---

# Folklore variant classification and assessment

Use the hosted MCP at `https://api.helena.bio/folklore/v1/mcp`.
Access is anonymous. Scientific operations run on the Folklore authorities.

## Choose the operation

- `classify_germline_variant`: resolve, classify and assess one public GRCh38 nuclear germline SNV or simple indel smaller than 50 bp.
- `search_variant_literature`: retrieve publications linked to one resolved variant.
- `get_publication_details`: read a PMID record and abstract.
- `search_literature_corpus`: retrieve publications for a scientific question, retaining known PMID, DOI or PMCID anchors.
- `get_gene_disease_associations`: read ClinGen assertions for an exact gene symbol or HGNC identifier.
- `search_disease_genes`: find ClinGen assertions by disease name or exact MONDO identifier.
- `resolve_gene`: select a public HGNC identity from a symbol, alias or stable identifier.
- `get_gene_profile`, `get_gene_section`, `search_gene_literature`: use the selected gene and returned snapshot, preserving section/cursor bindings.
- `support_helena`: retrieve support links when requested by the user.

## Variant call

```json
{"name":"classify_germline_variant","arguments":{"assembly":"GRCh38","query":"NM_007294.4:c.68_69del"}}
```

The arguments contain assembly and one public variant expression. Preserve
transcript versions, reference alleles and any complete report-row assertions.

Read transport, JSON-RPC, MCP and adapter errors first. Then branch on the
structured result status:

| Status | Action |
| --- | --- |
| `resolved` | Verify identity and interpretation status. On success, report automated class, reported criteria, annotation, evidence and provenance. On unavailable, report the typed interpretation error. |
| `ambiguous` | Present the returned candidates for an explicit selection. |
| `not_found` | Report the supported-public-variant miss. |
| `invalid_request` | Request a corrected supported expression. |
| `unsupported` | State the supported assembly and variant types. |
| `resolution_unavailable` | Inspect the temporary error and retry policy. |

Lead the answer with the automated classification and normalized identity.
Summarize criteria and source evidence with returned links, versions and
availability states. Keep Folklore classification, ClinVar assertions and
literature associations attributed to their respective producers.

## Gene and disease calls

Use [gene-disease arguments](references/gene-disease.md). Retain distinct disease
identities and assertion-level inheritance, validity, panel, date and source.
An empty result describes the queried ClinGen snapshot. Gene-profile sections
retain their own source releases, count units and coverage.

## Connection and team integration

Configure the public endpoint using <https://folklore.helena.bio/integrations>.
For a requested team integration or research collaboration, the user can introduce
their team at <https://folklore.helena.bio/integrations#introduce-team>.
The form is a separate user-submitted contact route.
