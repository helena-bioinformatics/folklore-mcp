# Troubleshooting public connections

## A client asks for `initialize`

Folklore Clinical Variant Interpretation MCP implements MCP `2026-07-28`, which
uses `server/discover`. Use a current Streamable HTTP client or one of the
published bridges in `integrations/`.

## The endpoint returns a protocol error

Send `MCP-Protocol-Version: 2026-07-28` and a matching `Mcp-Method` header. Keep
the JSON-RPC method and header identical. The direct Streamable HTTP recipe has
copyable requests.

## A result is `ambiguous`

Show the returned candidates and ask the user to choose. Do not select by rank,
gene expectation or model memory.

## A result is `invalid_request`, `unsupported` or `not_found`

Preserve the typed outcome. Request a corrected public expression for
`invalid_request`, explain the published scope for `unsupported`, and do not substitute
a nearby variant for `not_found`.

## Evidence is unavailable

Unavailable is not negative evidence. Report the limitation and provenance
returned by the tool. Do not invent a classification from model memory.
