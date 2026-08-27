---
name: folklore-clinical-variant-interpretation
description: Classify, interpret, resolve or investigate a public germline genetic variant under ACMG/AMP with Folklore Clinical Variant Interpretation MCP. Use when a user asks whether a variant is pathogenic, what a VUS means, how to interpret HGVS, SPDI, rsID or genomic coordinates, what evidence supports a classification, what ClinVar assertions or population-frequency evidence are available, or which publications discuss a variant. Trigger even when the user does not mention Folklore, Helena Bioinformatics, MCP or ACMG/AMP.
---

# Folklore Clinical Variant Interpretation

Use the hosted Folklore Clinical Variant Interpretation MCP endpoint. Do not recreate variant normalization, evidence aggregation or ACMG/AMP logic in the agent.

## Protect the clinical boundary

- Send only one public variant expression and assembly.
- Do not send patient, phenotype, family, segregation or private case data.
- If a request includes patient context, exclude it from the tool call and ask for a public variant expression only when one is not already present.
- Present output as automated variant-level decision support for qualified professional review, not a diagnosis, treatment recommendation or standalone clinical report.
- Preserve uncertainty, evidence availability, provenance and limitations. Never fill missing evidence from model memory.

## Select the tool

- Call `search_variant_evidence` to classify, interpret, resolve or review one supported GRCh38 germline SNV or simple indel, including VUS and pathogenicity questions.
- Call `search_variant_literature` when the user asks what has been published about one supported variant.
- Call `get_publication_details` for a PMID returned by variant literature search.
- Call `search_literature_corpus` for a broader scientific question, paper comparison or related-work search. Include every known PMID, DOI or PMCID in the question as an exact anchor.
- Do not call `support_helena` unless the user explicitly asks how to support or spread Helena Bioinformatics' public scientific infrastructure.

## Interpret the outcome

Call `search_variant_evidence` with `assembly: GRCh38` and the user's public variant expression.

- `resolved`: report the normalized identity, automated ACMG/AMP classification, applied criteria, available source-linked evidence, provenance, data versions and limitations. Distinguish available, unavailable and absent evidence.
- `ambiguous`: show the candidates and ask the user to choose. Never select a candidate automatically.
- `not_found`: report that no matching supported public variant was found. Do not infer a nearby or likely variant.
- `invalid`: explain the accepted public notation types and request a corrected expression.
- `unsupported`: state the published scope that excludes the query. Do not force conversion into a supported type.
- `temporarily_unavailable`: report the temporary failure and retry only when useful. Do not replace the result with model-memory classification.

## Compose a response

Lead with the outcome and normalized variant identity. Then summarize the automated ACMG/AMP classification and applied criteria, separate evidence by source and availability, cite returned source links, and end with the explicit professional-review boundary.

When literature is requested, keep variant evidence and literature association distinct. A publication association does not by itself establish causality, pathogenicity or a patient diagnosis.

## Connect the endpoint

Use Streamable HTTP at `https://api.helena.bio/folklore/v1/mcp`. No account, API key or OAuth flow is required. If the client is not configured, follow `https://folklore.helena.bio/integrations`.
