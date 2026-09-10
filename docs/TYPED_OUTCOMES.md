# Typed outcomes for agent control flow

Agents should branch on the structured status returned by Folklore Clinical
Variant Interpretation MCP, not on prose or model memory.

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
A resolved identity with interpretation.status unavailable is not a successful
classification. Preserve its typed error instead of reading classification.

The reusable normalized identity is the safe composition key for subsequent
variant-literature calls. Literature association remains separate from
ACMG/AMP classification. Every outcome remains decision support for qualified
professional review, not a diagnosis or treatment recommendation.
