import hashlib
import importlib.util
import json
from pathlib import Path

from folklore_mcp_service.case_tools.contracts import INPUT_SCHEMAS, OUTPUT_SCHEMAS
from folklore_mcp_service.case_tools.hosted import HOSTED_OUTPUT_SCHEMAS, hosted_tools


def digest(schema):
    return hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_frozen_hosted_schema_parity_and_only_download_transport_changes():
    baseline = json.loads(
        (Path(__file__).parent / "data/hosted-schema-hashes.json").read_text()
    )
    assert len(INPUT_SCHEMAS) == len(OUTPUT_SCHEMAS) == len(HOSTED_OUTPUT_SCHEMAS) == 18
    for name in INPUT_SCHEMAS:
        assert digest(INPUT_SCHEMAS[name]) == baseline["inputs"][name]
        assert digest(OUTPUT_SCHEMAS[name]) == baseline["base_outputs"][name]
        assert digest(HOSTED_OUTPUT_SCHEMAS[name]) == baseline["hosted_outputs"][name]
        if name != "download_analysis_result_file":
            assert HOSTED_OUTPUT_SCHEMAS[name] == OUTPUT_SCHEMAS[name]
    assert [t.name for t in hosted_tools()] == list(INPUT_SCHEMAS)


def test_public_export_scan_detects_private_material_without_printing_it():
    script = Path(__file__).resolve().parents[1] / "ops/check_public_export.py"
    spec = importlib.util.spec_from_file_location("public_export_scan", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.findings(b"public API schemas") == []
    assert module.findings(b"/root/" + b"private-work") == ["private_filesystem"]
    assert module.findings(b"-----BEGIN " + b"PRIVATE KEY-----") == ["private_key"]
