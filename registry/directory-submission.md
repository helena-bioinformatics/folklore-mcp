# Folklore Clinical Variant Interpretation MCP directory submission

## Listing identity

- Name: Folklore Clinical Variant Interpretation MCP
- Publisher: Helena Bioinformatics
- Category: Clinical genetics research and decision support
- MCP endpoint: `https://api.helena.bio/folklore/v1/mcp`
- Authentication: None
- Website: `https://folklore.helena.bio`
- Custom icon URL: `https://folklore.helena.bio/images/logos/folklore.png`
- Privacy policy: `https://www.helena.bio/privacy`
- Terms of use: `https://www.helena.bio/terms`

## Short description

Clinical variant interpretation for one supported GRCh38 germline variant,
including public Folklore annotation, evidence, provenance, automated ACMG/AMP
decision support and related literature.

## Full description

Folklore Clinical Variant Interpretation MCP is the official public, read-only
MCP server from Helena Bioinformatics. It gives machines structured, read-only
access to the same public single-variant search shown by Folklore. It accepts coordinates,
supported genomic, coding and protein HGVS, SPDI or rsID. It returns explicit
resolved, ambiguous, not-found, invalid, unsupported and temporarily
unavailable outcomes. Ambiguous candidates are never selected automatically.

The service accepts no patient, phenotype, family or case record. Its automated
ACMG/AMP result is variant-level decision support and is not a diagnosis or a
substitute for qualified clinical interpretation.

## Tools

- `search_variant_evidence`: Search one supported GRCh38 germline nuclear SNV
  or simple indel smaller than 50 bp and return public evidence and provenance.
- `search_variant_literature`: Retrieve relevant publications for one supported
  GRCh38 germline variant from Folklore's public genetics literature corpus.
- `get_publication_details`: Retrieve the complete public bibliographic record
  for one PMID returned by Folklore literature search.
- `search_literature_corpus`: Search the public scientific Literature Corpus by
  natural-language question, publication identifier, gene, variant, phenotype,
  HPO or OMIM concept and return source-linked evidence candidates.

## Reviewer notes

- Remote stateless Streamable HTTP MCP server.
- Four read-only, non-destructive, idempotent tools.
- No authentication secret or user account is requested.
- No write operations, patient data, private systems or generative model.
- The tool preserves Folklore's evidence, ambiguity and safety limitations.
- Browser requests use an exact HTTPS origin allowlist; non-browser MCP clients
  may omit `Origin` as allowed by the transport.

## Intended users and safety boundary

Folklore is intended for qualified geneticists, molecular
biologists, laboratory professionals and researchers. It supplies traceable
variant evidence and an automated ACMG/AMP decision-support classification for
professional review. It does not provide patient diagnosis, treatment advice or
medical guidance to consumers. Clinically significant findings must be reviewed,
validated and confirmed by a qualified professional before clinical use.

The public variant tools accept only `assembly`, one variant `query`, and
bounded literature filters. Publication details accepts one PMID. Corpus search
accepts a bounded public scientific question and optional result controls. None
asks for or accepts a patient name, case identifier, patient phenotype, family
history, segregation evidence, clinical record or uploaded file.

## Example prompts

1. `Use Folklore Clinical Variant Interpretation MCP to classify ENST00000226413.5:c.317A>G under ACMG/AMP and summarize the evidence, provenance and limitations.`
2. `Resolve ENSP00000226413.5:p.Gln106Arg with Folklore and show the normalized GRCh38 variant and supporting evidence.`
3. `Search rs80357914 in Folklore. If it is ambiguous, show the candidates and ask me to choose rather than selecting one.`
4. `Search the Folklore Literature Corpus for BRCA1 homologous recombination studies and compare the source-linked evidence.`

## Anthropic submission disclosures

- Health data access: no patient or case data; the query is a single public
  variant identifier or notation.
- High-risk boundary: variant-level clinical decision support requiring review
  by a qualified genetics professional.
- AI disclosure: Claude produces the conversational explanation; Folklore
  supplies deterministic public evidence and automated classification data.
- Test account: not required; the endpoint and supported examples are public.
- Allowed link origin: `https://folklore.helena.bio`.
- Directory icon: use the custom Folklore icon URL above. Do not use the
  `api.helena.bio` favicon fallback because that host serves multiple products.
- Support: `privacy@helena.bio` for data protection and `security@helena.bio`
  for security concerns.
