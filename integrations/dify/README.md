# Folklore Clinical Variant Interpretation for Dify

Automated ACMG/AMP germline variant classification, source evidence,
variant literature, publication details, and biomedical corpus search.

Access is anonymous. The tools return automated classification, source evidence
and literature records.

- Website: https://folklore.helena.bio
- Integration guide: https://folklore.helena.bio/integrations
- Source: https://github.com/helena-bioinformatics/folklore-mcp

## Install

Download
`dist/folklore-clinical-variant-interpretation-0.2.0.difypkg` and its
`.sha256` sidecar. Verify the archive, then in Dify open **Plugins**, choose
**Install plugin from local file**, and select the `.difypkg` file.

Rebuild reproducibly with Dify CLI `0.6.10`:

```bash
dify plugin package integrations/dify \
  -o folklore-clinical-variant-interpretation-0.2.0.difypkg
```

## Optional journey context

Optional analytics configuration: [journey context](../JOURNEY_CONTEXT.md).
