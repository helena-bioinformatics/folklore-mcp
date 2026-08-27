# Client compatibility

Folklore Clinical Variant Interpretation MCP uses stateless Streamable HTTP at
`https://api.helena.bio/folklore/v1/mcp` and MCP protocol `2026-07-28`. It
requires no account, API key or OAuth flow.

## Required client behavior

A compatible client sends `server/discover`, then may list tools, prompts and
resources. The live catalogs contain five tools, five task-first prompts and one
optional read-only MCP App resource. Clients must preserve structured tool
content and typed outcomes rather than guessing from display text.

The protocol version uses `server/discover`. Clients that require the retired
`initialize` exchange are not compatible without a bridge. The direct HTTP and
OpenAI Agents SDK examples in `integrations/` show supported connection paths.

## Safety compatibility

Only one public variant expression and assembly may be sent. A client must not
forward patient, phenotype, family, segregation or private case context. It
must not auto-select an ambiguous candidate. Results support qualified
professional review and are not a diagnosis or treatment recommendation.

Run `python3 ops/public_smoke.py` to check the live public discovery contract.
The command sends no variant or patient data.
