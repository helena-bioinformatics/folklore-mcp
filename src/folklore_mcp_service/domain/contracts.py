"""Closed adapter contracts around the authoritative Folklore search result."""

from typing import Annotated, Any, Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

VariantQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]
SearchStatus = Literal[
    "resolved",
    "ambiguous",
    "not_found",
    "invalid_request",
    "unsupported",
    "resolution_unavailable",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchVariantArguments(StrictModel):
    """The only public scientific input admitted by the MCP tool."""

    assembly: Annotated[
        Literal["GRCh38"],
        Field(
            description=(
                "Reference genome assembly. Folklore currently accepts GRCh38 only."
            )
        ),
    ] = "GRCh38"
    query: Annotated[
        VariantQuery,
        Field(
            description=(
                "One germline nuclear SNV or simple indel to resolve and interpret; "
                "accepted forms include coordinates, genomic/coding/protein HGVS, "
                "SPDI, rsID, or a returned Folklore canonical_key in "
                "GRCh38:chrN:position:REF:ALT form."
            )
        ),
    ]


class CanonicalIdentity(StrictModel):
    assembly: Literal["GRCh38"]
    chromosome: Annotated[
        str, StringConstraints(pattern=r"^chr(?:[1-9]|1[0-9]|2[0-2]|X|Y)$")
    ]
    position: Annotated[int, Field(gt=0)]
    reference: Annotated[str, StringConstraints(pattern=r"^[ACGT]+$", max_length=50)]
    alternate: Annotated[str, StringConstraints(pattern=r"^[ACGT]+$", max_length=50)]
    variant_type: Literal["SNV", "INS", "DEL"]
    canonical_key: Annotated[str, StringConstraints(min_length=1, max_length=180)]

    @model_validator(mode="after")
    def validate_key(self) -> "CanonicalIdentity":
        expected = (
            f"{self.assembly}:{self.chromosome}:{self.position}:"
            f"{self.reference}:{self.alternate}"
        )
        if self.canonical_key != expected:
            raise ValueError("canonical key does not match identity")
        return self


class UpstreamContractError(ValueError):
    """The variant authority returned a response outside contract 1.0."""


def usage_boundary() -> dict[str, Any]:
    """Return the stable machine-readable boundary for every tool outcome."""

    return {
        "result_type": "automated_variant_level_classification",
        "review_required": True,
        "patient_context_evaluated": False,
        "intended_use": "professional_variant_review",
        "not_for": [
            "patient_diagnosis",
            "treatment_decision",
            "standalone_clinical_reporting",
        ],
    }


_TOP_LEVEL_KEYS: dict[str, frozenset[str]] = {
    "resolved": frozenset(
        {
            "search_contract_version",
            "status",
            "resolution",
            "identity",
            "interpretation",
        }
    ),
    "ambiguous": frozenset(
        {
            "search_contract_version",
            "status",
            "resolution",
            "error",
            "total_candidate_count",
            "candidates_truncated",
            "candidates",
        }
    ),
    "not_found": frozenset(
        {"search_contract_version", "status", "resolution", "error"}
    ),
    "invalid_request": frozenset(
        {"search_contract_version", "status", "resolution", "error"}
    ),
    "unsupported": frozenset(
        {"search_contract_version", "status", "resolution", "error"}
    ),
    "resolution_unavailable": frozenset(
        {"search_contract_version", "status", "resolution", "error"}
    ),
}


def validate_upstream_result(value: Any) -> dict[str, Any]:
    """Validate the owned envelope and preserve the upstream scientific DTO."""

    if not isinstance(value, dict):
        raise UpstreamContractError("response is not an object")
    status = value.get("status")
    if status not in _TOP_LEVEL_KEYS:
        raise UpstreamContractError("unknown search status")
    if value.get("search_contract_version") != "1.0":
        raise UpstreamContractError("unsupported search contract version")
    if frozenset(value) != _TOP_LEVEL_KEYS[status]:
        raise UpstreamContractError("unexpected top-level response fields")

    if status == "resolved":
        if not isinstance(value.get("resolution"), dict):
            raise UpstreamContractError("resolved response omitted resolution")
        identity = CanonicalIdentity.model_validate(value.get("identity"))
        interpretation = value.get("interpretation")
        if not isinstance(interpretation, dict):
            raise UpstreamContractError("resolved response omitted interpretation")
        if interpretation.get("contract_version") != "1.0":
            raise UpstreamContractError("unsupported interpretation contract version")
        if interpretation.get("status") not in {"success", "unavailable"}:
            raise UpstreamContractError("unknown interpretation status")
        if interpretation.get("identity") != identity.model_dump(mode="json"):
            raise UpstreamContractError("resolved and interpreted identities differ")
        if interpretation["status"] == "success":
            _validate_summary_fields(interpretation)
        else:
            _validate_typed_error(interpretation.get("error"))
    elif status == "ambiguous":
        if not isinstance(value.get("resolution"), dict):
            raise UpstreamContractError("ambiguous response omitted resolution")
        candidates = value.get("candidates")
        total = value.get("total_candidate_count")
        truncated = value.get("candidates_truncated")
        if (
            not isinstance(candidates, list)
            or not candidates
            or len(candidates) > 10
            or isinstance(total, bool)
            or not isinstance(total, int)
            or total < len(candidates)
            or not isinstance(truncated, bool)
            or truncated != (total > len(candidates))
        ):
            raise UpstreamContractError("invalid ambiguous candidate envelope")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise UpstreamContractError("invalid candidate")
            CanonicalIdentity.model_validate(candidate.get("identity"))
    else:
        if status == "not_found" and not isinstance(value.get("resolution"), dict):
            raise UpstreamContractError("not-found response omitted resolution")
        if (
            status in {"invalid_request", "unsupported", "resolution_unavailable"}
            and value.get("resolution") is not None
            and not isinstance(value.get("resolution"), dict)
        ):
            raise UpstreamContractError("error response has invalid resolution")
        _validate_typed_error(value.get("error"))
    return value


def _validate_typed_error(value: Any) -> None:
    if not isinstance(value, dict):
        raise UpstreamContractError("error outcome omitted typed error")
    if (
        not isinstance(value.get("code"), str)
        or not isinstance(value.get("message"), str)
        or not 1 <= len(value["code"]) <= 128
        or not 1 <= len(value["message"]) <= 4_096
    ):
        raise UpstreamContractError("error outcome is not typed")
    if not isinstance(value.get("retryable"), bool):
        raise UpstreamContractError("error retryability is not boolean")


def _validate_summary_fields(interpretation: dict[str, Any]) -> None:
    required_strings = (
        ("display", "label"),
        ("annotation", "gene_symbol"),
        ("classification", "automated_class"),
        ("limitations", "diagnostic_use"),
        ("limitations", "unavailable_context"),
    )
    for group, field in required_strings:
        container = interpretation.get(group)
        if (
            not isinstance(container, dict)
            or not isinstance(container.get(field), str)
            or not 1 <= len(container[field]) <= 4_096
        ):
            raise UpstreamContractError("interpretation omitted bounded summary fields")
    criteria = interpretation["classification"].get("criteria")
    if criteria is not None and (
        not isinstance(criteria, str) or len(criteria) > 4_096
    ):
        raise UpstreamContractError("classification criteria has invalid type")


def record_url(result: dict[str, Any]) -> str | None:
    """Build the exact public UI record URL for one resolved identity."""

    if result.get("status") != "resolved":
        return None
    identity = CanonicalIdentity.model_validate(result["identity"])
    query = urlencode(
        {
            "assembly": identity.assembly,
            "chromosome": identity.chromosome,
            "position": str(identity.position),
            "reference": identity.reference,
            "alternate": identity.alternate,
        }
    )
    return f"https://folklore.helena.bio/variant?{query}"


def tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": "1",
        "record_url": record_url(result),
        "result": result,
        "usage_boundary": usage_boundary(),
        "adapter_error": None,
    }


