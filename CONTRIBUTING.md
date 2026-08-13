# Contributing

Contributions that improve MCP compatibility, public contract validation,
documentation, tests or safe failure handling are welcome.

Before opening a pull request:

1. Keep the service read-only and stateless.
2. Do not add patient, phenotype, family or private case inputs.
3. Do not add credentials, private endpoints or deployment topology.
4. Preserve ambiguity and professional-review boundaries.
5. Run `pytest`, `ruff check .` and `ruff format --check .`.

Scientific resolver, annotation, evidence and ACMG/AMP changes belong to the
Folklore product rather than this protocol adapter.
