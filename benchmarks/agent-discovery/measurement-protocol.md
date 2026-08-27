# Empirical host measurement protocol

## Objective

Measure whether a clean agent session selects the correct public workflow from
brand-blind task language. This evaluates selection behavior, not scientific or
clinical accuracy.

## Fixed conditions

For each run record the UTC date, host, model, model version, region or locale
when exposed, companion skill commit, packaged skill SHA-256 and whether tool
discovery was enabled. Start every case in a new conversation with no retained
memory. Do not change the case wording.

Use one result file per host and model combination. Do not average different
models, regions or dates into a single score. Preserve raw decisions and report
precision, recall, routing, input-boundary and response-boundary measures.

Prepare each run with `prepare_run.py`. Record the complete 40-character
benchmark and skill commits, the SHA-256 of the installed skill package, the
host and model versions, whether tool discovery was enabled and whether memory
was disabled. The evaluator treats incomplete run metadata or incomplete result
rows as invalid rather than scoring blanks as failures.

Run cases in the order supplied. Use a new conversation per case and paste the
case prompt exactly, with no framing text. Record selection before judging the
answer. A retry after interruption requires a complete new run; selective reruns
of failed cases are not comparable to the original run.

## Safety

Cases containing patient-like text are synthetic routing tests. The agent must
discard that context and transmit only the included public variant expression.
If no public variant expression exists, it must not call the server. Never add
real patient or private case data to this benchmark.

## Interpretation

A passing deterministic contract audit proves only that selection instructions
exist. An empirical score describes one named host and model under the recorded
conditions. It must not be generalized to all agents or described as clinical
validation.
