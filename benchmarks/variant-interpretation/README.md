# Variant classification benchmark

Compare public variant interfaces on identity, automated class, reported criteria,
source evidence, typed outcomes and elapsed time.

## Cases and capture

`cases.csv` contains the fixed public HGVS, rsID and coordinate inputs, including
ambiguous, invalid and unsupported expressions. Preserve case IDs, exact inputs,
assembly and original order.

```bash
python3 benchmarks/variant-interpretation/capture_folklore.py \
  --output folklore-baseline.jsonl
```

Record every case's status, normalized allele, transcript, automated class,
criteria, source versions, evidence availability and elapsed time. Request pacing
follows the shared endpoint budget. Separate technical admission failures from
scientific outcomes.

## Comparison and metrics

Use the same case input for each tool. Compare classifications only for matching
normalized alleles and retain unresolved cases as their exact typed outcomes.
Record tool/version, date, protocol, authentication, source releases and run count.

- Identity concordance: exact assembly/chromosome/position/reference/alternate agreement.
- Class concordance: exact agreement among returned ACMG/AMP classes.
- Criterion concordance: Jaccard similarity over reported criteria.
- Provenance coverage: presence of source identity and version fields.
- Outcome handling: preserved resolved, ambiguous, not_found, invalid_request,
  unsupported and unavailable statuses.
- Reproducibility: repeated allele/contract identity with source-version changes recorded.
- Latency: median and interquartile range over at least five sequential runs.

Concordance measures agreement. Accuracy evaluation uses a curated reference set,
prespecified acceptance criteria and documented adjudication.

[Comparison method](COMPARISON_METHOD.md) | [Preregistration](PREREGISTRATION.md) |
[Review](INDEPENDENT_REVIEW.md) | [Manifest](benchmark-manifest.json) |
[Dataset template](dataset-manifest.template.json)
