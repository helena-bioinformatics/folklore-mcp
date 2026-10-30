# Public gene profiles

Folklore MCP 1.6.0 adds the public website's gene identity and source-qualified profile workflow. The adapter relays existing public evidence; it does not acquire datasets, infer biological facts or reconstruct private scientific logic. Enable `FOLKLORE_PUBLIC_GENE_ENABLED=true` for the standalone adapter. Gene literature additionally requires `FOLKLORE_LITERATURE_ENABLED=true`.

## Resolve before reading

Call `resolve_gene` with one printable public symbol, previous symbol, alias, HGNC, Ensembl or NCBI Gene identifier (1 to 128 characters):

```json
{"name":"resolve_gene","arguments":{"query":"BRCA1"}}
```

Preserve `exact`, `alias`, `ambiguous`, `not_found` and `withdrawn`. For ambiguity, show every returned candidate and require an explicit choice. Do not select the most familiar gene, substitute a replacement or interpret no match as biological absence. Gene-plus-HGVS expressions belong in `search_variant_evidence`.

After resolution, use the selected candidate's `identity.gene_id` and returned `identity_snapshot_id` as the required `snapshot_id` for all three subsequent tools. Snapshot identifiers are 64 lowercase hexadecimal characters. Do not reuse the example below with a fabricated snapshot:

```json
{"name":"get_gene_profile","arguments":{"gene_id":"HGNC:1100","snapshot_id":"<identity_snapshot_id returned by resolve_gene>"}}
```

## Profile sections and continuation

The profile preserves thirteen sections: `overview`, `disease_validity`, `structure`, `constraint`, `dosage`, `mechanisms`, `clinical_variants`, `clinical_variant_consequences`, `expression`, `gwas`, `phenotypes`, `protein_pathways` and `literature`.

`get_gene_section` requires the same `gene_id`, `snapshot_id` and one section name. `limit` is an integer from 1 to 50 (default 20); `cursor` is an opaque continuation value returned for that section. Preserve each assertion's provider, assembly, release, source links, coverage and limitations. Retain `total`, `observed_total`, count units, nulls and overlapping axes rather than summing unrelated counts. Unavailable or not integrated evidence is distinct from a source having no record.

Native GRCh37 transcript rows are reference evidence and do not expand the GRCh38 variant interpretation input contract. Constraint, GWAS associations, dosage and gene-disease validity are distinct evidence types; none alone establishes variant pathogenicity or a patient diagnosis.

If `snapshot_unavailable` is returned, restart resolution and reload the whole profile. Do not combine pages from different snapshots. Keep pagination cursors bound to their issuing gene, snapshot and section.

## Separate live literature

`search_gene_literature` requires the selected gene and snapshot. `limit` is an integer from 1 to 25 (default 20), `sort` is `relevance`, `newest` or `oldest`, and an optional opaque `cursor` continues the same gene/snapshot/sort capture.

The response preserves capture time/hash, publication links, match labels, degradation and pagination. This is query-matched discovery through the existing literature service, not guaranteed exact gene filtering or curated gene-disease evidence. Abstracts are excluded. A live capture is separate from the immutable profile's literature section and does not change variant classification.

## Results and safety

Every new tool returns `contract_version`, `result`, `record_url`, `usage_boundary` and `adapter_error`. Text-only clients receive the same complete envelope as JSON text. Scientific DTOs are validated before relay; invalid identity, snapshot, source, count or cursor bindings fail closed. No synthetic evidence replaces a transport or authority error. Snapshot conflicts, withdrawn identities, invalid cursors and unavailable capacity remain distinguishable.

Send public identifiers only. The tools accept no patient histories, phenotype narratives, family or segregation data, private case context or sequencing uploads. Gene evidence requires professional review and is not a diagnosis, treatment recommendation or variant classification.
