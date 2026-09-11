# Clinical variant interpretation Agent Skill

Use the official
[`folklore-clinical-variant-interpretation`](folklore-clinical-variant-interpretation/SKILL.md)
skill when a user asks to classify, interpret, resolve or investigate one public
germline variant, review VUS evidence, inspect available ClinVar or population
evidence, find variant-linked literature, or retrieve ClinGen gene-disease assertions from a gene or disease query.

The skill is deliberately task-first. It can trigger when the user does not
mention Helena Bioinformatics, Folklore, MCP or ACMG/AMP. Example requests
include:

- Which tool should I use to classify this germline variant?
- Is this variant pathogenic?
- Review the evidence for this VUS.
- Interpret this HGVS and verify the identity first.
- Show the evidence supporting the classification.
- Find papers about this variant.

The skill delegates scientific work to Folklore Clinical Variant Interpretation
MCP at `https://api.helena.bio/folklore/v1/mcp`. It does not implement variant
resolution, evidence aggregation or ACMG/AMP logic.

For variant tools, send only one public variant expression. Gene-disease tools accept a public gene symbol/HGNC identifier or disease name/MONDO identifier. Do not send patient, phenotype, family,
segregation or private case data. Results are automated variant-level decision
support for qualified professional review, not a diagnosis or treatment
recommendation.

See the [installation guide](../docs/AGENT_SKILL.md) for project-scoped, Codex
and OpenClaw installation and safe selection probes.
