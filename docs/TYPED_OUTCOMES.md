# Typed outcomes for agent control flow

Branch on the structured status returned by Folklore MCP.

| Outcome | Agent action |
| --- | --- |
| `resolved` | Verify normalized identity, then report classification, criteria, evidence, provenance and limits. |
| `ambiguous` | Present candidates and require an explicit choice. |
| `not_found` | Report no supported public match. Do not infer a nearby variant. |
| `invalid_request` | Explain accepted notation and request a corrected public expression. |
| `unsupported` | State the published boundary without forcing conversion. |
| `resolution_unavailable` | Report the temporary failure and retry only when useful. |

Read the outer JSON-RPC error before result. For a tool response, the adapter
envelope is at result.structuredContent. If envelope.result is null, use
envelope.adapter_error (code, message, retryable); it is not a scientific miss.
Otherwise branch on envelope.result.status using the exact enum above.
A resolved identity with interpretation.status unavailable carries a typed
interpretation error. Classification is read when interpretation.status is success.

The normalized identity is the composition key for variant-literature calls.
Literature match labels and ACMG/AMP classification retain their respective
source semantics.
