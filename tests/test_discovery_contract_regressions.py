import importlib.util
import json
import re
from pathlib import Path

import jsonschema
import pytest

from folklore_mcp_service.domain.contracts import (
    mcp_output_schema,
    tool_result,
    validate_upstream_result,
)

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/folklore-clinical-variant-interpretation"


def load_module(relative):
    spec = importlib.util.spec_from_file_location("benchmark", ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_documented_status_sets_equal_output_schema():
    schema = mcp_output_schema()
    expected = set(
        schema["properties"]["result"]["anyOf"][0]["properties"]["status"]["enum"]
    )
    assert (
        set(re.findall(r"^- `([a-z_]+)`:", (SKILL / "SKILL.md").read_text(), re.M))
        == expected
    )
    assert (
        set(
            re.findall(
                r"^\| `([a-z_]+)`", (ROOT / "docs/TYPED_OUTCOMES.md").read_text(), re.M
            )
        )
        == expected
    )
    assert (
        set(
            json.loads((ROOT / "registry/agent-selection.json").read_text())["outcomes"]
        )
        == expected
    )
    assert (
        set(
            json.loads((ROOT / "registry/agent-selection.schema.json").read_text())[
                "properties"
            ]["outcomes"]["items"]["enum"]
        )
        == expected
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("invalid_request", "invalid"),
        ("resolution_unavailable", "temporarily_unavailable"),
    ],
)
def test_audit_rejects_stale_status_even_when_other_words_match(tmp_path, old, new):
    audit = load_module("benchmarks/agent-discovery/audit_skill.py")
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        (SKILL / "SKILL.md").read_text().replace(f"- `{old}`:", f"- `{new}`:")
    )
    assert not audit.audit(ROOT / "benchmarks/agent-discovery/cases.csv", skill)[
        "typed_outcomes_exact"
    ]


def test_packaged_failure_examples_validate_against_scientific_contract():
    examples = json.loads((SKILL / "references/response-examples.json").read_text())
    assert {entry["name"] for entry in examples["scientific_failures"]} == {
        "not_found",
        "invalid_request",
        "unsupported",
        "resolution_unavailable",
    }
    for entry in examples["scientific_failures"]:
        result = validate_upstream_result(entry["scientific_result"])
        envelope = tool_result(result)
        jsonschema.validate(envelope, mcp_output_schema())
        assert envelope["record_url"] is None
        assert envelope["adapter_error"] is None


def test_capture_never_promotes_ambiguous_candidate_to_identity():
    capture = load_module("benchmarks/variant-interpretation/capture_folklore.py")
    candidates = [
        {"identity": {"canonical_key": "one"}},
        {"identity": {"canonical_key": "two"}},
    ]
    response = {
        "result": {
            "structuredContent": {
                "result": {"status": "ambiguous", "candidates": candidates}
            }
        }
    }
    record = capture._record({"case_id": "ambiguity"}, response, 1)
    assert record["identity"] is None
    assert record["candidates"] == candidates
    assert record["raw_response"] == response


def test_capture_retains_adapter_failure_separately_from_scientific_miss():
    capture = load_module("benchmarks/variant-interpretation/capture_folklore.py")
    error = {"code": "upstream_timeout", "message": "Timeout", "retryable": True}
    response = {
        "result": {
            "isError": True,
            "structuredContent": {"result": None, "adapter_error": error},
        }
    }
    record = capture._record({"case_id": "timeout"}, response, 1)
    assert record["status"] is None
    assert record["adapter_error"] == error
    assert record["tool_error"] is True
