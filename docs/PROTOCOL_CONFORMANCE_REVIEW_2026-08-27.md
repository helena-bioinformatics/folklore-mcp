# Protocol conformance review, 2026-08-27

This note records Helena Bioinformatics' reproduction and classification of
[public issue 1](https://github.com/helena-bioinformatics/folklore-mcp/issues/1).
It is a protocol review of Folklore Clinical Variant Interpretation MCP, not a
scientific-performance, clinical-accuracy, diagnosis or treatment claim.

## Reproduction boundary

The checks used only `server/discover` and static list methods. They sent no
variant, patient, phenotype, family, segregation or private case data. The
hosted endpoint was checked with MCP protocol `2026-07-28`, and the public
adapter source and first-party tests were inspected separately.

## Classification

| Observation | Classification | Reproduction result |
|---|---|---|
| Requests without the required `_meta` envelope may be accepted by mixed replicas | `needs_evidence` | A repeated sample produced no accepted response. Every request that reached validation returned HTTP 400 with JSON-RPC `-32602`; the remaining attempts were rejected by the separate HTTP 429 rate limiter. A later single control again returned HTTP 400 and `-32602`. |
| The server lacks the MCP `2026-07-28` stateless lifecycle or `server/discover` | `already_resolved` | The live endpoint returned `2026-07-28` discovery without a session or legacy initialization exchange. |
| Tool and resource change support is undeclared | `already_resolved` | Live discovery explicitly returned `listChanged: false` for tools, resources and prompts. The lists are static and no change-notification subscription is served. |
| Invalid cursors are accepted by the static list methods | `accepted_with_scope` | A non-object cursor was already rejected by schema validation. A syntactically valid string that the server never issued was accepted by `tools/list`, `resources/list` and `prompts/list`. These methods return complete static lists and no `nextCursor`, so every non-null cursor is unissued and invalid. |
| Add the suggested third-party scoring action to CI | `needs_evidence` | Existing first-party CI already tests the current protocol surface. The score did not distinguish already-resolved observations from the reproduced cursor case. A third-party workflow will not be added until its version, permissions, scoring contract and supply-chain boundary are independently reviewed. |

The MCP pagination guidance says invalid cursors should produce JSON-RPC
`-32602`. It also tells clients to continue only with an opaque `nextCursor`
returned by the server. See the
[MCP pagination specification](https://modelcontextprotocol.io/specification/draft/server/utilities/pagination).
The stateless lifecycle and optional discovery method are described in the
[MCP 2026-07-28 release note](https://blog.modelcontextprotocol.io/posts/2026-07-28/).

## Accepted correction

Public adapter commit
[`c7005c7`](https://github.com/helena-bioinformatics/folklore-mcp/commit/c7005c74e6c5b919a0f9725eb61080263f58b3a8)
rejects every non-null cursor on `tools/list`, `resources/list` and
`prompts/list` with JSON-RPC `-32602`. A first-party regression test covers all
three methods. The repository test, lint and formatting checks passed, and the
public GitHub CI completed successfully.

## Acceptance criteria and deployment state

The correction is complete only when all of the following are true:

1. the source change and regression test are on public `main`;
2. public CI passes;
3. the same scoped change is deployed through Helena Bioinformatics' normal
   reviewed production workflow;
4. each live static list method rejects an unissued string cursor with HTTP 400
   and JSON-RPC `-32602`;
5. ordinary cursor-free list requests and discovery remain unchanged.

Criteria 1 and 2 are satisfied. The hosted endpoint still accepted the
unissued string cursor when this note was published, so criteria 3 through 5
remain pending. The issue is therefore **validated and recorded for
implementation**, not described as fixed in production.

## Severity and ownership

- Severity: low protocol-conformance defect.
- Scientific and clinical impact: none identified; the affected methods list
  static metadata and do not process variant evidence.
- Affected contract: MCP pagination behavior for `tools/list`,
  `resources/list` and `prompts/list`.
- Owner: Helena Bioinformatics production workflow.
- Follow-up: deploy the scoped adapter change, run the live acceptance checks,
  and update this note with the verified result.
