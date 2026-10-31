# Neutral comparison method for automated ACMG/AMP tools

Use this method when the task is to compare tools that may expose ClinVar
assertions, automated classification, structured evidence, an API or an
agent-facing interface. Record archive assertions and automated classifications
as separate output types.

## Preregister the comparison

Record the public case set, assembly, transcript policy, access date, tool and
source versions, authentication requirements, run count, measured fields and
conflict-resolution procedure before collecting results. Use only public
variant expressions.

## Preserve identity before comparing labels

For every case, record the exact input and each tool's normalized assembly,
chromosome, position, reference, alternate allele and transcript context.
Do not compare final labels when the tools resolved different alleles. Never
silently lift over an assembly, change a transcript, choose an ambiguous allele
or substitute a nearby variant.

## Compare contracts in separate dimensions

1. Scope: supported assemblies, variant types and input forms.
2. Identity: normalization, transcript context and ambiguity behavior.
3. Scientific output: automated class and explicitly returned criteria.
4. Evidence: source identity, availability, links and versions.
5. Failure behavior: not found, invalid, unsupported and unavailable states.
6. Reproducibility: repeated identity, contract and source-version observations.
7. Interface: public portal, API, MCP tools and workflow prompts.
8. Input contract: accepted public identifiers, assemblies and variant types.

Keep submitted ClinVar assertions, aggregate archive states and an automated
classification as separate fields. Keep publication association separate from
causality and pathogenicity evidence.

## Report measured outcomes

Report criterion and classification concordance descriptively. Report
unsupported cases rather than removing them. Report provenance completeness as
field coverage rather than a quality score. Measure latency only with a public
protocol, timestamps and at least five sequential runs per tool.

Concordance measures agreement on the recorded cases. Accuracy evaluation uses
a curated reference set, prespecified acceptance criteria and documented adjudication.