def text_summary(result: dict[str, Any]) -> str:
    """Produce a bounded fallback for clients that ignore structured content."""

    status = result["status"]
    if status == "resolved":
        interpretation = result["interpretation"]
        if interpretation["status"] == "unavailable":
            error = interpretation["error"]
            return f"Folklore resolved the variant, but evidence is unavailable: {error['message']}"
        display = interpretation["display"]
        annotation = interpretation["annotation"]
        classification = interpretation["classification"]
        limitations = interpretation["limitations"]
        url = record_url(result)
        return (
            f"Folklore resolved {display['label']} in {annotation['gene_symbol']}. "
            f"Automated ACMG/AMP class: {classification['automated_class']}; "
            f"criteria: {classification['criteria'] or 'none reported'}. "
            f"{limitations['diagnostic_use']} {limitations['unavailable_context']} "
            f"Record: {url}"
        )
    if status == "ambiguous":
        return (
            f"The query is ambiguous and has {result['total_candidate_count']} "
            "supported GRCh38 candidates. Ask the user to choose; do not guess."
        )
    error = result["error"]
    return f"Folklore search outcome {status}: {error['message']}"


def mcp_input_schema() -> dict[str, Any]:
    return SearchVariantArguments.model_json_schema()


def mcp_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_version",
            "record_url",
            "result",
            "usage_boundary",
            "adapter_error",
        ],
        "properties": {
            "contract_version": {"type": "string", "const": "1"},
            "record_url": {"type": ["string", "null"], "format": "uri"},
            "result": {
                "anyOf": [
                    {
                        "type": "object",
                        "required": ["search_contract_version", "status"],
                        "properties": {
                            "search_contract_version": {
                                "type": "string",
                                "const": "1.0",
                            },
                            "status": {
                                "type": "string",
                                "enum": list(_TOP_LEVEL_KEYS),
                            },
                        },
                        "additionalProperties": True,
                    },
                    {"type": "null"},
                ]
            },
            "usage_boundary": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "result_type",
                    "review_required",
                    "patient_context_evaluated",
                    "intended_use",
                    "not_for",
                ],
                "properties": {
                    "result_type": {
                        "type": "string",
                        "const": "automated_variant_level_classification",
                    },
                    "review_required": {"type": "boolean", "const": True},
                    "patient_context_evaluated": {
                        "type": "boolean",
                        "const": False,
                    },
                    "intended_use": {
                        "type": "string",
                        "const": "professional_variant_review",
                    },
                    "not_for": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "patient_diagnosis",
                                "treatment_decision",
                                "standalone_clinical_reporting",
                            ],
                        },
                        "minItems": 3,
                        "maxItems": 3,
                        "uniqueItems": True,
                    },
                },
            },
            "adapter_error": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["code", "message", "retryable"],
                        "properties": {
                            "code": {"type": "string", "minLength": 1},
                            "message": {"type": "string", "minLength": 1},
                            "retryable": {"type": "boolean"},
                        },
                    },
                    {"type": "null"},
                ]
            },
        },
    }
