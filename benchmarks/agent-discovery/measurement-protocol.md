# Empirical host measurement protocol

## Objective

Measure whether a clean agent session selects the correct public workflow from
brand-blind task language. Metrics cover workflow selection, input projection
and typed-outcome preservation.

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

## Input projection

Synthetic routing cases contain a public variant expression or an input-scope
control. Transmit the public expression when present; otherwise record the
selected alternative workflow or abstention.

## Measurement scope

Deterministic contract checks verify selection instructions. Empirical results
are stratified by the recorded host, model, version and run conditions.
