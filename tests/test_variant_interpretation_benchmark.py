import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "variant-interpretation"


def _module():
    spec = importlib.util.spec_from_file_location(
        "capture_folklore", BENCHMARK / "capture_folklore.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cases_are_public_bounded_and_cover_input_states() -> None:
    with (BENCHMARK / "cases.csv").open(newline="") as source:
        cases = list(csv.DictReader(source))
    assert len(cases) == 20
    assert {case["assembly"] for case in cases} == {"GRCh38"}
    assert len({case["case_id"] for case in cases}) == len(cases)
    classes = {case["input_class"] for case in cases}
    assert {
        "rsid",
        "multiallelic-rsid",
        "transcript-hgvs",
        "coordinate",
        "spdi",
        "invalid",
        "not-found",
        "unsupported-assembly",
        "unsupported-variant-type",
    } <= classes
    forbidden = ("patient", "phenotype", "family", "segregation", "proband")
    assert not any(
        term in case["input"].lower() for case in cases for term in forbidden
    )


def test_record_projection_is_bounded_and_preserves_safety() -> None:
    module = _module()
    response = {
        "result": {
            "isError": False,
            "structuredContent": {
                "contract_version": "1",
                "result": {
                    "search_contract_version": "1.0",
                    "status": "resolved",
                    "resolution": {"normalized_query": "rs1"},
                    "identity": {"assembly": "GRCh38", "canonical_key": "key"},
                    "interpretation": {
                        "annotation": {"gene_symbol": "GENE", "transcript_id": "ENST1"},
                        "classification": {"automated_class": "VUS", "criteria": "PM2"},
                        "evidence": {"clinvar": {"availability": "available"}},
                        "provenance": {
                            "classifier_version": "1",
                            "reference_versions": [],
                        },
                    },
                },
                "usage_boundary": {
                    "review_required": True,
                    "patient_context_evaluated": False,
                    "not_for": ["patient_diagnosis", "treatment_decision"],
                },
            },
        }
    }
    record = module._record(
        {
            "case_id": "case",
            "input": "rs1",
            "assembly": "GRCh38",
            "input_class": "rsid",
        },
        response,
        25,
    )
    assert record["status"] == "resolved"
    assert record["identity"]["canonical_key"] == "key"
    assert record["review_required"] is True
    assert record["patient_context_evaluated"] is False
    assert "patient_diagnosis" in record["not_for"]
    assert "content" not in record
