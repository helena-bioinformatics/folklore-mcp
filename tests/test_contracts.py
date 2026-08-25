import pytest
from pydantic import ValidationError

from folklore_mcp_service.domain.contracts import (
    CanonicalIdentity,
    SearchVariantArguments,
    UpstreamContractError,
    record_url,
    text_summary,
    tool_result,
    usage_boundary,
    validate_upstream_result,
)

IDENTITY = {
    "assembly": "GRCh38",
    "chromosome": "chr17",
    "position": 43124028,
    "reference": "CTC",
    "alternate": "C",
    "variant_type": "DEL",
    "canonical_key": "GRCh38:chr17:43124028:CTC:C",
}


def resolved_result() -> dict:
    return {
        "search_contract_version": "1.0",
        "status": "resolved",
        "resolution": {"notation_family": "coordinate"},
        "identity": IDENTITY,
        "interpretation": {
            "contract_version": "1.0",
            "status": "success",
            "identity": IDENTITY,
            "display": {"label": "chr17:43124028 CTC>C"},
            "annotation": {"gene_symbol": "BRCA1"},
            "classification": {"automated_class": "LP", "criteria": "PVS1"},
            "limitations": {
                "diagnostic_use": "This result is not a patient diagnosis.",
                "unavailable_context": "Patient context was not evaluated.",
            },
        },
    }


def test_arguments_are_closed_bounded_and_grch38_only() -> None:
    assert SearchVariantArguments(query=" rs80357914 ").query == "rs80357914"
    with pytest.raises(ValidationError):
        SearchVariantArguments(query="x", assembly="GRCh37")
    with pytest.raises(ValidationError):
        SearchVariantArguments(query="x", extra="not allowed")
    with pytest.raises(ValidationError):
        SearchVariantArguments(query="x" * 513)


def test_resolved_envelope_requires_matching_canonical_identity() -> None:
    result = validate_upstream_result(resolved_result())
    assert CanonicalIdentity.model_validate(result["identity"]).variant_type == "DEL"
    assert record_url(result) == (
        "https://folklore.helena.bio/variant?assembly=GRCh38&chromosome=chr17"
        "&position=43124028&reference=CTC&alternate=C"
    )
    assert "BRCA1" in text_summary(result)
    assert "not a patient diagnosis" in text_summary(result)
    assert tool_result(result)["adapter_error"] is None
    assert tool_result(result)["usage_boundary"] == usage_boundary()
    assert usage_boundary() == {
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


def test_marker_like_variant_text_remains_opaque_payload_content() -> None:
    marker = "[Tool result trimmed for length]"
    result = resolved_result()
    result["interpretation"]["limitations"]["unavailable_context"] = marker

    validated = validate_upstream_result(result)

    assert validated["interpretation"]["limitations"]["unavailable_context"] == marker
    assert marker in text_summary(validated)
    assert tool_result(validated)["result"] == validated
    assert tool_result(validated)["adapter_error"] is None


def test_resolved_envelope_rejects_identity_drift_and_extra_fields() -> None:
    mismatched = resolved_result()
    mismatched["interpretation"]["identity"] = {**IDENTITY, "position": 1}
    with pytest.raises(UpstreamContractError):
        validate_upstream_result(mismatched)
    extra = resolved_result()
    extra["private_debug"] = "forbidden"
    with pytest.raises(UpstreamContractError):
        validate_upstream_result(extra)


def test_resolved_envelope_rejects_missing_text_fallback_fields() -> None:
    missing = resolved_result()
    del missing["interpretation"]["classification"]["automated_class"]
    with pytest.raises(UpstreamContractError):
        validate_upstream_result(missing)


def test_ambiguous_envelope_is_bounded_and_never_guessed() -> None:
    result = {
        "search_contract_version": "1.0",
        "status": "ambiguous",
        "resolution": {"notation_family": "rsid"},
        "error": {
            "code": "ambiguous_variant",
            "message": "The query identifies more than one supported variant.",
            "retryable": False,
        },
        "total_candidate_count": 2,
        "candidates_truncated": False,
        "candidates": [
            {"identity": IDENTITY},
            {
                "identity": {
                    **IDENTITY,
                    "reference": "C",
                    "alternate": "CTC",
                    "variant_type": "INS",
                    "canonical_key": "GRCh38:chr17:43124028:C:CTC",
                }
            },
        ],
    }
    validate_upstream_result(result)
    assert record_url(result) is None
    assert "Ask the user to choose" in text_summary(result)
    result["candidates_truncated"] = True
    with pytest.raises(UpstreamContractError):
        validate_upstream_result(result)


@pytest.mark.parametrize(
    "status",
    ["not_found", "invalid_request", "unsupported", "resolution_unavailable"],
)
def test_error_envelopes_require_typed_error(status: str) -> None:
    result = {
        "search_contract_version": "1.0",
        "status": status,
        "resolution": {"notation_family": "coordinate"}
        if status == "not_found"
        else None,
        "error": {"code": "example", "message": "Closed message.", "retryable": False},
    }
    assert validate_upstream_result(result)["status"] == status
    result["error"]["retryable"] = "false"
    with pytest.raises(UpstreamContractError):
        validate_upstream_result(result)
