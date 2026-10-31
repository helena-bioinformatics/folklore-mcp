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
pip install "openai-agents==0.24.0" "mcp>=2,<3"
```

Set `OPENAI_API_KEY` through your normal secret-management process, then run:

```bash
python integrations/openai-agents-python/main.py \
  "Classify ENST00000226413.5:c.317A>G under ACMG/AMP"
```

The example exposes four scientific tools. It sends one public variant
expression and preserves classification, source evidence and typed outcomes.

The endpoint needs no Folklore account or API key. The OpenAI Agents SDK call
still requires the user's own OpenAI API access.

## Inputs and output

The command-line request identifies one public variant or a scientific
literature question. Results retain the returned classification and source fields.

Optional analytics uses the SDK `tool_meta_resolver`, with caller-owned context
kept outside model arguments. See [journey context](../JOURNEY_CONTEXT.md).
The default run remains anonymous; no account ID or prompt is used as an ID.
