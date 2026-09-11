# Gene-disease evidence in adapter 1.5.0

Use `get_gene_disease_associations` with `{"gene":"BRCA1","limit":20,"offset":0}` for an exact approved gene symbol, or supply an HGNC identifier. Use `search_disease_genes` with `{"disease":"MONDO:0007254","limit":20,"offset":0}` for an exact MONDO identifier, or a public disease-name substring such as `Marfan`.

These are request examples, not captured scientific results. Use the live response as evidence. Both tools accept `limit` from 1 to 50 (default 20) and `offset` from 0 to 1000 (default 0). Preserve pagination and reported limits; never present one page as the full catalogue. A disease-name substring may match several diseases. Keep their disease identifiers separate, and ask for clarification when the user's intended disease is unclear.

The first release exposes ClinGen Gene-Disease Validity assertions. Preserve returned gene and disease identifiers, assertion-level inheritance, evidence classification, source links and dates. Never attach an inheritance mode from one assertion to a different disease. Do not collapse contradictory assertions or replace a source assessment with model memory. Report missing values as unavailable.

The dataset covers curated assertions, not every gene or every known association. An empty result means no matching assertion in this source snapshot. It does not establish that a gene has no disease association. Association validity does not classify a particular variant or establish a diagnosis. Results require qualified professional review.

Send public identifiers/names only. Do not send patient, phenotype, family, segregation or private case data, VCFs, sequencing files or lists of patient variants. Gene/disease association lookup is not batch variant analysis, raw DNA sequence parsing or variant calling.
