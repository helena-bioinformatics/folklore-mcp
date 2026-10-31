# Agent tool-selection benchmark

The 100 fixed cases in `cases.csv` cover classification, VUS assessment, identity,
ClinVar assertions, population frequencies, literature and input-scope handling.

## Run

```bash
python3 benchmarks/agent-discovery/audit_skill.py
python3 benchmarks/agent-discovery/prepare_run.py path/to/host-model-run
python3 benchmarks/agent-discovery/evaluate_results.py \
  path/to/host-model-run/results.csv \
  --metadata path/to/host-model-run/run-metadata.json
```

For each host/model/version, install the recorded skill package and run each
case in a fresh conversation using its exact prompt and original order. Record
selection before answer evaluation, the actual selected tool, transmitted public
arguments, typed outcome and source attribution. Retain every interrupted or
failed attempt with its status and transcript reference.

The run metadata records benchmark, skill package checksum, host, model, version,
date and available tool configuration. Keep host/model strata separate.
The evaluator checks case completeness, uniqueness and recorded metadata before
reporting selection precision, recall, routing and input-contract measures.

`audit_skill.py` performs a deterministic selection-contract check. Empirical
host results record actual agent choices under the stated configuration.
