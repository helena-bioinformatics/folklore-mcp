# Optional caller-owned journey context

The hosted Folklore MCP accepts explicitly enabled pseudonymous context in
`params._meta["io.helena/analytics"]`. It stays outside scientific arguments.
All examples remain anonymous by default. Adding this capability does not
activate analytics for existing installations or prove client adoption.

Use four separate application settings:

| Setting | Meaning |
| --- | --- |
| `analytics_opt_in` | Actual boolean `true`, only after analytics is enabled for this caller. |
| `analytics_user_id` | Caller-owned, random canonical lowercase UUIDv4. |
| `analytics_session_id` | Optional random UUIDv4 for one conversation or workflow run. |
| `analytics_intent` | Optional closed category listed below. |

Categories are `variant_evidence`, `literature_review`, `gene_disease_review`,
and `infrastructure_support`. Never pass a prompt or scientific query as intent.
Never reuse an authentication session, email, username, clinical record ID,
IP address, workflow ID or one shared ID for all users. Do not derive identity
from these values. Generate and retain the random pseudonym only in the caller's
permitted analytics context; rotate the session for a new actual conversation
or run. Multiple calls in that run reuse the same IDs. No file, cookie or
cross-application identity store is created by these examples.

Missing/false opt-in or an invalid pseudonym omits the entire extension. Invalid
optional session/category values are omitted. Only these four settings can reach
analytics; arbitrary settings, free text and scientific inputs are excluded.
Turning opt-in off stops forwarding immediately; it does not delete old records.

## Owned callers

| Client | Input surface | Verification boundary |
| --- | --- | --- |
| Dify source tools | Four operator-controlled `form` settings on each tool; workflow applications map their own approved context. | Actual request builder and tool entry points tested; installed Dify instances are not remotely changed. |
| Galaxy | `--analytics-opt-in`, `--analytics-user-id`, `--analytics-session-id`, `--analytics-intent`; optional wrapper controls. | CLI request tested; run IDs must come from the application, never Galaxy account/history identifiers. |
| KNIME | Same names in typed `knio.flow_variables`. | Executed script request tested with KNIME I/O fixtures; all rows in one run reuse supplied context. |
| n8n | Same names in the Variant query node; disabled/empty by default. | Actual exported HTTP body expression tested; imported workflows need updating explicitly. |
| Colab/Kaggle notebook | Optional settings in `JOURNEY = {}`. | Executable request cell tested; context is attached only to Folklore, not the subsequent Noodle calls. |
| OpenAI Agents Python | Same CLI settings, or `run(request, analytics=settings)` using SDK `tool_meta_resolver`. | SDK 0.24.0 metadata hook; no identity inferred from Runner context or model arguments. |
| Biorouter | Pass the extension as request metadata from the calling application. | FastMCP 3.4.2 proxy forwards metadata; it must not generate one shared user/session for its process. |
| Biomni | Host application must supply call metadata through its configured stdio proxy. | YAML contains only connection configuration; end-user context forwarding is not established by discovery or a smoke query. |
| ChatGPT, Claude and other hosted/desktop connectors | Host-controlled per-call metadata, if supported. | URL/static headers are not per-user journey context. Do not add personal IDs to URLs, headers or tool arguments. |

## Direct request example

Use your application's supplied values, not a global example identity:

```python
settings = {
    "analytics_opt_in": True,
    "analytics_user_id": approved_random_user_uuid,
    "analytics_session_id": current_random_conversation_uuid,
    "analytics_intent": "literature_review",
}
```

The client validates and projects them into `_meta`. Protocol version and
client capabilities remain intact. Scientific input/output schemas, results,
server authentication and the anonymous public endpoint are unchanged.

The OpenAI SDK example uses a per-tool metadata resolver, not Responses API
request metadata or an HTTP header. See the official OpenAI documentation:
https://developers.openai.com/api/docs/guides/tools-connectors-mcp

## Scope of delivery

This change updates the public source examples and wrapper definitions. It does
not publish a new Official Registry/server version, replace a prebuilt Dify
package, update marketplace installations, or enable analytics in third-party
accounts. Rebuild packages/import workflows from the reviewed source before
claiming their adoption. Use public test data and verify actual received session
metadata independently of aggregate historical warnings.
