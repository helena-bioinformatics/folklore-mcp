"""Four read-only public gene workflow tools over the existing authority."""

import asyncio
import json
from typing import Any
from urllib.parse import quote

import mcp.types as types
from pydantic import ValidationError

from folklore_mcp_service.application.public_gene_gateway import (
    PublicGeneGateway,
    PublicGeneGatewayError,
)
from folklore_mcp_service.domain.public_gene_contracts import (
    PUBLIC_GENE_ARGUMENTS,
)
from folklore_mcp_service.domain.public_projection import public_schema

PUBLIC_GENE_TOOL_OPERATIONS = {
    "resolve_gene": "resolve",
    "get_gene_profile": "profile",
    "get_gene_section": "section",
    "search_gene_literature": "literature",
}
PUBLIC_GENE_TOOL_NAMES = frozenset(PUBLIC_GENE_TOOL_OPERATIONS)


def public_gene_output_schema(operation: str) -> dict:
    """Scientific DTOs are fully validated at runtime, as for variant evidence."""
    result_required = {
        "resolve": [
            "schema_version",
            "request_id",
            "identity_snapshot_id",
            "status",
            "candidates",
            "candidate_total",
            "complete",
        ],
        "profile": [
            "schema_version",
            "gene_id",
            "request_id",
            "snapshot_id",
            "identity",
            "sources",
            "sections",
        ],
        "section": [
            "gene_id",
            "request_id",
            "snapshot_id",
            "section",
            "status",
            "coverage",
            "data",
            "pagination",
        ],
        "literature": [
            "schema_version",
            "gene_id",
            "request_id",
            "snapshot_id",
            "captured_at",
            "capture_sha256",
            "records",
            "returned",
            "has_more",
            "next_cursor",
        ],
    }[operation]
    return public_schema(
        {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "contract_version",
                "result",
                "record_url",
                "usage_boundary",
                "adapter_error",
            ],
            "properties": {
                "contract_version": {"type": "string", "const": "1"},
                "result": {
                    "anyOf": [
                        {
                            "type": "object",
                            "required": result_required,
                            "additionalProperties": True,
                        },
                        {"type": "null"},
                    ]
                },
                "record_url": {"type": ["string", "null"], "format": "uri"},
                "adapter_error": {
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "code",
                                "message",
                                "retryable",
                                "available_snapshot_id",
                            ],
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                                "retryable": {"type": "boolean"},
                                "available_snapshot_id": {
                                    "type": ["string", "null"],
                                    "pattern": "^[a-f0-9]{64}$",
                                },
                            },
                        },
                        {"type": "null"},
                    ]
                },
            },
        }
    )


def public_gene_tools(*, literature_enabled: bool) -> list[types.Tool]:
    definitions = [
        (
            "resolve_gene",
            "Resolve a gene symbol, alias or stable identifier",
            "Resolve a human gene symbol, previous symbol, alias, HGNC, Ensembl or NCBI Gene identifier. Returns exact, alias, ambiguous, not_found or withdrawn status with candidates and identity_snapshot_id. Use a selected HGNC gene_id and snapshot_id with get_gene_profile. Gene-plus-HGVS and variant expressions use classify_germline_variant.",
        ),
        (
            "get_gene_profile",
            "Read the complete gene profile",
            "Read the selected gene_id and immutable snapshot_id from resolve_gene. Returns overview, disease validity, dosage, mechanisms, transcripts, native assemblies, constraint, ClinVar summaries and consequences, expression, GWAS, phenotypes and protein/pathways with source assertions, coverage, count units and null values. get_gene_section supplies further pages. Live search_gene_literature is separate from the snapshot literature section.",
        ),
        (
            "get_gene_section",
            "Read a page of gene records",
            "Read a gene-profile section using gene_id, snapshot_id and its returned opaque cursor. Returns source records, assembly/release, coverage, totals, count units and provenance. snapshot_unavailable requires a fresh resolution/profile request.",
        ),
        (
            "search_gene_literature",
            "Find live literature for a resolved public gene",
            "Retrieve a live publication capture for a resolved gene_id and snapshot_id. Returns source links, match labels, capture time/hash, degradation and gene/snapshot/sort-bound cursors. This capture is separate from the immutable reference snapshot and contains no abstracts.",
        ),
    ]
    return [
        types.Tool(
            name=name,
            title=title,
            description=description,
            input_schema=PUBLIC_GENE_ARGUMENTS[
                PUBLIC_GENE_TOOL_OPERATIONS[name]
            ].model_json_schema(),
            output_schema=public_gene_output_schema(PUBLIC_GENE_TOOL_OPERATIONS[name]),
            annotations=types.ToolAnnotations(
                title=title,
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        )
        for name, title, description in definitions
        if literature_enabled or name != "search_gene_literature"
    ]


def _result(
    *, result: dict | None = None, error: PublicGeneGatewayError | None = None
) -> types.CallToolResult:
    symbol = result.get("canonical_symbol") if result else None
    if (
        result
        and result.get("status") in {"exact", "alias"}
        and len(result.get("candidates", [])) == 1
    ):
        identity = result["candidates"][0]["identity"]
        if identity["status"] == "Approved":
            symbol = identity["symbol"]
    structured = {
        "contract_version": "2",
        "result": result,
        "record_url": f"https://folklore.helena.bio/gene/{quote(symbol, safe='')}"
        if symbol
        else None,
        "adapter_error": {
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
            "available_snapshot_id": error.available_snapshot_id,
        }
        if error
        else None,
    }
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(
                    structured,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                ),
            )
        ],
        structured_content=structured,
        is_error=error is not None,
    )


async def call_public_gene_tool(
    *,
    params,
    gateway: PublicGeneGateway,
    settings,
    semaphore: asyncio.Semaphore,
    observe: Any | None = None,
) -> types.CallToolResult:
    started = asyncio.get_running_loop().time()
    outcome = "internal_failure"
    try:
        operation = PUBLIC_GENE_TOOL_OPERATIONS.get(params.name)
        if operation is None:
            outcome = "invalid_request"
            return _result(
                error=PublicGeneGatewayError(
                    "unknown_tool", "Unknown public gene tool.", retryable=False
                )
            )
        try:
            arguments = PUBLIC_GENE_ARGUMENTS[operation].model_validate(
                params.arguments or {}
            )
        except (ValidationError, ValueError):
            outcome = "invalid_request"
            return _result(
                error=PublicGeneGatewayError(
                    "invalid_arguments",
                    "Supply only the public gene identifiers, snapshot and bounded pagination required by this tool.",
                    retryable=False,
                )
            )
        async with asyncio.timeout(settings.FOLKLORE_MCP_DEADLINE_SECONDS):
            async with semaphore:
                result = await gateway.request(
                    operation, arguments.model_dump(mode="json", exclude_none=True)
                )
        outcome = result.get("status", "ok")
        if outcome in {
            "exact",
            "alias",
            "available",
            "source_has_no_record",
            "unavailable",
            "not_integrated",
            "not_applicable",
        }:
            outcome = "ok"
        return _result(result=result)
    except TimeoutError:
        outcome = "upstream_timeout"
        return _result(
            error=PublicGeneGatewayError(
                outcome, "Public gene evidence timed out.", retryable=True
            )
        )
    except PublicGeneGatewayError as exc:
        outcome = exc.code
        return _result(error=exc)
    finally:
        if observe is not None:
            observe(params.name, outcome, asyncio.get_running_loop().time() - started)
