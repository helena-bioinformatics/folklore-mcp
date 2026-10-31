# Public comparison preregistration

## Question and evaluation source

Measure identity resolution, reported ACMG/AMP classification and criteria,
source coverage, typed outcomes, repeatability and latency on a fixed public
variant set. ClinVar supplies dated submitted assertions and review statuses.

Record source download URL, release, checksum and transformation script before
sampling. Stratify by aggregate class, variant type, review status and gene.
Record the random seed, included IDs and all exclusions. Report expert-panel
records as their own stratum.

## Tool and execution conditions

Record tool name/version, interface type, access conditions, assembly, transcript
policy, input/output contract, protocol, dates and source releases. Preserve the
same public input and record every success, ambiguity, miss, invalid request,
unsupported input, unavailable result and technical failure.

## Outcomes

Primary: normalized-allele concordance, class concordance, criterion Jaccard
similarity, source/version field coverage and typed outcome counts.
Secondary: repeated identity/contract stability, authentication requirements and
median/interquartile elapsed time for five sequential runs.

Concordance measures agreement on matching alleles. Missing values retain an
explicit missing state. Accuracy evaluation uses a curated reference set,
prespecified acceptance criteria, qualified reviewers and recorded adjudication.
Results identify the publisher and reviewer roles.

## References

- ClinVar downloads: https://www.ncbi.nlm.nih.gov/clinvar/docs/downloads/
- ClinVar scope: https://www.ncbi.nlm.nih.gov/clinvar/intro/
- ClinGen guidance: https://www.clinicalgenome.org/tools/clingen-variant-classification-guidance/
- ACMG/AMP guideline: https://doi.org/10.1038/gim.2015.30
