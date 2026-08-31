# Helena Bioinformatics n8n templates

These credential-free templates call the production, stateless MCP 2026-07-28
endpoints directly with explicit method and tool headers. They intentionally use
the core HTTP Request node because the current n8n MCP Client performs the older
session initialization exchange, while these Helena endpoints are stateless and
do not implement the retired `initialize` method.

Import the JSON file, change the sample question or identifier, and run it. The
templates accept public, non-sensitive research inputs only.

| Template | Public service |
| --- | --- |
| `noodle-biomedical-literature-search.json` | Noodle biomedical paper search |
| `folklore-variant-interpretation.json` | Folklore germline variant evidence |
| `ask-helena-public-knowledge.json` | Ask Helena source-cited public knowledge |
