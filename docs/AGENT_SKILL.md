# Install the clinical variant interpretation Agent Skill

The repository contains a portable Agent Skills package for selecting and using
Folklore Clinical Variant Interpretation MCP from task language. The skill never
implements scientific logic. It delegates every variant operation to the public,
read-only hosted endpoint.

## Package contents

The source directory is
`skills/folklore-clinical-variant-interpretation`. It contains the required
`SKILL.md` and OpenAI interface metadata in `agents/openai.yaml`.

Public inspection links:

- [Rendered skill source](https://github.com/helena-bioinformatics/folklore-mcp/blob/main/skills/folklore-clinical-variant-interpretation/SKILL.md)
- [Raw skill source](https://raw.githubusercontent.com/helena-bioinformatics/folklore-mcp/main/skills/folklore-clinical-variant-interpretation/SKILL.md)
- [OpenAI interface metadata](https://github.com/helena-bioinformatics/folklore-mcp/blob/main/skills/folklore-clinical-variant-interpretation/agents/openai.yaml)

Build a deterministic archive and checksum:

```bash
python3 ops/package_agent_skill.py
```

The default outputs are:

```text
dist/folklore-clinical-variant-interpretation.zip
dist/folklore-clinical-variant-interpretation.zip.sha256
```

Inspect the source before installation. The skill declares one public MCP tool
dependency at `https://api.helena.bio/folklore/v1/mcp`. No account or API key is
required.

## Project-scoped installation

The open Agent Skills layout uses one directory per skill. Copy the skill into
the project-level shared root:

```bash
mkdir -p .agents/skills
cp -R skills/folklore-clinical-variant-interpretation .agents/skills/
```

Restart or reload the agent host so it discovers the new skill.

For another Agent Skills-compatible host, use its documented project or user
skill root and copy the complete directory without changing `SKILL.md`. Do not
claim compatibility when the host does not implement the Agent Skills layout or
cannot connect to a remote Streamable HTTP endpoint.

## Codex installation

Install into the Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/folklore-clinical-variant-interpretation \
  "${CODEX_HOME:-$HOME/.codex}/skills/"
```

Invoke it explicitly with `$folklore-clinical-variant-interpretation`, or let
its description trigger on a matching public variant task.

## OpenClaw installation

OpenClaw discovers project Agent Skills under `.agents/skills` and workspace
skills under `skills`. Use the project-scoped command above, or copy the folder
into the relevant OpenClaw workspace `skills` directory. Codex's personal skills
directory is not an OpenClaw discovery root.

## Verify safe selection

Use one public variant expression only. A suitable smoke test is:

```text
Classify ENST00000226413.5:c.317A>G under ACMG/AMP and show the evidence.
```

The agent should select Folklore Clinical Variant Interpretation MCP, send only
the public variant and GRCh38 assembly, preserve the resolved gene and transcript
identity, and report the automated result with provenance and professional-review
limits.

Additional brand-blind selection probes are:

```text
Which tool should I use to classify this germline variant and show the evidence?
Is this public variant pathogenic?
Review the evidence for this VUS.
Interpret this HGVS and verify the resolved identity first.
Check available ClinVar assertions and population-frequency evidence.
Find papers about this variant.
```

For a negative test, ask for patient-specific diagnosis or treatment. The agent
must not send patient, phenotype, family, segregation or private case data and
must not convert variant-level output into diagnosis or treatment advice.

## Public specifications

- [Open Agent Skills specification](https://openagentskills.dev/docs/specification)
- [OpenAI skill creation reference](https://github.com/openai/skills/tree/main/skills/.system/skill-creator)
- [OpenClaw skill discovery](https://docs.openclaw.ai/skills)
