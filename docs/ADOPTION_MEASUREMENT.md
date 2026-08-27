# Privacy-preserving adoption measurement

Folklore Clinical Variant Interpretation MCP adoption should be measured with
bounded aggregate events, not by retaining scientific queries or identifying
users.

## Allowed aggregate measures

- Counts of public MCP discovery and tool calls by coarse surface.
- Counts of typed outcomes such as resolved, ambiguous, invalid, unsupported
  and temporarily unavailable.
- Aggregate reliability, latency and error-rate distributions.
- Public referral or directory source when supplied without user identity.

## Data that must not be collected for outreach measurement

- Variant expressions, coordinates, HGVS, rsIDs, genes or classifications.
- Patient, phenotype, family, segregation or private case data.
- IP addresses, user-agent strings, cookies, fingerprints or account identity.
- Full URLs or query strings that could contain scientific input.

Report only sufficiently aggregated trends. Do not infer individuals,
institutions, diagnoses or clinical activity. Adoption metrics measure public
tool use and discoverability, not clinical validity or patient outcomes.
