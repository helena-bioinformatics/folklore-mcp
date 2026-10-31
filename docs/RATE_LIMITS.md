# Public request budgets

Publisher observation, 31 October 2026: the hosted MCP endpoint uses a
six-requests-per-minute budget per source IP, with burst allowance six.
Discovery, catalog listing, protocol negotiation and scientific calls all
consume that same POST budget. It is not a per-tool or per-conversation quota.
Clients behind a shared gateway or NAT share the allowance.

Other clients sharing source IP consume the same bucket. Simultaneous
connections are also bounded. The endpoint can return HTTP 429 without an
application or scientific failure.

## Handle HTTP 429 before interpreting evidence

The current hosted response supplies Retry-After: 10 and JSON-RPC error
code -32029. Preserve the response as a technical admission outcome. It is
not a gene, variant or publication not_found result. Do not replace it with
empty evidence, a classification or a result recalled from a model.

Stop the current operation on 429. Honor Retry-After for any explicitly
authorized later attempt. It can be delta-seconds or an HTTP-date; it is
optional under HTTP. A missing or malformed value needs a conservative
finite fallback, not a tight retry loop. A valid delay exceeding the job's
remaining time ends that job; do not shorten the server's hint to fit it.

Admission depends on the shared source-IP budget at request time. Honor
server cooldowns and origin/input checks. Replay eligibility is determined
by the operation contract.

## Shared-instance helper

[ops/client_rate_budget.py](../ops/client_rate_budget.py) supplies RateBudget.
It has no HTTP transport and never retries its callback. Reuse one instance
across all cooperating requests, including metadata calls. Its default
ten-second spacing and finite attempt count apply within that shared instance.

execute(operation, deadline=..., cancelled=...) admits at most one callback
per invocation. The deadline is an absolute monotonic time. The callback
receives remaining seconds and must apply that timeout to its transport.
Admission waiting, lock waiting and queued cancellation are checked locally.
An arbitrary synchronous callback cannot be force-cancelled in flight.
A callback returning after its deadline is rejected rather than reported as
a successful result. Cancellation also requires cooperation during I/O.

On a real HTTP 429, the transport raises RateLimited with its Retry-After
header. The instance records a cooldown and latches admission. Already queued
callbacks stop without sending. resume() is an explicit later decision:
it checks elapsed cooldown, deadline and cancellation under the same lock.
It neither sends a request nor resets attempt counts. Ordinary transport
exceptions also consume an attempt and release the lock without replay.

The lock is instance-local. Coordinate processes and hosts through a shared
caller-owned scheduler when they share egress.

## Existing discovery smoke

Run python3.12 ops/public_smoke.py from the repository root. Its four metadata
calls share one budget, start at least ten seconds apart, and stop on 429.
Each HTTP attempt rejects redirects, caps the body at 2 MiB and requires
JSON media, unambiguous JSON keys and a matching successful RPC identity.
It advertises JSON and event-stream acceptance but explicitly rejects SSE
in this JSON-response hosted-service check.

The smoke supplies an admission deadline ninety seconds ahead and passes
the smaller of twenty seconds or remaining time to the socket transport.
This is not a forcibly enforced total I/O deadline: DNS, slow reads or an
uncooperative transport can overrun it. A late callback cannot qualify success.
The check exercises four metadata methods. Scientific calls and SDK client
qualification have separate acceptance criteria.

Run the offline validation with
python3.12 -m pytest tests/test_client_rate_budget.py. It covers virtual-time
spacing, finite attempts, HTTP-date/delta Retry-After, cancellation, deadlines,
queued calls, atomic resume, error release and the actual metadata caller.
No live traffic or deliberately generated rate-limit responses are required.

For a single bounded scientific connection check, use the
[direct HTTP recipe](../integrations/direct-streamable-http/README.md).
Protocol compatibility and historical observations are recorded in
[client compatibility](COMPATIBILITY.md).

HTTP semantics: [429](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)
leaves the counting policy to the server and makes Retry-After optional.
[Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after)
defines delta-seconds and HTTP-date handling.
