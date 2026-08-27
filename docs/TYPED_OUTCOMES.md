# Typed outcomes for agent control flow

Agents should branch on the structured status returned by Folklore Clinical
Variant Interpretation MCP, not on prose or model memory.

| Outcome | Agent action |
| --- | --- |
| `resolved` | Verify normalized identity, then report classification, criteria, evidence, provenance and limits. |
| `ambiguous` | Present candidates and require an explicit choice. |
| `not_found` | Report no supported public match. Do not infer a nearby variant. |
| `invalid` | Explain accepted notation and request a corrected public expression. |
| `unsupported` | State the published boundary without forcing conversion. |
| `temporarily_unavailable` | Report the temporary failure and retry only when useful. |

The reusable normalized identity is the safe composition key for subsequent
variant-literature calls. Literature association remains separate from
ACMG/AMP classification. Every outcome remains decision support for qualified
professional review, not a diagnosis or treatment recommendation.
