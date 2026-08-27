import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "agent-discovery"
SKILL = ROOT / "skills" / "folklore-clinical-variant-interpretation" / "SKILL.md"


def load_audit_module():
    path = BENCHMARK / "audit_skill.py"
    spec = importlib.util.spec_from_file_location("audit_skill", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_evaluator_module():
    path = BENCHMARK / "evaluate_results.py"
    spec = importlib.util.spec_from_file_location("evaluate_results", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_prepare_module():
    path = BENCHMARK / "prepare_run.py"
    spec = importlib.util.spec_from_file_location("prepare_run", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_corpus_is_brand_blind_bounded_and_has_negative_controls() -> None:
    cases = list(csv.DictReader((BENCHMARK / "cases.csv").open()))
    assert len(cases) == 100
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(len(case["prompt"]) <= 220 for case in cases)
    assert all(
        forbidden not in case["prompt"]
        for case in cases
        for forbidden in ("Folklore", "Helena", "MCP")
    )
    assert any(case["expected_selection"] == "no" for case in cases)
    assert any(case["family"] == "safety" for case in cases)


def test_selection_contract_covers_routes_intents_and_safety() -> None:
    module = load_audit_module()
    result = module.audit(BENCHMARK / "cases.csv", SKILL)
    assert result["tool_routes_complete"]
    assert all(result["intent_contract"].values())
    assert all(result["safety_contract"].values())
    assert result["typed_outcomes_present"]
    assert result["implicit_trigger_present"]


def test_empirical_evaluator_reports_perfect_complete_fixture(tmp_path: Path) -> None:
    cases = list(csv.DictReader((BENCHMARK / "cases.csv").open()))
    result_path = tmp_path / "results.csv"
    with result_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "selected",
                "selected_tool",
                "public_input_only",
                "expected_behavior_preserved",
                "review_boundary_present",
                "notes",
            ],
        )
        writer.writeheader()
        for case in cases:
            selected = case["expected_selection"] == "yes"
            writer.writerow(
                {
                    "case_id": case["id"],
                    "selected": "yes" if selected else "no",
                    "selected_tool": case["expected_tool"] if selected else "none",
                    "public_input_only": "yes" if selected else "no",
                    "expected_behavior_preserved": "yes" if selected else "no",
                    "review_boundary_present": "yes" if selected else "no",
                    "notes": "",
                }
            )
    module = load_evaluator_module()
    report = module.evaluate(BENCHMARK / "cases.csv", result_path)
    assert report["completed_count"] == 100
    assert report["selection_precision"] == 1
    assert report["selection_recall"] == 1
    assert report["routing_accuracy"] == 1
    assert report["public_input_compliance"] == 1
    assert report["expected_behavior_rate"] == 1
    assert report["review_boundary_rate"] == 1


def test_prepare_run_creates_all_case_ids_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    module = load_prepare_module()
    output_dir = tmp_path / "host-model-run"
    results_path, metadata_path, count = module.prepare_run(
        BENCHMARK / "cases.csv",
        BENCHMARK / "run-metadata-template.json",
        output_dir,
    )
    rows = list(csv.DictReader(results_path.open()))
    assert count == 100
    assert [row["case_id"] for row in rows] == [
        f"AD{index:03d}" for index in range(1, 101)
    ]
    assert metadata_path.exists()

    try:
        module.prepare_run(
            BENCHMARK / "cases.csv",
            BENCHMARK / "run-metadata-template.json",
            output_dir,
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("prepare_run must refuse to overwrite a run")


def test_evaluator_rejects_blank_prepared_rows_and_incomplete_metadata(
    tmp_path: Path,
) -> None:
    prepare = load_prepare_module()
    evaluator = load_evaluator_module()
    output_dir = tmp_path / "host-model-run"
    results_path, metadata_path, _ = prepare.prepare_run(
        BENCHMARK / "cases.csv",
        BENCHMARK / "run-metadata-template.json",
        output_dir,
    )

    try:
        evaluator.evaluate(BENCHMARK / "cases.csv", results_path)
    except ValueError as exc:
        assert "incomplete result row" in str(exc)
    else:
        raise AssertionError("blank result rows must not be scored")

    try:
        evaluator.validate_metadata(metadata_path)
    except ValueError as exc:
        assert "missing run metadata" in str(exc)
    else:
        raise AssertionError("blank run metadata must not be accepted")


def test_evaluator_accepts_complete_cold_start_metadata(tmp_path: Path) -> None:
    evaluator = load_evaluator_module()
    metadata_path = tmp_path / "run-metadata.json"
    metadata = {
        "benchmark_commit": "a" * 40,
        "case_order": "AD001-AD100",
        "host": "test-host",
        "memory_disabled": True,
        "model": "test-model",
        "model_version": "1.0",
        "notes": "",
        "region_or_locale": "not_exposed",
        "schema_version": "1.0",
        "skill_commit": "b" * 40,
        "skill_package_sha256": "c" * 64,
        "tool_discovery_enabled": True,
        "utc_date": "2026-08-27T00:00:00Z",
    }
    metadata_path.write_text(json.dumps(metadata))
    assert evaluator.validate_metadata(metadata_path) == metadata
