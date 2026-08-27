# Public variant interpretation benchmark

This benchmark measures whether a public variant interpretation interface can
resolve identity, expose evidence, preserve provenance and fail safely. It does
not evaluate patients, diagnosis, treatment or clinical outcomes.

## Research questions

1. Does the interface preserve the exact input, assembly and normalized allele?
2. Does it distinguish resolved, ambiguous, not found, invalid, unsupported and
   unavailable outcomes?
3. For resolved variants, does it expose an automated class, applied criteria,
   evidence availability, source links and data versions?
4. Can a repeated run be tied to the same public contract and source snapshot?
5. Does the response keep variant-level decision support separate from patient
   diagnosis and treatment?

## Case set

`cases.csv` contains public variant expressions only. It deliberately mixes
rsIDs, transcript HGVS and coordinates, including multiallelic identifiers and
invalid or unsupported inputs. A case label describes the input form, not the
expected scientific result.

The case set contains no patient, phenotype, family, segregation or private case
data. Do not add any such data when extending it.

## Folklore baseline

Capture the current public Folklore Clinical Variant Interpretation MCP result:

```bash
python3 benchmarks/variant-interpretation/capture_folklore.py \
  --output folklore-baseline.jsonl
```

The script calls the public read-only endpoint, records one line per case and
does not write raw response bodies. It retains the fields needed for comparison:
status, normalized identity, gene and transcript where returned, automated
class, criteria, evidence availability, provenance versions, safety boundary
and elapsed time. It waits one second between cases by default and uses bounded
retry handling for HTTP 429 responses. Keep the delay enabled on public runs.

## Comparison protocol

The machine-readable [benchmark manifest](benchmark-manifest.json) fixes the
public endpoint, case set, measured fields, metrics and clinical boundary. The
[neutral comparison method](COMPARISON_METHOD.md) explains how to compare an
archive, an automated classifier and an agent-facing API without assuming they
answer the same question.

The [preregistered protocol](PREREGISTRATION.md) fixes the research question,
candidate public evaluation source, sampling dimensions, outcomes and
independent-review gate. Complete
`dataset-manifest.template.json` with the dated public source checksum and seed
before collecting comparative results.

Before running another tool, record:

- tool name, public version and access date;
- exact input and declared assembly;
- supported variant and data scope;
- whether authentication or payment is required;
- normalized genomic allele and transcript context;
- final label and criterion-level output;
- evidence sources, availability states and versions;
- ambiguity, invalid-input and unavailable behavior;
- stated clinical and patient-data boundary;
- elapsed wall time from request to complete result.

Use the same public input for every tool. Do not silently lift over, change a
transcript, choose one allele from an ambiguous rsID, or substitute a nearby
variant. Record unsupported cases as unsupported rather than dropping them.

## Metrics

- Identity concordance: exact agreement on assembly, chromosome, position,
  reference and alternate allele among tools that resolve the case.
- Five-class concordance: exact label agreement among tools that emit an
  ACMG/AMP class.
- Criterion concordance: Jaccard similarity over explicitly returned criteria.
- Provenance completeness: presence of source identity and version fields,
  reported as field coverage rather than a quality score.
- Outcome safety: explicit non-resolved state without guessed identity.
- Boundary completeness: explicit professional-review, no-diagnosis and
  no-treatment limits plus a documented patient-data policy.
- Reproducibility: same normalized identity and contract version on repeated
  runs, with source-version changes reported rather than hidden.
- Latency: median and interquartile range over at least five sequential runs,
  reported separately from scientific results.

## Interpretation limits

Concordance is not accuracy. ClinVar is an archive of submitted assertions, not
a universal ground truth, and automated tools can use different evidence dates,
transcripts, gene-specific specifications and unavailable data. Any accuracy or
clinical-validity claim requires an independently curated evaluation set,
qualified reviewers, prespecified acceptance criteria and conflict resolution.

Folklore Clinical Variant Interpretation MCP is published by Helena
Bioinformatics. Its public results are automated variant-level decision support
for qualified professional review, not a diagnosis or treatment recommendation.
