# Client compatibility

Folklore Clinical Variant Interpretation MCP uses the hosted endpoint
https://api.helena.bio/folklore/v1/mcp without an account, API key or OAuth.

## Current 1.6.0 surface and qualification

The fully enabled 1.6.0 configuration exposes ten scientific tools and the
separate, optional support_helena helper, five workflow prompts and one optional
MCP App resource. Self-hosted feature gates can reduce that inventory. Read
tools/list for the actual enabled tools; support discovery is not scientific
retrieval. The four public gene tools are described in
[Public gene profiles](PUBLIC_GENE_PROFILES.md).

The modern 2026-07-28 path is stateless. Each request carries matching protocol
metadata and routing headers; it has no initialize exchange or Mcp-Session-Id.
[The direct HTTP recipe](../integrations/direct-streamable-http/README.md)
contains a complete request and a one-call identity/snapshot smoke.
The smoke qualifies only the hosted JSON response to resolve_gene for BRCA1.
It does not qualify named SDK clients, streaming responses, profile retrieval
or clinical accuracy. Record the exact client package/version, protocol,
transport, date, discovery outcome and scientific result for any broader
compatibility claim.

All MCP requests, including optional discovery and lists, consume the
[shared network budget](RATE_LIMITS.md). A single smoke also consumes that
budget. Coordinate callers sharing egress and stop on HTTP 429; automatic
replay is not part of either example.

## Historical protocol observations

Publisher observation on 2026-09-10, adapter 1.4.1 and MCP Python SDK 2.0.0:

| Mode | Entry | Observed behavior |
| --- | --- | --- |
| Stateless 2026-07-28 | server/discover | supportedVersions contains 2026-07-28; tools/list is directly callable. |
| Legacy 2025-03-26 | initialize | Returns protocolVersion 2025-03-26 and capabilities. |

The SDK supplied legacy negotiation in that observation. There was no
extra remote bridge in the hosted request path. The local Biomni/Biorouter
stdio bridges are separate client integrations. Do not infer that initialize
is rejected because the modern protocol no longer requires it, or claim
every legacy version is verified from this one probe.

For 2026-07-28 requests send MCP-Protocol-Version and Mcp-Method. Also send
Mcp-Name matching params.name for tools/call and prompts/get, or params.uri
for resources/read. Include the matching protocol version and client capabilities
in params._meta as shown in the direct HTTP recipe. Missing or mismatched routing headers are transport errors,
not scientific not_found outcomes. server/discover is an optional preflight,
not a stateful initialization exchange.

## Result handling

Read HTTP and JSON-RPC errors before interpreting result.structuredContent.
Check result.isError and adapter_error; HTTP 200 alone is insufficient.
Variant envelopes have a nullable result: preserve adapter_error when it is null
and otherwise branch on result.status. See [Typed outcomes](TYPED_OUTCOMES.md).
The gene-disease tools return their source assertions, pagination and
usage_boundary directly; see [Gene-disease evidence](GENE_DISEASE_EVIDENCE.md).
The four gene-profile tools use a nullable result envelope and preserve gene,
snapshot, source and section identity; see [Public gene profiles](PUBLIC_GENE_PROFILES.md).
A corpus-scoped miss or unavailable reference section is not biological absence.

Variant tools accept only one public variant expression and assembly. Gene-disease tools accept a public gene/disease identifier or disease name with bounded pagination. Do not forward
patient-specific histories or phenotype narratives, family or segregation
context, or private case data. Public phenotype/HPO/OMIM reference-literature
queries remain allowed by their published schema. Never
auto-select an ambiguous candidate. Results require qualified professional
review and are not a diagnosis or treatment recommendation.

Run python3 ops/public_smoke.py for modern discovery. That check does not
execute a scientific tool. Run the separate one-call identity/snapshot smoke
from the direct HTTP recipe for its bounded scientific acceptance criteria.
Keep discovery, transport acceptance and scientific results separate.
