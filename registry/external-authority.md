# External authority and outreach ledger

Last checked: 2026-08-30

This ledger prevents duplicate or spammy outreach. An owned adapter, issue,
submission or release asset is not independent adoption. Mark an item accepted
only when a maintainer-controlled public surface says so.

| Priority | Surface | Current evidence | Status | Next action |
| - | - | - | - | - |
| 1 | Stanford Biomni | [Issue #331](https://github.com/snap-stanford/Biomni/issues/331) and the tested `integrations/biomni` recipe | Open proposal; no labels, assignee, maintainer response, branch or pull request | Wait for maintainer feedback. Do not bump repeatedly. Submit a focused PR only if the maintainers invite it or their documented process permits it. |
| 2 | Biorouter | Reproducible `.brxt` builder, immutable release asset and live five-tool smoke test under `integrations/biorouter` | Publisher-owned integration artifact; no independent upstream acceptance is claimed | Identify Biorouter's current contribution policy and maintainer-controlled catalog before any submission. Reuse the existing pinned package and ambiguity probe. |
| 3 | MCPMed | Publisher dashboard submission in the Clinical Tools category | Pending moderator review; no durable public listing URL | Wait for the assigned public URL or a reasoned moderator response. Do not resubmit while pending. |
| 4 | Awesome Healthcare MCP Servers | [Issue #8](https://github.com/rdmgator12/awesome-healthcare-mcp-servers/issues/8) | Open submission; one comment; no acceptance evidence | Await maintainer action. If requirements are stated, make one scoped response; otherwise do not bump. |
| 5 | Awesome Medical AI Skills | [Pull request #2](https://github.com/JuneYaooo/awesome-medical-ai-skills/pull/2) | Open pull request; not merged | Keep canonical identity and version current only when requested by review or before merge. Do not open a duplicate PR. |

## Contribution boundary

Any integration contribution must preserve all of the following:

- exact endpoint and five-tool inventory for release 1.4.1;
- public variant-level inputs only;
- no patient, phenotype, family, segregation or private case data;
- pinned or otherwise reproducible setup;
- one deterministic `rs80357914` ambiguity probe;
- no automatic allele selection;
- source-linked output and returned provenance;
- qualified professional review and no diagnosis or treatment claim.

## Acceptance evidence

Acceptable evidence is a merged maintainer-controlled contribution, an
editorial listing, a documentation entry, or explicit maintainer feedback.
A publisher-authored issue, pull request, directory submission or website is
useful operational evidence but is not independent endorsement.

## Outreach rules

- Check this ledger and the linked thread before contacting anyone.
- Follow the destination's contribution instructions and code of conduct.
- Do not mass-submit the same copy to unrelated directories.
- Do not pay for links or request unsupported endorsements.
- Record rejection requirements and use them to choose the next target.
- Update `Last checked` and the exact public evidence when state changes.
