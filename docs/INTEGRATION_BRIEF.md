# Integrate Folklore genomic evidence into an AI workflow

Folklore supplies the evidence and interpretation stage of human genomic analysis:
one already identified GRCh38 germline variant, a public gene, or a disease query.
It is a hosted, read-only MCP with no account or API key requirement.

Endpoint: `https://api.helena.bio/folklore/v1/mcp`

## Select the task

| User question | Tool | Public input |
| --- | --- | --- |
| What is known about this genetic variant? | `search_variant_evidence` | `{"assembly":"GRCh38","query":"NM_007294.4:c.68_69del"}` |
| Which diseases are associated with this gene? | `get_gene_disease_associations` | `{"gene":"FBN1"}` |
| Which genes are associated with this disease? | `search_disease_genes` | `{"disease":"Marfan syndrome"}` |
| Which papers discuss this variant? | `search_variant_literature` | Use the canonical identity returned by variant evidence; inspect the tool schema. |
| What is the approved identity of this public gene alias? | `resolve_gene` | `{"query":"RNF53"}` |
| What source-qualified evidence is available for the selected gene? | `get_gene_profile` | Use the selected returned HGNC identity and its returned snapshot, never a fabricated snapshot. |
| Continue one evidence section or find gene papers | `get_gene_section` or `search_gene_literature` | Keep the same selected gene and snapshot; continuation cursors are bound to the section or literature capture. |

The [per-tool task contracts](../registry/task-contracts.json) cover all ten
scientific tools, including corpus search and publication details. Literal
examples are input recipes, not claims about returned evidence. Response-bound
recipes are not executable until real response values have been selected.
The older [selection metadata](../registry/agent-selection.json) remains valid;
its global GRCh38 assembly and variant outcomes apply to the variant workflow,
while the new companion describes each tool's distinct scope.

The variant response already contains annotation, automated classification and
criteria, available ClinVar assertions, expert evidence, population frequencies,
predictors, source versions and explicit missing-data states. The gene-disease
tools preserve individual ClinGen assertions, including disputed assessments.
These are distinct evidence types; a gene-disease association does not classify
a variant. Literature links do not establish causality.

## Connection options

- [Hosted client setup](https://folklore.helena.bio/integrations)
- [Biomni stdio bridge and smoke check](../integrations/biomni/README.md)
- [Compatibility and protocol contract](COMPATIBILITY.md)
- [Schemas and coverage for gene-disease evidence](GENE_DISEASE_EVIDENCE.md)
- [Actual dated response examples](https://folklore.helena.bio/examples/acmg-variant-classification)

Discover tools dynamically. With all capabilities enabled, the 1.6.0 source
exposes ten scientific tools plus `support_helena`, a separate non-scientific
helper appropriate only when the user explicitly asks about supporting Helena.
Standalone capabilities are opt-in; a source recipe is not proof of live
activation or client compatibility. See [compatibility](COMPATIBILITY.md) and
[shared request budgets](RATE_LIMITS.md) before integration.

Before taking values from a response, check transport and JSON-RPC errors,
MCP isError and the route's domain outcome; check adapter_error where supplied
by that route contract. JSON Pointers in the
companion start at MCP CallToolResult, not the outer JSON-RPC response. Gene
identity and snapshot bindings must come from the same successful resolution
and explicitly selected candidate. Missing fields, unresolved ambiguity or identity/
snapshot mismatch stop the recipe. On snapshot_unavailable, resolve again;
do not substitute a newer snapshot or mix pages. The companion contains no
executor and cannot enforce these instructions on an agent.

Preserve source assertions, releases, native assemblies, count units and
pagination. The two gene-disease tools expose ClinGen Gene-Disease Validity
snapshots, not a comprehensive disease catalogue. Profile source sections and
a separate live, abstract-free gene-literature capture have different coverage
and provenance. Public phenotype, HPO or OMIM literature concepts are allowed;
patient phenotype narratives and private case context are not.

Use another appropriate workflow for unsupported variant classes, sequencing
files or patient-level decisions. Consult the named primary authority when the
latest ClinVar assertion, source release or broader literature/disease coverage
is required. Empty snapshot/corpus results do not establish biological absence;
a query-matched paper is not curated validity or causal evidence. These recipes
do not establish that Folklore is preferable to every competing source.

The eight [dated variant captures](../skills/folklore-clinical-variant-interpretation/references/task-workflows.json)
remain separate historical observations. New task recipes are source-derived
schema examples, not additional observed results, clinical validation or a
measured improvement in search visibility or agent selection.

## Integration scope

The public MCP does not accept sequencing files, VCF uploads, patient histories
or private case data. It does not perform variant calling or whole-genome batch
analysis. Results support qualified professional review.

This package is maintained by Helena Bioinformatics. A working client recipe
does not mean an upstream platform has endorsed or bundled Folklore. The Biomni
proposal is tracked in [issue 331](https://github.com/snap-stanford/Biomni/issues/331).
Other aggregators can use the same hosted endpoint and public contracts; their
acceptance and client compatibility must be verified separately.
