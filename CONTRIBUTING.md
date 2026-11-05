# Contributing

Contributions that improve MCP compatibility, public contract validation,
documentation, tests or safe failure handling are welcome.

Before opening a pull request:

1. Keep anonymous scientific queries read-only; route authenticated writes through the admitted API with durable idempotency.
2. Preserve public science contracts and the authenticated case schemas.
3. Do not add credentials, private endpoints or deployment topology.
4. Preserve exact identity, ambiguity, typed errors and source provenance.
5. Run `pytest`, `ruff check .` and `ruff format --check .`.

Scientific resolver, annotation, evidence and ACMG/AMP changes belong to the
Folklore product rather than this protocol adapter.

## Hosted 2.0 adapter

Case API clients, strict schemas, encrypted recovery and frozen-export queries belong to this adapter. Scientific authorities remain excluded. Use synthetic fixtures. Run python ops/check_public_export.py --base HEAD plus all CI checks before export.
