# Folklore Clinical Variant Interpretation MCP distribution

Canonical public server title: `Folklore Clinical Variant Interpretation MCP`

Canonical Registry description: `Helena Bioinformatics MCP for clinical variant
interpretation, ACMG/AMP evidence and literature.`

Canonical identity: `io.github.helena-bioinformatics/folklore`

Canonical endpoint: `https://api.helena.bio/folklore/v1/mcp`

The server exposes five read-only tools: `search_variant_evidence`,
`search_variant_literature`, `get_publication_details` and
`search_literature_corpus`, plus the explicit opt-in `support_helena` tool. The
first three return public Folklore evidence and
related literature for one supported GRCh38 germline nuclear SNV or simple
indel. The corpus tool performs semantic-first scientific-literature retrieval;
PMID, DOI and PMCID values embedded in the question become exact publication
anchors. The server does not accept patient context and does not provide a
diagnosis.

`support_helena` returns the separate Helena Good campaign, rules, manifest,
and MCP links. It does not call the scientific gateway, initiate payment,
create outreach proof, or alter Folklore evidence and rankings.

Version 1.1 adds an MCP Apps resource for hosts that support inline UI. The
resource renders the same public Variant Evidence component used by
`folklore.helena.bio`; text-only MCP clients continue to receive the same
structured result and summary. The app is read-only and cannot call tools.

Reusable directory copy is in `directory-submission.md`, exact client
configurations are in `platforms/client-configs.json`, and the metadata-only
MCP package is in `packages/folklore`. These artifacts expose only the public
endpoint and contain no service source, credentials or private data.

The separate public repository at
`https://github.com/helena-bioinformatics/folklore-mcp` contains the approved
standalone MCP protocol adapter, public contracts and API clients, tests, CI,
packaging and distribution metadata. It is not metadata-only, and it is not the
Folklore interpretation backend. Public releases must exclude scientific
implementation, private data and datasets, credentials, internal routing and
deployment material, unrelated platform code and private Git history. The full
boundary and release review are documented in the canonical publication
contract and the public repository's `docs/PUBLIC_SOURCE_BOUNDARY.md`.

`discovery-contract.json` is the machine-readable desired state shared by
distribution tests and the read-only operator reconciler. Run from the repository
root:

```bash
python3 services/folklore_mcp_service/ops/reconcile_discovery.py
```

The canonical gate uses the Official Registry `version=latest` filter and
compares production `server/discover`, `tools/list`, `resources/list` and the
domain Server Card. Aggregator and editorial drift is visible but non-blocking
unless `--strict-aggregators` is selected. The reconciler performs no writes.

`agent-selection.json` is the machine-readable task-selection companion. It
defines positive and negative intents, brand-blind example requests, accepted
public input forms, the four scientific tool routes, typed outcomes and the
clinical boundary. `agent-selection.schema.json` provides its strict JSON
Schema. These files help agent catalogs index the user job rather than only the
server name; they do not replace the MCP tool schemas or claim universal model
selection.

MCP protocol `2026-07-28` is stateless. It uses `server/discover` as the optional
preflight and does not implement the retired `initialize` exchange. Legacy
compatibility, if justified by observed clients, must use an explicitly routed
older protocol contract rather than changing the current endpoint semantics.

Registry publication must happen only after production activation, live
`tools/list`/`tools/call` verification and Vladimir's final submission approval.

The official Registry version is published only from the signed source state
tagged `folklore-mcp-v<server.json version>`. The GitHub workflow validates the
record with a pinned publisher, authenticates through short-lived GitHub OIDC
and publishes the immutable version without repository secrets.
