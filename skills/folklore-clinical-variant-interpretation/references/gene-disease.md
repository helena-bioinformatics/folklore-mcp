# Gene-disease assertions

`get_gene_disease_associations` accepts an exact approved gene symbol or HGNC
identifier, for example `{"gene":"BRCA1","limit":20,"offset":0}`.
`search_disease_genes` accepts an exact MONDO identifier or public disease-name
substring, for example `{"disease":"Marfan","limit":20,"offset":0}`.

Both accept `limit` from 1 to 50 (default 20) and `offset` from 0 to 1000
(default 0). Follow returned pagination. Keep distinct disease identifiers and
assertion-level inheritance, validity classification, panel, source links and
dates. Missing source values remain unavailable.

The source is the reported ClinGen Gene-Disease Validity snapshot. Empty results
mean no matching assertion in that query/snapshot. Variant classification and
gene-disease validity have separate output contracts.
