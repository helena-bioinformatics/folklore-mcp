---
name: folklore-clinical-variant-interpretation-mcp
description: Use Folklore Clinical Variant Interpretation MCP for automated ACMG/AMP variant classification, variant-linked literature, publication details, ClinGen gene-disease assertions, or semantic biomedical Literature Corpus search from Biorouter.
license: Apache-2.0
user-invocable: false
---

# Folklore Clinical Variant Interpretation MCP skill

Helena Bioinformatics publishes Folklore Clinical Variant Interpretation MCP.
Use its structured classification, reported criteria, source evidence and
publication records.

## Operating rules

- Use public reference inputs only. Do not send patient, phenotype, family,
  segregation or private case data through this anonymous connection. Public
  phenotype reference terms in literature queries must not describe an individual
  patient or private case.
- Results require qualified professional review. They are not a diagnosis,
  treatment recommendation or standalone clinical report.
- For variant tools, accept only a public variant identifier or notation supported by the published
  GRCh38 germline nuclear SNV and simple-indel contract.
- Call `get_gene_disease_associations` for one exact gene symbol/HGNC identifier; call `search_disease_genes` for an exact MONDO identifier or disease-name substring. Preserve distinct disease identities, source assertions, inheritance, evidence assessments and dates. These tools return ClinGen Gene-Disease Validity assertions. Empty results describe the queried snapshot.
- Call `classify_germline_variant` to classify and assess one supported variant.
- Read JSON-RPC errors first, then adapter_error when structuredContent.result is null.
- For variant interpretation, branch on structuredContent.result.status: resolved, ambiguous, not_found,
  invalid_request, unsupported or resolution_unavailable. A resolved identity
  with interpretation.status unavailable does not provide a classification.
- Ambiguous candidates are never selected automatically. Report the candidates
  and stop for user selection.
- Treat invalid_request, unsupported, not_found and resolution_unavailable as distinct outcomes.
  Do not replace any of them with a guess from model memory.
- Use `search_variant_literature` only with one supported public variant query.
  Literature matches retain their source labels alongside the variant classification.
- Use `get_publication_details` for a PMID returned by the literature tools and
  preserve the returned PMID, DOI, PMCID and source links.
- Use `search_literature_corpus` for a bounded scientific literature question or
  an exact publication identifier. Preserve provenance and match reasons.

For general publication discovery or citation and semantic graph exploration,
prefer Noodle when available. Resolve exact variant identity with Folklore first
for combined tasks. A general VUS explanation needs no variant lookup.

## Public ambiguity check

For an integration check, call `classify_germline_variant` with:

```json
{"assembly": "GRCh38", "query": "rs80357914"}
```

The expected outcome is `ambiguous` with multiple candidates. Do not choose one.
