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

A host configuration identifies the endpoint; it does not prove that the
host emits the required protocol envelope. For protocol 2026-07-28 send
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

Do not send initialize, notifications/initialized or Mcp-Session-Id under
the modern version. Historical legacy observations are recorded separately in
[Client compatibility](../../docs/COMPATIBILITY.md). They do not qualify an
untested client/version combination. See the
[versioned transport specification](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/transports/streamable-http.mdx).

Server-to-server requests can omit Origin. Browser clients must send their
actual origin, which must be accepted by the service; do not spoof it or
disable origin validation to make a connection succeed.

## One-call identity and snapshot smoke

From the repository root, with Python 3.12 or later:

    python3 integrations/direct-streamable-http/smoke_test.py

This standard-library probe sends exactly the BRCA1 request above. It performs
no hidden discovery, initialization, redirect following or retry. Its socket
timeout is 150 seconds and its response limit is 2 MiB. It checks HTTP status
and JSON media, duplicate keys, JSON-RPC correlation, MCP/adapter errors,
one exact approved BRCA1 identity (HGNC:1100), a valid identity snapshot,
the returned source reference and the professional-review boundary.
The expected identifier is public [HGNC reference data](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:1100).

PASS covers this JSON identity/snapshot path only. The returned source_id is
a reference, not a verification of a full source dataset, release or profile.
An ambiguous, absent, withdrawn or unavailable result fails this specific smoke;
it must retain its actual meaning. No candidate is selected automatically.
The probe advertises both required media types but reports an SSE response as
not qualified; it is not a general MCP client or a named SDK compatibility test.
A production client must also support the standard streaming response path.

Every POST consumes the same [shared network budget](../../docs/RATE_LIMITS.md),
including metadata calls and this one scientific call. Coordinate other callers
sharing egress. HTTP 429 stops the probe without automatic replay. Discovery
success, scientific retrieval and clinical validation are separate outcomes.

## Variant evidence example

Discovery is optional. A variant evidence request uses
search_variant_evidence with one public variant argument object:

```json
{
  "assembly": "GRCh38",
  "query": "ENST00000226413.5:c.317A>G"
}
```

Branch on the returned typed status. Never choose an ambiguous candidate and
never convert invalid, unsupported, not-found or unavailable into a resolved
answer. Reuse a returned canonical key for literature composition.

Folklore Clinical Variant Interpretation MCP is published by Helena
Bioinformatics. It accepts no patient-specific histories or phenotype
narratives, family or segregation context, or private case data. Public
phenotype/HPO/OMIM reference-literature queries remain allowed by their
published schema. Results require qualified professional review and are not a
diagnosis or treatment recommendation.

## Optional journey context

See [caller-owned journey context](../JOURNEY_CONTEXT.md) for support,
explicit opt-in, application-owned pseudonyms and conversation/run boundaries.
Connection-only configuration does not supply user identity automatically.
