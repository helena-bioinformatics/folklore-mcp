"""Contract and exact-encoding acceptance for the case executable."""

from decimal import Decimal

import pytest
from jsonschema import Draft202012Validator

from folklore_mcp_service.case_tools.common import (
    CaseError,
    decimal_string,
    json_bytes,
    parse_json,
    private_directory,
    wire_numbers,
)
from folklore_mcp_service.case_tools.contracts import (
    INPUT_SCHEMAS,
    OUTPUT_SCHEMAS,
    TOOLS,
    validate_input,
    validate_output,
)
from folklore_mcp_service.case_tools.main import CaseService


def test_eighteen_standalone_input_and_output_schemas():
    assert len(TOOLS) == 18 and len(set(TOOLS)) == 18
    for name in TOOLS:
        for schema in (INPUT_SCHEMAS[name], OUTPUT_SCHEMAS[name]):
            assert schema["type"] == "object"
            Draft202012Validator.check_schema(schema)
    validate_output(
        "list_analysis_contexts",
        {
            "ok": True,
            "data": {
                "contract_version": "1.0.0",
                "source_operation": "list_analysis_contexts",
                "result": {"contexts": []},
            },
        },
    )


def test_exact_scientific_numeric_transport_and_api_replay_bytes():
    value = parse_json(b'{"count":9007199254740993,"score":0.10000000000000000001}')
    assert wire_numbers(value) == {
        "count": "9007199254740993",
        "score": "0.10000000000000000001",
    }
    assert json_bytes(parse_json(json_bytes(value))) == json_bytes(value)
    for score in (0.5, 1.0, 0.0):
        body = {"clinical_profile": {"custom_genes": [{"priority_score": score}]}}
        assert json_bytes(parse_json(json_bytes(body))) == json_bytes(body)
    assert decimal_string(Decimal("-0.000")) == "0"


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"n":NaN}',
        b'{"n":Infinity}',
        b"{}{}",
        b'{"n":1e100000}',
        b'{"n":1e1024}',
        b'{"a":"\xff"}',
    ],
)
def test_malformed_and_extreme_json_never_becomes_data(raw):
    with pytest.raises(CaseError):
        parse_json(raw)


def test_unknown_fields_and_credentials_are_not_tool_arguments():
    with pytest.raises(CaseError):
        validate_input("list_analysis_contexts", {"api_key": "secret"})
    with pytest.raises(CaseError):
        validate_input("get_case_analysis_status", {"analysis_id": "wrong"})
    with pytest.raises(CaseError):
        validate_input("draft_alias", {})


def test_private_directory_rejects_final_and_ancestor_symlinks(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    for path in (link, link / "state"):
        with pytest.raises(CaseError):
            private_directory(path)


def test_private_directory_creates_only_private_missing_parents(tmp_path):
    path = private_directory(tmp_path / "new" / "state")
    assert path.stat().st_mode & 0o777 == 0o700
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_error_output_removes_internal_receipt_and_raw_exception_details():
    envelope = CaseService._error(
        CaseError(
            "upstream_unavailable",
            "private raw body",
            retryable=True,
            details={
                "http_status": 503,
                "definitive_response": True,
                "body": "patient",
                "retry_after_seconds": 120,
            },
        )
    )
    assert envelope["error"]["details"] == {}
    assert "120 seconds" in envelope["error"]["message"]
    assert "private" not in str(envelope) and "patient" not in str(envelope)
    for name in TOOLS:
        validate_output(name, envelope)


def test_entire_mcp_result_has_a_byte_budget():
    with pytest.raises(CaseError, match="budget"):
        CaseService._result(
            "get_analysis_export_summary", {"ok": True, "data": {"large": "x" * 65536}}
        )


@pytest.mark.parametrize(
    "key,valid",
    [
        ("a", True),
        ("a b", True),
        ("!", True),
        ("a" * 200, True),
        (" ", False),
        (" a", False),
        ("a ", False),
        ("a" * 201, False),
    ],
)
def test_idempotency_key_exact_http_transport_domain(key, valid):
    import h11

    arguments = {
        "idempotency_key": key,
        "context_binding_id": "11111111-1111-4111-8111-111111111111",
        "profile": "singleton-germline-v1",
        "input": {
            "kind": "s3_object",
            "connection_id": "22222222-2222-4222-8222-222222222222",
            "bucket": "synthetic-bucket",
            "key": "tests/case.vcf",
            "version_id": "immutable-v1",
        },
        "max_cost_units": "0",
    }
    if valid:
        assert (
            validate_input("submit_case_analysis", arguments)["idempotency_key"] == key
        )
        connection = h11.Connection(h11.CLIENT)
        wire = connection.send(
            h11.Request(
                method="POST",
                target="/",
                headers=[("Host", "api.helena.bio"), ("Idempotency-Key", key)],
            )
        )
        server = h11.Connection(h11.SERVER)
        server.receive_data(wire)
        received = server.next_event()
        assert dict(received.headers)[b"idempotency-key"].decode("ascii") == key
    else:
        with pytest.raises(CaseError):
            validate_input("submit_case_analysis", arguments)
