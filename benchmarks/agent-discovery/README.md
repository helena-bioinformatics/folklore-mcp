# Cold-start agent discovery benchmark

This benchmark tests the selection question that precedes every scientific tool
call: can an agent recognize a public germline variant interpretation job when
the user does not name Helena Bioinformatics, Folklore Clinical Variant
Interpretation MCP, MCP or ACMG/AMP?

The 100-case corpus is intentionally brand-blind. It covers pathogenicity questions, VUS
review, variant identity, evidence, ClinVar, population frequency, literature,
invalid notation, unsupported scope and requests containing patient context.

## What this benchmark can establish

`audit_skill.py` verifies that the published companion skill has explicit
selection language, routes every expected job to a published tool and preserves
the clinical boundary. This is a deterministic contract audit. It does not
claim that every language model will select the skill.

An empirical host evaluation should install the packaged skill, start each case
in a new conversation, disable memory from earlier cases and record:

- whether the skill was selected before any answer was drafted;
- which tool was selected;
- whether only a public variant expression and assembly were transmitted;
- whether ambiguous, invalid, not-found, unsupported and unavailable outcomes
  were preserved;
- whether classification and literature association remained distinct;
- whether the final answer retained the professional-review boundary.

Report the host, model, version, date, skill package SHA-256 and complete result
matrix. Do not combine results from different host or model versions.

Copy `host-results-template.csv` for each host and model combination. Record one
row per case, then run `evaluate_results.py` to calculate selection precision,
selection recall, routing accuracy, public-input compliance and safety-boundary
retention. The evaluator reports missing case IDs and refuses duplicate rows.

## Run the deterministic audit

```bash
python3 benchmarks/agent-discovery/audit_skill.py
python3 benchmarks/agent-discovery/evaluate_results.py \
  path/to/completed-host-results.csv
```

The audit emits JSON with case counts, route coverage, intent-family coverage
and safety-contract checks. A passing result means the selection contract is
present and testable, not that scientific or clinical accuracy was established.

## Safety

Never send patient, phenotype, family, segregation or private case data. For a
case that contains such context, the expected behavior is to exclude that
context and use only a public variant expression when one is already present.
If no public variant expression is present, the agent should request one rather
than calling a tool.
