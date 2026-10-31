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
MCP at `https://api.helena.bio/folklore/v1/mcp`. The hosted scientific authorities produce variant resolution, evidence
aggregation and ACMG/AMP classification.

Variant inputs contain one public expression and GRCh38 assembly. Gene-disease
inputs contain a public gene symbol/HGNC identifier or disease name/MONDO
identifier. The skill routes classification and retrieval to the hosted tools.

See the [installation guide](../docs/AGENT_SKILL.md) for project-scoped, Codex
and OpenClaw installation and selection probes.
