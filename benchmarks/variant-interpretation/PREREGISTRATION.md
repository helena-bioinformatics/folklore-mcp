# Preregistered public comparison protocol

Status: protocol only. No comparative result or superiority claim is made.

## Research question

Under a fixed public-variant-only case set, how do public variant information
and automated classification interfaces differ in identity resolution, explicit
ACMG/AMP criteria, typed failure behavior, provenance coverage,
reproducibility and latency?

## Evaluation set

The primary candidate set is a dated export of public ClinVar GRCh38 sequence
variants with review status and variation identifiers. The source release date,
download URL, checksum and transformation script must be fixed before sampling.
ClinVar is an archive of submitted assertions, not a universal truth set.

An expert-panel subset may be reported separately when the public record has a
ClinGen Variant Curation Expert Panel review status. It must not be mixed with
lower-review-status records without stratification. The benchmark excludes
patient, phenotype, family, segregation and private case data.

## Sampling

Before collection, select strata by five-class aggregate label, variant type,
review status and gene. Publish the random seed and preserve exclusions. Do not
drop an item because a tool returns invalid, unsupported, ambiguous, not found
or unavailable. These are measured outcomes.

## Compared surfaces

Record each tool's public name, version, access date, access conditions,
assembly, input policy and output contract. ClinVar must be labelled as an
archive. A portal, API and automated classifier are separate interface types.
Commercial tools are included only when their terms allow reproducible public
measurement and publication of the stated fields.

## Primary outcomes

1. Exact GRCh38 identity concordance among interfaces that resolve the case.
2. Criterion-level Jaccard similarity among interfaces that return criteria.
3. Exact five-class concordance among interfaces that return a class.
4. Explicit non-resolved outcome rate without guessed identity.
5. Provenance field coverage for source identity, version and retrieval date.

## Secondary outcomes

- Repeat-run identity and contract stability.
- Median and interquartile elapsed time over five sequential runs.
- Public availability and authentication requirements.
- Explicit professional-review, no-diagnosis and no-treatment boundaries.

## Analysis rules

Concordance is descriptive and is not accuracy, clinical validity or
superiority. Different resolved alleles are never compared as classification
disagreement. Missing output is reported as missing, not benign or negative.
Associations in literature are not treated as causality or pathogenicity.

## Independent review gate

Any clinical-accuracy or validation claim requires a qualified independent
reviewer, a prespecified conflict-resolution method and an independently
curated evaluation set. A publisher-run result must retain that label.

## Primary public references

- ClinVar downloads: https://www.ncbi.nlm.nih.gov/clinvar/docs/downloads/
- ClinVar scope: https://www.ncbi.nlm.nih.gov/clinvar/intro/
- ClinGen classification guidance: https://www.clinicalgenome.org/tools/clingen-variant-classification-guidance/
- ClinGen VCEP protocol: https://www.clinicalgenome.org/docs/clingen-variant-curation-expert-panel-vcep-protocol/
- ACMG/AMP 2015 guideline: https://doi.org/10.1038/gim.2015.30
