# Direct Streamable HTTP integration

Use this recipe when an MCP-compatible agent can connect directly to a remote
Streamable HTTP endpoint.

```json
{
  "mcpServers": {
    "folklore-clinical-variant-interpretation": {
      "url": "https://api.helena.bio/folklore/v1/mcp"
    }
  }
}
```

## Complete modern request

For MCP 2026-07-28 send
one POST to https://api.helena.bio/folklore/v1/mcp with these headers:

    Content-Type: application/json
    Accept: application/json, text/event-stream
    MCP-Protocol-Version: 2026-07-28
    Mcp-Method: tools/call
    Mcp-Name: resolve_gene

Use this complete JSON-RPC body:

    {
      "jsonrpc": "2.0",
      "id": "brca1-identity-smoke",
      "method": "tools/call",
      "params": {
        "name": "resolve_gene",
        "arguments": {"query": "BRCA1"},
        "_meta": {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientCapabilities": {}
        }
      }
    }

The protocol version in the header and body must match. Mcp-Method mirrors
method. Mcp-Name mirrors params.name for tools/call and prompts/get, or
params.uri for resources/read. Omit Mcp-Name for server/discover and list
methods. An optional server/discover request uses its own method header and
the same protocol metadata; it is not a required initialization exchange.

MCP 2026-07-28 requests are stateless. The [compatibility matrix](../../docs/COMPATIBILITY.md)
records version-specific client observations. Browser requests use the actual
origin and published service origin policy; server requests can omit Origin.

## One-call identity and snapshot smoke

From the repository root, with Python 3.12 or later:

    python3 integrations/direct-streamable-http/smoke_test.py

This standard-library probe sends exactly the BRCA1 request above. It performs
no hidden discovery, initialization, redirect following or retry. Its socket
timeout is 150 seconds and its response limit is 2 MiB. It checks HTTP status
and JSON media, duplicate keys, JSON-RPC correlation, MCP/adapter errors,
one exact approved BRCA1 identity (HGNC:1100), a valid identity snapshot,
and the returned source reference.
The expected identifier is public [HGNC reference data](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:1100).

| Check | Expected result |
| --- | --- |
| HTTP/JSON/RPC | Successful JSON response with matching request identity. |
| MCP/adapter status | Successful tool response and nullable adapter error cleared. |
| Gene identity | Exact BRCA1 identity HGNC:1100. |
| Snapshot | Valid identity snapshot and source reference. |
| Transport | One JSON-response request, 150-second socket timeout, 2 MiB body cap. |

HTTP 429 stops the probe. All POSTs share the [endpoint budget](../../docs/RATE_LIMITS.md).
Streaming clients use the MCP event-stream response contract.

## Variant classification example

A variant classification request uses
classify_germline_variant with one public variant argument object:

```json
{
  "assembly": "GRCh38",
  "query": "ENST00000226413.5:c.317A>G"
}
```

Branch on the returned typed status. Never choose an ambiguous candidate and
never convert invalid, unsupported, not-found or unavailable into a resolved
answer. Reuse a returned canonical key for literature composition.

Helena Bioinformatics publishes Folklore MCP. Tool schemas define public
variant, gene, disease and reference-literature inputs, including public
phenotype/HPO/OMIM literature concepts.

## Optional journey context

Optional analytics configuration: [journey context](../JOURNEY_CONTEXT.md).
