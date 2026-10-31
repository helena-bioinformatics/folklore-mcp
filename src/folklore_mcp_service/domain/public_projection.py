"""Public MCP presentation projection over validated authority responses."""

from copy import deepcopy
from typing import Any


def public_result(value: dict[str, Any]) -> dict[str, Any]:
    """Remove only owned presentation fields, preserving scientific source content."""
    result = deepcopy(value)
    result.pop("usage_boundary", None)
    if "contract_version" in result:
        result["contract_version"] = "2"
    if "contractVersion" in result:
        result["contractVersion"] = "2"
    variants = [result]
    variants.extend(
        result[key]
        for key in ("result", "variant_result")
        if isinstance(result.get(key), dict)
    )
    for variant in variants:
        interpretation = variant.get("interpretation")
        if isinstance(interpretation, dict):
            limitations = interpretation.get("limitations")
            if isinstance(limitations, dict):
                limitations.pop("diagnostic_use", None)
                limitations.pop("unavailable_context", None)
                if not limitations:
                    interpretation.pop("limitations")
    if isinstance(result.get("warnings"), list):
        warning_replacements = {
            "Reference assertions are not a diagnosis or variant classification. Coverage is limited to this ClinGen snapshot; missing associations do not establish absence. Distinct diseases and all evidence classifications are retained.": "Coverage is limited to this ClinGen snapshot; missing associations do not establish absence. Distinct diseases and all evidence classifications are retained.",
            "Local reference snapshot; not a patient diagnosis.": "Local reference snapshot.",
        }
        result["warnings"] = [
            warning_replacements.get(item, item) for item in result["warnings"]
        ]
    literature = result.get("literature")
    if isinstance(literature, dict) and isinstance(literature.get("limitations"), list):
        boilerplate = {
            "A literature association does not establish causality, pathogenicity or a diagnosis.",
            "Results are computational evidence for review by a qualified genetics professional.",
            "For professional review.",
        }
        literature["limitations"] = [
            item for item in literature["limitations"] if item not in boilerplate
        ]
    return result


def public_schema(
    value: dict[str, Any], *, error_schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Publish the v2 shape without altering internal upstream validators."""
    schema = deepcopy(value)
    props = schema.get("properties", {})
    props.pop("usage_boundary", None)
    if "required" in schema:
        schema["required"] = [
            key for key in schema["required"] if key != "usage_boundary"
        ]
    for key in ("contract_version", "contractVersion"):
        if key in props:
            version = "2"
            props[key]["const"] = version
            if "default" in props[key]:
                props[key]["default"] = version
    schema.get("$defs", {}).pop("UsageBoundary", None)
    if error_schema is not None:
        definitions = schema.pop("$defs", {})
        return {
            "type": "object",
            "$defs": definitions,
            "anyOf": [schema, deepcopy(error_schema)],
        }
    return schema
