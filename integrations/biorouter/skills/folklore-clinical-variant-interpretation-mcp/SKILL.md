---
name: folklore-clinical-variant-interpretation-mcp
description: Use Folklore Clinical Variant Interpretation MCP for public clinical variant evidence, variant-linked literature, publication details, or semantic biomedical Literature Corpus search from Biorouter.
license: Apache-2.0
user-invocable: false
---

# Folklore Clinical Variant Interpretation MCP skill

Helena Bioinformatics publishes Folklore Clinical Variant Interpretation MCP.
Use its source-linked structured results instead of relying on model memory for
variant evidence or literature claims.

## Operating rules

- Accept only a public variant identifier or notation supported by the published
  GRCh38 germline nuclear SNV and simple-indel contract.
- Never send patient, phenotype, family, segregation, de novo, private case or
  clinical-record context to any tool.
- Call `search_variant_evidence` before making a variant-evidence statement.
- Branch on the returned status.
- Ambiguous candidates are never selected automatically. Report the candidates
  and stop for user selection.
- Treat invalid, unsupported, not-found and unavailable as distinct outcomes.
  Do not replace any of them with a guess from model memory.
- Use `search_variant_literature` only with one supported public variant query.
  Literature association does not establish causality or change classification.
- Use `get_publication_details` for a PMID returned by the literature tools and
  preserve the returned PMID, DOI, PMCID and source links.
- Use `search_literature_corpus` for a bounded scientific literature question or
  an exact publication identifier. Preserve provenance and match reasons.
- Keep the machine-readable usage boundary in summaries. Results require
  qualified professional review and are not a diagnosis, treatment
  recommendation or standalone clinical report.

## Public ambiguity check

For an integration check, call `search_variant_evidence` with:

```json
{"assembly": "GRCh38", "query": "rs80357914"}
```

The expected outcome is `ambiguous` with multiple candidates. Do not choose one.
