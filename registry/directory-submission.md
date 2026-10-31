# Folklore MCP directory copy

## Identity

- Title: Folklore Clinical Variant Interpretation MCP
- Version: 1.7.0
- Publisher: Helena Bioinformatics
- Category: Bioinformatics, genomics, variant classification
- Tags: ACMG-AMP, germline, variant-classification, gene-disease, literature
- Endpoint: `https://api.helena.bio/folklore/v1/mcp`
- Authentication: anonymous
- Website: `https://folklore.helena.bio`
- Source: `https://github.com/helena-bioinformatics/folklore-mcp`
- Icon: `https://folklore.helena.bio/images/logos/folklore.png`
- Privacy: `https://www.helena.bio/privacy`
- Terms: `https://www.helena.bio/terms`

## Short description

ACMG/AMP germline variant classification, gene profiles, disease associations and literature.

## Full description

Folklore MCP classifies and assesses germline variants under ACMG/AMP.
`classify_germline_variant` returns canonical identity, automated classification,
reported criteria, annotations, source evidence and provenance. Input is one
public GRCh38 nuclear germline SNV or simple indel smaller than 50 bp, expressed
as supported HGVS, SPDI, rsID or genomic coordinates.

Gene tools resolve HGNC identities and provide source-qualified profiles with
snapshot-bound pagination. Gene-disease operations retrieve ClinGen validity
assertions with disease identity, inheritance, panel, assessment, date and source.
Literature tools retrieve variant-linked papers, complete PMID records and
query-matched publications.

All eleven tools are read-only: ten scientific operations and `support_helena`,
a separate support-link helper. Stateless Streamable HTTP provides structured
responses, typed outcomes, workflow prompts and an optional result-viewing app.

## Example tasks

- Classify `NM_007294.4:c.68_69del` under ACMG/AMP and show reported criteria.
- Assess this VUS with source evidence and population frequencies.
- Resolve `rs80357914` and present its candidate alleles.
- Retrieve ClinGen assertions for `FBN1` or `Marfan syndrome`.
- Resolve `BRCA1`, read its gene profile and retrieve linked literature.

## Connection details

MCP protocol: `2026-07-28`. Each request carries matching protocol and routing
metadata. Browser requests use the published HTTPS origin policy. Scientific
responses preserve domain statuses, identity, source versions and pagination.

Security contact: `security@helena.bio`. Privacy contact: `privacy@helena.bio`.
