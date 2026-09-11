# Client compatibility

Folklore Clinical Variant Interpretation MCP uses the hosted endpoint
https://api.helena.bio/folklore/v1/mcp without an account, API key or OAuth.

## Verified protocol matrix

Publisher observation on 2026-09-10, adapter 1.4.1 and MCP Python SDK 2.0.0:

| Mode | Entry | Observed behavior |
| --- | --- | --- |
| Stateless 2026-07-28 | server/discover | supportedVersions contains 2026-07-28; tools/list is directly callable. |
| Legacy 2025-03-26 | initialize | Returns protocolVersion 2025-03-26 and capabilities. |

The deployed SDK supplies legacy negotiation beneath the adapter. There is no
extra remote bridge in the hosted request path. The local Biomni/Biorouter
stdio bridges are separate client integrations. Do not infer that initialize
is rejected because the modern protocol no longer requires it, or claim
every legacy version is verified from this one probe.

For 2026-07-28 requests send MCP-Protocol-Version, Mcp-Method and, for named
operations such as tools/call, Mcp-Name matching params.name. Include the
protocol version and client capabilities in params._meta as shown in the
direct HTTP recipe. Missing or mismatched routing headers are transport errors,
not scientific not_found outcomes. server/discover is an optional preflight,
not a stateful initialization exchange.

## Result handling

The full 1.5.0 configuration contains seven tools, five workflow prompts and one optional MCP App
resource. Read JSON-RPC errors first. Otherwise inspect result.structuredContent:
when its result is null, handle adapter_error; otherwise branch on result.status.
See TYPED_OUTCOMES.md for the exact six variant statuses. The new gene-disease tools return their own structured response directly, with source assertions, pagination and usage_boundary; errors carry adapter_error and isError. See GENE_DISEASE_EVIDENCE.md.

Variant tools accept only one public variant expression and assembly. Gene-disease tools accept a public gene/disease identifier or disease name with bounded pagination. Do not forward
patient, phenotype, family, segregation or private case context. Never
auto-select an ambiguous candidate. Results require qualified professional
review and are not a diagnosis or treatment recommendation.

Run python3 ops/public_smoke.py for modern discovery. The runtime benchmark
records scientific calls separately from discovery and transport acceptance.
