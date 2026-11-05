# Authenticated case workflows

Use the existing hosted endpoint with an Authorization Bearer API key. Public
science remains available anonymously. Discovery is caller-dependent: 11 tools
without credentials and 29 with current admitted credentials.

## Tools

- `list_analysis_contexts`
- `submit_case_analysis`
- `get_case_analysis_status`
- `acknowledge_sequencing_qc_review`
- `request_sequencing_analysis_cancellation`
- `get_case_analysis_result_manifest`
- `download_analysis_result_file`
- `get_analysis_export_summary`
- `get_analysis_export_schema`
- `get_analysis_export_provenance`
- `get_analysis_export_variant`
- `query_analysis_export_records`
- `get_analysis_export_gene_records`
- `list_cases`
- `get_case`
- `list_case_analyses`
- `list_source_connections`
- `browse_source_objects`

## Processing and results

Select a context returned by list_analysis_contexts. Use only its admitted
source roots and a supported input profile. Source browsing returns bounded
metadata, not storage credentials or file contents. Submit with an explicit
native cost ceiling and an original idempotency key. Preserve that key and exact
request for recovery; an uncertain response does not authorize a replacement.

Poll the accepted analysis ID. A review acknowledgement requires the exact
current receipt identity. Cancellation is supported only by eligible sequencing
workflows, not every job. Read the result manifest before selecting an artifact.
The six JSON view tools inspect a selected frozen export without rerunning
scientific interpretation.

download_analysis_result_file verifies original bytes, size, checksum,
media type and current manifest, then returns download_url. Fetch this protected
API URL with the same Bearer credential. It contains no key or provider-signed
secret. It is not a public sharing link.

## Isolation and recovery

The hosted manager reauthorizes every private call and before returning data.
Credential-specific encrypted state and durable command journals are isolated
with a server HMAC namespace. Key rotation creates a new local namespace; it
does not inherit the old credential's recovery journal. Backend case visibility
follows the current stable principal and context authority.

Private results and authenticated catalogs are not publicly cached. Never send
clinical records through public literature or classification arguments.

## Optional adapter operation

Running this Apache adapter yourself is optional. Authenticated hosting requires
Linux filesystem locking, a single serving worker, private persistent state and:

- FOLKLORE_MCP_ENABLED=true
- FOLKLORE_MCP_CASES_ENABLED=true (default false)
- FOLKLORE_MCP_CASE_STATE_DIR: an absolute private persistent directory
- FOLKLORE_MCP_CASE_NAMESPACE_SECRET: 64 lowercase hex characters from 32 random
  bytes; preserve it with the private state
- FOLKLORE_MCP_CASE_MAX_NAMESPACES: default 1024, range 8..8192

The manager bounds live services and active calls to eight, authority requests
to eight, idle retention to 300 seconds and storage admission to 8 GiB.
Authority requests have a 30-second deadline. Capacity failures do not erase
journals. The API origin is fixed. Back up private state securely, never publish it.

Legacy stdio bridges support clients without remote HTTP. They are optional
client transports, not a second Folklore product.
