# Folklore Clinical Variant Interpretation for Dify

Official Helena Bioinformatics tools for read-only germline variant evidence,
variant literature, publication details, and biomedical corpus search.

No authentication is required. Outputs require professional review and must not
be used as diagnosis, treatment advice, or an autonomous clinical decision.

- Website: https://folklore.helena.bio
- Integration guide: https://folklore.helena.bio/integrations
- Source: https://github.com/helena-bioinformatics/folklore-mcp

## Install

Download
`dist/folklore-clinical-variant-interpretation-0.1.0.difypkg` and its
`.sha256` sidecar. Verify the archive, then in Dify open **Plugins**, choose
**Install plugin from local file**, and select the `.difypkg` file.

Rebuild reproducibly with Dify CLI `0.6.10`:

```bash
dify plugin package integrations/dify \
  -o folklore-clinical-variant-interpretation-0.1.0.difypkg
```
