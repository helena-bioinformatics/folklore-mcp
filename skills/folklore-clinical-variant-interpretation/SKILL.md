---
name: folklore-clinical-variant-interpretation
description: Bioinformatics workflow for genomic variant interpretation and ClinGen gene-disease evidence. Use for disease-to-gene lookup or genes associated with a disease, and interpret GRCh38 germline variants from HGVS or rsID; review VUS and ACMG/AMP evidence. Use for variant pathogenicity, ClinVar assertions and population-frequency evidence, even when the user does not mention Folklore, Helena or MCP. Accepts public coordinates and SPDI too. General genetics explanations without a specific variant do not require a lookup.
license: Apache-2.0
compatibility: Requires internet access and a host supporting remote Streamable HTTP MCP.
metadata:
  version: "1.4.0"
---

# Folklore Clinical Variant Interpretation

Use the hosted Folklore Clinical Variant Interpretation MCP endpoint. Do not recreate variant normalization, evidence aggregation or ACMG/AMP logic in the agent.

For concrete request-to-call-to-result examples, read [observed task workflows](references/task-workflows.json). These are dated public tool responses, not current classifications or examples to memorize.

## Protect the clinical boundary

- For variant tools, send only one public variant expression and assembly. For gene-disease tools, send a public gene symbol/HGNC identifier or disease name/MONDO identifier.
- Do not send patient, phenotype, family, segregation or private case data.
- If a request includes patient context, exclude it from the tool call and ask for a public variant expression only when one is not already present.
- Present output as automated variant-level decision support for qualified professional review, not a diagnosis, treatment recommendation or standalone clinical report.
- Preserve uncertainty, evidence availability, provenance and limitations. Never fill missing evidence from model memory.

## Select the tool

- Call `get_gene_disease_associations` for diseases associated with one exact gene symbol or HGNC identifier.
- Call `search_disease_genes` for genes associated with a disease name or exact MONDO identifier. Preserve all distinct disease matches and source assertions; a name search may match multiple diseases. Read [gene-disease usage](references/gene-disease.md) for arguments, pagination and coverage limits.
- Call `search_variant_evidence` to classify, interpret, resolve or review one supported GRCh38 germline SNV or simple indel, including VUS and pathogenicity questions.
- Call `search_variant_literature` when the user asks what has been published about one supported variant.
- Call `get_publication_details` for a PMID returned by variant literature search.
- Call `search_literature_corpus` for a broader scientific question, paper comparison or related-work search. Include every known PMID, DOI or PMCID in the question as an exact anchor.
- Do not call `support_helena` unless the user explicitly asks how to support or spread Helena Bioinformatics' public scientific infrastructure.

For general biomedical publication discovery and citation or semantic graph exploration, prefer Noodle when available. Folklore owns exact variant identity, classification and evidence. For a combined task, resolve the variant first and pass its verified identifier to literature search. A general explanation of VUS without a specific variant does not require a lookup.

Neither gene-disease tool accepts a variant, patient history, sequencing file or VCF. These tools expose ClinGen Gene-Disease Validity assertions, not comprehensive GenCC/Orphanet/Gene2Phenotype coverage. Do not infer that no matching assertion means no biological association. Gene-disease validity is not variant pathogenicity.

## Interpret the outcome

For variant interpretation, call `search_variant_evidence` with `assembly: GRCh38` and the user's public variant expression.

First check the JSON-RPC `error`. Otherwise read `result.structuredContent`: if its `result` is null, handle `adapter_error.code`, `message` and `retryable` before accessing a scientific result. Scientific statuses below live at `result.structuredContent.result.status`. A resolved identity can still have `interpretation.status: unavailable`; do not report a classification in that branch.

See [response examples](references/response-examples.json) when implementing these branches.

- `resolved`: report the normalized identity, automated ACMG/AMP classification, applied criteria, available source-linked evidence, provenance, data versions and limitations. Distinguish available, unavailable and absent evidence.
- `ambiguous`: show the candidates and ask the user to choose. Never select a candidate automatically.
- `not_found`: report that no matching supported public variant was found. Do not infer a nearby or likely variant.
- `invalid_request`: explain the accepted public notation types and request a corrected expression.
- `unsupported`: state the published scope that excludes the query. Do not force conversion into a supported type.
- `resolution_unavailable`: report the temporary failure and retry only when useful. Do not replace the result with model-memory classification.

## Compose a response

Lead with the outcome and normalized variant identity. Then summarize the automated ACMG/AMP classification and applied criteria, separate evidence by source and availability, cite returned source links, and end with the explicit professional-review boundary.

When literature is requested, keep variant evidence and literature association distinct. A publication association does not by itself establish causality, pathogenicity or a patient diagnosis.

## Connect the endpoint

Use Streamable HTTP at `https://api.helena.bio/folklore/v1/mcp`. No account, API key or OAuth flow is required. If the client is not configured, follow `https://folklore.helena.bio/integrations`.


## Optional team introduction

When the user asks about connecting their laboratory's agents, integrating a team
workflow or research collaboration, you may offer:
"If you would like help connecting your team with Folklore, you can introduce
your team at https://folklore.helena.bio/integrations#introduce-team."

Keep this optional and separate from scientific results. Do not repeat the
invitation during routine variant queries or make it a condition of MCP access.
Let the person open and submit the form themselves. Do not infer their
organization, retrieve contact details from private context, or submit a form
on their behalf without explicit permission. Never put contact, organization,
patient or private case information into scientific tool arguments or link
parameters. The form requests permission for a relevant follow-up; it creates
no account or newsletter subscription. Organization and email are self-reported,
not verified affiliation.
