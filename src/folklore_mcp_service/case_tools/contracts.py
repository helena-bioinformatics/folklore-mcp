"""Versioned input, source DTO and MCP output contracts for case tools."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, validators

from .common import VERSION, CaseError, json_bytes
from .discovery import PACKET as DISCOVERY_PACKET
from .discovery import TOOLS as DISCOVERY_TOOLS
from .source_browse import PACKET as SOURCE_BROWSE_PACKET
from .source_browse import TOOL as SOURCE_BROWSE_TOOL

_DATA = Path(__file__).with_name("data")
API_PACKET = json.loads((_DATA / "phase1-api-schemas.json").read_text())
EXPORT_PACKET = json.loads((_DATA / "phase1-export-contract.json").read_text())
INPUT_SCHEMAS = json.loads((_DATA / "phase1-tool-input-schemas.json").read_text())[
    "tools"
]


def _prune_definitions(schema: dict) -> dict:
    """Keep only definitions reached by local references in this tool schema."""
    result = copy.deepcopy(schema)
    definitions = result.pop("$defs", {})
    needed = set()

    def visit(value):
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref.split("/")[2].replace("~1", "/").replace("~0", "~")
                if name not in definitions:
                    raise ValueError("Unresolved tool schema reference")
                if name not in needed:
                    needed.add(name)
                    visit(definitions[name])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)
    if needed:
        result["$defs"] = {name: definitions[name] for name in sorted(needed)}
    return result


INPUT_SCHEMAS.update(DISCOVERY_PACKET["input_schemas"])
INPUT_SCHEMAS[SOURCE_BROWSE_TOOL] = SOURCE_BROWSE_PACKET["input_schema"]

INPUT_SCHEMAS = {
    name: _prune_definitions(schema) for name, schema in INPUT_SCHEMAS.items()
}

API_TOOLS = tuple(API_PACKET["input_schemas"])
EXPORT_TOOLS = tuple(EXPORT_PACKET["input_schemas"])
TOOLS = API_TOOLS + EXPORT_TOOLS + DISCOVERY_TOOLS + (SOURCE_BROWSE_TOOL,)
WRITE_TOOLS = frozenset(
    (
        "submit_case_analysis",
        "acknowledge_sequencing_qc_review",
        "request_sequencing_analysis_cancellation",
    )
)
StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer",
        lambda checker, item: isinstance(item, int) and not isinstance(item, bool),
    ),
)


def validate_input(name: str, arguments: dict) -> dict:
    if name not in INPUT_SCHEMAS:
        raise CaseError("unknown_tool")
    if not isinstance(arguments, dict):
        raise CaseError("invalid_input")
    try:
        raw = json_bytes(arguments)
    except (TypeError, ValueError, RecursionError):
        raise CaseError("invalid_input") from None
    if len(raw) > 1048576:
        raise CaseError(
            "invalid_input", details={"limit_name": "command_bytes", "limit": 1048576}
        )
    errors = StrictValidator(
        INPUT_SCHEMAS[name], format_checker=FormatChecker()
    ).iter_errors(arguments)
    if next(errors, None) is not None:
        raise CaseError("invalid_input")
    if name == SOURCE_BROWSE_TOOL and len(raw) > 32768:
        raise CaseError(
            "invalid_input", details={"limit_name": "command_bytes", "limit": 32768}
        )
    if name == "list_cases" and chr(0) in arguments.get("query", ""):
        raise CaseError("invalid_input")
    if name == "submit_case_analysis":
        if int(arguments["max_cost_units"]) > 9223372036854775807:
            raise CaseError("invalid_input")
        from .validation import validate_submit

        validate_submit(arguments)
    return copy.deepcopy(arguments)


def validate_source(name: str, value: dict) -> dict:
    definition = API_PACKET["api_output_structural_contracts"][name]
    schema = copy.deepcopy(definition["source_schema"])
    schema["$defs"] = API_PACKET["$defs"]
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value):
        raise CaseError("invalid_upstream_response")
    return value


def _wire_schema(value):
    if isinstance(value, list):
        return [_wire_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _wire_schema(item) for key, item in value.items()}
    types = value.get("type")
    members = types if isinstance(types, list) else [types]
    if "integer" in members or "number" in members:
        integer = "integer" in members and "number" not in members
        converted = [
            "string" if item in ("integer", "number") else item for item in members
        ]
        result["type"] = (
            list(dict.fromkeys(converted)) if isinstance(types, list) else converted[0]
        )
        result["pattern"] = (
            r"^-?(?:0|[1-9][0-9]*)$"
            if integer
            else r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$"
        )
        result["maxLength"] = 1024
        for key in (
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "multipleOf",
        ):
            result.pop(key, None)
    for key in ("const", "default"):
        if (
            key in value
            and isinstance(value[key], (int, float))
            and not isinstance(value[key], bool)
        ):
            result[key] = json_bytes(value[key]).decode("ascii")
    if "enum" in value:
        result["enum"] = [
            json_bytes(item).decode("ascii")
            if isinstance(item, (int, float)) and not isinstance(item, bool)
            else item
            for item in value["enum"]
        ]
    return result


_ERROR = EXPORT_PACKET["output_schemas"]["get_analysis_export_summary"]["$defs"][
    "error"
]


def output_schema(name: str) -> dict:
    if name in EXPORT_TOOLS:
        return copy.deepcopy(EXPORT_PACKET["output_schemas"][name])
    if name == "download_analysis_result_file":
        fields = {
            key: {"type": "string"}
            for key in (
                "analysis_id",
                "case_id",
                "generation_id",
                "artifact_id",
                "sha256",
                "size_bytes",
                "media_type",
                "expires_at",
                "local_path",
            )
        }
        payload = {
            "type": "object",
            "properties": fields,
            "required": list(fields),
            "additionalProperties": False,
        }
        member = "file"
    elif name == SOURCE_BROWSE_TOOL:
        payload = _wire_schema(SOURCE_BROWSE_PACKET["api_result_schema"])
        member = "result"
    else:
        payload = _wire_schema(
            DISCOVERY_PACKET["api_result_schemas"][name]
            if name in DISCOVERY_TOOLS
            else API_PACKET["api_output_structural_contracts"][name]["source_schema"]
        )
        member = "result"
    data = {
        "type": "object",
        "properties": {
            "contract_version": {"const": VERSION},
            "source_operation": {"const": name},
            member: payload,
        },
        "required": ["contract_version", "source_operation", member],
        "additionalProperties": False,
    }
    error_defs = copy.deepcopy(
        EXPORT_PACKET["output_schemas"]["get_analysis_export_summary"]["$defs"]
    )
    error_defs.update(_wire_schema(API_PACKET["$defs"]))
    if name in DISCOVERY_TOOLS:
        error_defs.update(_wire_schema(DISCOVERY_PACKET["$defs"]))
    if name == SOURCE_BROWSE_TOOL:
        error_defs.update(_wire_schema(SOURCE_BROWSE_PACKET["$defs"]))
    return {
        "type": "object",
        "oneOf": [
            {
                "type": "object",
                "properties": {"ok": {"const": True}, "data": data},
                "required": ["ok", "data"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "ok": {"const": False},
                    "error": {"$ref": "#/$defs/error"},
                },
                "required": ["ok", "error"],
                "additionalProperties": False,
            },
        ],
        "$defs": error_defs,
    }


OUTPUT_SCHEMAS = {name: _prune_definitions(output_schema(name)) for name in TOOLS}


def validate_output(name: str, result: dict) -> None:
    if not Draft202012Validator(
        OUTPUT_SCHEMAS[name], format_checker=FormatChecker()
    ).is_valid(result):
        raise CaseError("invalid_tool_response")


DESCRIPTIONS = {
    "list_analysis_contexts": "List the contexts and analysis profiles admitted for the configured API key.",
    "submit_case_analysis": "Submit one case analysis with an explicit context, immutable S3 input, cost ceiling and idempotency key.",
    "get_case_analysis_status": "Read the current analysis stage, outcome, sequencing review and billing state.",
    "acknowledge_sequencing_qc_review": "Record an explicit acknowledgement of the exact sequencing QC review receipt.",
    "request_sequencing_analysis_cancellation": "Request cancellation of sequencing analysis and return its current state.",
    "get_case_analysis_result_manifest": "Read and verify the published analysis result manifest.",
    "download_analysis_result_file": "Save a verified original result file and return its local path, size and digest.",
    "get_analysis_export_summary": "Read the frozen export summary, coverage and collection availability.",
    "get_analysis_export_schema": "Describe the frozen export fields, exact numeric encoding and supported query operators.",
    "query_analysis_export_records": "Filter, sort, project and page one collection in a verified frozen analysis export.",
    "get_analysis_export_variant": "Read one exact generation-local variant record from the frozen export.",
    "get_analysis_export_gene_records": "Page one frozen export collection for an exact source gene symbol.",
    "get_analysis_export_provenance": "Read the recorded clinical profile, source hashes, classifier and export identities.",
}

DESCRIPTIONS[SOURCE_BROWSE_TOOL] = (
    "Browse one level of explicitly permitted S3 sources and select an actual immutable file version."
)

DESCRIPTIONS.update(
    {
        "list_cases": "List cases linked to this machine principal's accepted Partner API commands in one selected context; optional literal case-name search.",
        "get_case": "Read the operational header and latest partner-command summary of one machine-owned case in the selected context.",
        "list_case_analyses": "Page compact accepted partner-command history for one machine-owned case; this is not native reanalysis/execution history.",
        "list_source_connections": "List the selected context's currently admitted S3 root grants, preserving source order and duplicates; no provider browsing or health check.",
    }
)
