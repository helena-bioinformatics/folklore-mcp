"""MCP presentation for source-attributed gene-disease reference assertions."""

import asyncio
import json
from typing import Any

import mcp.types as types
from pydantic import ValidationError

from folklore_mcp_service.application.gene_disease_gateway import (
    GeneDiseaseGateway,
    GeneDiseaseGatewayError,
)
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.gene_disease_contracts import (
    GeneDiseaseResponse,
    GetGeneDiseaseArguments,
    SearchDiseaseGenesArguments,
)
from folklore_mcp_service.domain.public_projection import public_result, public_schema

GENE_TOOL = "get_gene_disease_associations"
DISEASE_TOOL = "search_disease_genes"


def gene_disease_output_schema() -> dict[str, Any]:
    success = public_schema(GeneDiseaseResponse.model_json_schema())
    definitions = success.pop("$defs", {})
    error = {
        "type": "object",
        "additionalProperties": False,
        "required": ["contractVersion", "adapter_error"],
        "properties": {
            "contractVersion": {"const": "2"},
            "adapter_error": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "message", "retryable"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "retryable": {"type": "boolean"},
                },
            },
        },
    }
    return {"type": "object", "$defs": definitions, "anyOf": [success, error]}


def gene_disease_tools() -> list[types.Tool]:
    definitions = [
        (
            GENE_TOOL,
            "Find diseases associated with a gene",
            GetGeneDiseaseArguments,
            "Find diseases associated with an exact gene symbol or HGNC identifier. Returns ClinGen gene-disease validity assertions, relation-specific inheritance, source reports and snapshot provenance, including conflicting and limited assertions.",
        ),
        (
            DISEASE_TOOL,
            "Find genes associated with a disease",
            SearchDiseaseGenesArguments,
            "Find genes associated with an exact MONDO identifier or disease-name search. Returns ClinGen validity assertions with inheritance, source reports and snapshot provenance. Name searches can return multiple disease identities.",
        ),
    ]
    return [
        types.Tool(
            name=name,
            title=title,
            description=description,
            input_schema=model.model_json_schema(),
            output_schema=gene_disease_output_schema(),
            annotations=types.ToolAnnotations(
                title=title,
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        )
        for name, title, model, description in definitions
    ]


def reference_error(code: str, message: str, retryable: bool) -> types.CallToolResult:
    result = {
        "contractVersion": "2",
        "adapter_error": {"code": code, "message": message, "retryable": retryable},
    }
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(result))],
        structured_content=result,
        is_error=True,
    )


async def call_gene_disease_tool(
    *,
    params: types.CallToolRequestParams,
    gateway: GeneDiseaseGateway,
    settings: Settings,
    semaphore: asyncio.Semaphore,
    observe: Any | None,
) -> types.CallToolResult:
    model, kind = (
        (GetGeneDiseaseArguments, "genes")
        if params.name == GENE_TOOL
        else (SearchDiseaseGenesArguments, "diseases")
    )
    try:
        arguments = model.model_validate(params.arguments or {})
    except (ValidationError, ValueError):
        return reference_error(
            "invalid_arguments",
            "Supply only a public gene or disease identifier and pagination.",
            False,
        )
    started = asyncio.get_running_loop().time()
    outcome = "internal_failure"
    try:
        async with asyncio.timeout(settings.FOLKLORE_MCP_DEADLINE_SECONDS):
            async with semaphore:
                response = await gateway.search(kind, arguments.model_dump(mode="json"))
        outcome = response.status
        result = public_result(response.model_dump(mode="json"))
        # Include the source assertions in text-only clients, with identical evidence.
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text", text=json.dumps(result, ensure_ascii=False)
                )
            ],
            structured_content=result,
            is_error=False,
        )
    except TimeoutError:
        outcome = "upstream_timeout"
        return reference_error(
            outcome, "Gene-disease reference evidence timed out.", True
        )
    except GeneDiseaseGatewayError as exc:
        outcome = exc.code
        return reference_error(exc.code, str(exc), exc.retryable)
    finally:
        if observe is not None:
            observe(params.name, outcome, asyncio.get_running_loop().time() - started)
