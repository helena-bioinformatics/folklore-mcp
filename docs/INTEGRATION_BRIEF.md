# Integrate Folklore classification into an AI workflow

Same endpoint: 11 anonymous public tools and 18 additional authenticated tools.
Supply a Folklore API key in the Authorization Bearer header. No local server
is required. See [case workflows](CASE_WORKFLOWS.md).

Folklore classifies and assesses identified GRCh38 germline variants under ACMG/AMP.
Gene, disease and literature tools provide source-qualified scientific context.
These eleven anonymous tools are hosted and read-only. Authenticated case
workflows use the same endpoint with a Folklore API key.

Endpoint: `https://api.helena.bio/folklore/v1/mcp`

## Select the task

| User question | Tool | Public input |
| --- | --- | --- |
| Classify and assess this germline variant. | `classify_germline_variant` | `{"assembly":"GRCh38","query":"NM_007294.4:c.68_69del"}` |
| Which diseases are associated with this gene? | `get_gene_disease_associations` | `{"gene":"FBN1"}` |
| Which genes are associated with this disease? | `search_disease_genes` | `{"disease":"Marfan syndrome"}` |
| Which papers discuss this variant? | `search_variant_literature` | Use the canonical identity returned by variant evidence; inspect the tool schema. |
| What is the approved identity of this public gene alias? | `resolve_gene` | `{"query":"RNF53"}` |
| What source-qualified evidence is available for the selected gene? | `get_gene_profile` | Use the selected returned HGNC identity and its returned snapshot, never a fabricated snapshot. |
| Continue one evidence section or find gene papers | `get_gene_section` or `search_gene_literature` | Keep the same selected gene and snapshot; continuation cursors are bound to the section or literature capture. |

The [per-tool task contracts](../registry/task-contracts.json) cover all ten
scientific tools, including corpus search and publication details. Literal
examples specify literal arguments. Response-bound recipes use values selected
from a successful response.
The [selection metadata](../registry/agent-selection.json) defines task routing.
GRCh38 assembly and variant statuses apply to the classification workflow.

The variant response already contains annotation, automated classification and
criteria, available ClinVar assertions, expert evidence, population frequencies,
predictors, source versions and explicit missing-data states. The gene-disease
tools preserve individual ClinGen assertions, including disputed assessments.
Variant classification, gene-disease validity assertions and literature matches
retain their separate producers and source semantics.

## Connection options

- [Hosted client setup](https://folklore.helena.bio/integrations)
- [Biomni stdio bridge and smoke check](../integrations/biomni/README.md)
- [Compatibility and protocol contract](COMPATIBILITY.md)
- [Schemas and coverage for gene-disease evidence](GENE_DISEASE_EVIDENCE.md)

Discover tools dynamically. With public capabilities enabled, the anonymous catalog
exposes ten scientific tools plus `support_helena`, a separate non-scientific
helper appropriate only when the user explicitly asks about supporting Helena.
Standalone capabilities use explicit feature gates. See [compatibility](COMPATIBILITY.md) and
[shared request budgets](RATE_LIMITS.md) before integration.

Before taking values from a response, check transport and JSON-RPC errors,
MCP isError and the route's domain outcome; check adapter_error where supplied
by that route contract. JSON Pointers in the
companion start at MCP CallToolResult, not the outer JSON-RPC response. Gene
identity and snapshot bindings must come from the same successful resolution
and explicitly selected candidate. Missing fields, unresolved ambiguity or identity/
snapshot mismatch stop the recipe. On snapshot_unavailable, resolve again;
do not substitute a newer snapshot or mix pages. The companion provides declarative input and output recipes.

Preserve source assertions, releases, native assemblies, count units and
pagination. The two gene-disease tools expose ClinGen Gene-Disease Validity
snapshots. Profile source sections and
a separate live, abstract-free gene-literature capture have different coverage
and provenance. Literature input accepts public phenotype, HPO and OMIM reference concepts.

Variant input is an identified public allele. Consult the named primary authority when the
latest ClinVar assertion, source release or broader literature/disease coverage
is required. Empty results describe the queried snapshot or corpus. Literature results
carry query-match labels; validity assertions carry their source assessments.

## Integration scope

Variant input is one public GRCh38 nuclear germline SNV or simple indel
smaller than 50 bp. Gene and disease tools accept the public identifiers and
names specified in their schemas.