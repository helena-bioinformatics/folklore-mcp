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
