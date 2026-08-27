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

Use `prepare_run.py` for each host and model combination. It creates a result
sheet pre-populated with all 100 case IDs and a metadata record. Complete both
files, then run `evaluate_results.py` to calculate selection precision,
selection recall, routing accuracy, public-input compliance and safety-boundary
retention. The evaluator rejects missing, duplicate, unknown or incomplete case
rows and refuses cold-start metadata that does not identify the exact benchmark,
skill package, host and model.

## Run the deterministic audit

```bash
python3 benchmarks/agent-discovery/audit_skill.py
python3 benchmarks/agent-discovery/prepare_run.py \
  path/to/host-model-run
python3 benchmarks/agent-discovery/evaluate_results.py \
  path/to/host-model-run/results.csv \
  --metadata path/to/host-model-run/run-metadata.json
```

Fill every result field with `yes` or `no`; use `none` for `selected_tool`
when the agent correctly does not select the workflow. Keep the original case
order. Do not evaluate the generated blank sheet before all 100 cases are run.

For each case:

1. start a new conversation with memory and prior-case context disabled;
2. make the packaged skill and tool catalogue available under the recorded
   host conditions;
3. paste the exact `prompt` value from `cases.csv` without a prefix, suffix or
   correction;
4. record selection before evaluating answer quality;
5. record the actual tool route and whether only public variant input was sent;
6. preserve the raw host transcript outside this repository when host terms
   permit, but never add patient or private case data;
7. close the conversation before the next case.

Do not rerun only failed cases, change the prompt wording, mix host versions or
fill results from model memory. If a case is interrupted, rerun the complete
100-case set in a new result directory and retain the interrupted run as such.

The audit emits JSON with case counts, route coverage, intent-family coverage
and safety-contract checks. A passing result means the selection contract is
present and testable, not that scientific or clinical accuracy was established.

## Safety

Never send patient, phenotype, family, segregation or private case data. For a
case that contains such context, the expected behavior is to exclude that
context and use only a public variant expression when one is already present.
If no public variant expression is present, the agent should request one rather
than calling a tool.
