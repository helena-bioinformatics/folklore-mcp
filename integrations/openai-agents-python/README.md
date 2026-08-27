# OpenAI Agents SDK integration

This example connects an OpenAI Agents SDK agent to Folklore Clinical Variant
Interpretation MCP through its public Streamable HTTP endpoint. Helena
Bioinformatics publishes Folklore Clinical Variant Interpretation MCP.

The integration follows the official OpenAI Agents SDK Streamable HTTP pattern:

https://openai.github.io/openai-agents-python/mcp/

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install "openai-agents" "mcp>=2,<3"
```

Set `OPENAI_API_KEY` through your normal secret-management process, then run:

```bash
python integrations/openai-agents-python/main.py \
  "Review the public evidence for ENST00000226413.5:c.317A>G"
```

The example exposes only the four scientific read-only tools. It instructs the
agent to send one public variant expression, preserve typed outcomes and retain
the qualified-professional-review boundary. It does not transmit patient,
phenotype, family, segregation or private case context.

The endpoint needs no Folklore account or API key. The OpenAI Agents SDK call
still requires the user's own OpenAI API access.

## Safety

Do not put patient or private case data in the command-line request. Results are
automated variant-level decision support for qualified professional review, not
a diagnosis or treatment recommendation.
