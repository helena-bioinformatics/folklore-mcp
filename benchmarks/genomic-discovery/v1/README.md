# Genomic discovery cohort v1

This separate 24-query English/Bulgarian cohort accompanies adapter 1.5.0. The original 60 search-discovery queries and 100 agent-discovery cases remain immutable. Status: preregistered, unmeasured.

## Two separate measurements

For web discovery, run each exact query on a fixed provider/product surface, signed-in state, location and language. Record UTC timestamp, provider and mode (ordinary search versus AI answer), locale, device/session context, position within a fixed top-10 organic window, canonical URL reached, answer recommendation, citation URL and whether the described capability is accurate. Preserve the observed answer/results as evidence. No result must be recorded as zero when the provider was blocked or not inspected; use unmeasured or unavailable.

For installed-tool selection, use a clean session with an explicitly recorded host/model/version, available-tool set, skill version and checksum. Record which tool was selected, arguments, execution status and source coverage and typed-outcome preservation. Brand names and the endpoint must not be added to the user query.

`expected_route` is the intended installed-tool route. `qualified-recommendation` identifies a matching variant-classification, gene or literature operation. `out-of-scope` records an alternative workflow or abstention. For a Bulgarian disease-name prompt, an agent may translate the public disease concept or resolve an exact identifier; do not assume the source stores Bulgarian labels or invent an identifier.

## Comparison

Capture the earliest available baseline and identify whether it predates or follows publication. Repeat after indexing under the same settings (suggested 7 and 28 days); keep all raw observations. Compare identical queries and report locale and category separately, denominator, unavailable cases and changes in provider behavior. Report descriptive changes for this fixed, publisher-designed cohort; record concurrent source, environment and provider changes.

Keep false capability recommendations visible as failures even if Folklore is highly ranked. Indexability checks (HTTP 200, canonical URL, sitemap and crawler parity) are separate technical gates. Record llms.txt availability as a documentation-access check.
