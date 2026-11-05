# Security policy

## Supported versions

Security fixes are provided for the latest release on the `main` branch.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to `security@helena.bio`.
Include a minimal reproducer with redacted secrets. We will acknowledge reports
and coordinate disclosure
after the issue has been assessed and remediated.

Do not open a public issue for an unpatched vulnerability.

## Opaque payload text

Scientific titles, abstracts, scientific limitations and error messages are
opaque payload strings. Transport integrity is evaluated using transport
metadata and the response contract.

## Hosted 2.0 adapter

Send API keys only in Authorization Bearer headers to the canonical endpoint. Do not publish keys, clinical records, exported cases or adapter state. Private tools use current API admission and credential-isolated encrypted journals. Report suspected cross-credential disclosure through the existing security contact.
