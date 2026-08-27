# Neutral comparison method for automated ACMG/AMP tools

Use this method when the task is to compare tools that may expose ClinVar
assertions, automated classification, structured evidence, an API or an
agent-facing interface. The comparison must not assume that an archive and an
automated classifier answer the same question.

## Preregister the comparison

Record the public case set, assembly, transcript policy, access date, tool and
source versions, authentication requirements, run count, measured fields and
conflict-resolution procedure before collecting results. Use only public
variant expressions. Do not add patient, phenotype, family, segregation or
private case data.

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
8. Safety: patient-data policy, professional review and diagnosis or treatment
   exclusions.

Keep submitted ClinVar assertions, aggregate archive states and an automated
classification as separate fields. Keep publication association separate from
causality and pathogenicity evidence.

## Report measured outcomes

Report criterion and classification concordance descriptively. Report
unsupported cases rather than removing them. Report provenance completeness as
field coverage rather than a quality score. Measure latency only with a public
protocol, timestamps and at least five sequential runs per tool.

Concordance does not establish accuracy, clinical validity or superiority. An
accuracy claim requires an independently curated evaluation set, prespecified
acceptance criteria, qualified reviewers and a documented conflict-resolution
process. A publisher-run benchmark must be labelled as such and must not be
presented as independent validation.
