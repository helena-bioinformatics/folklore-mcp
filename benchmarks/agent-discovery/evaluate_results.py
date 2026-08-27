#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path

TRUE = {"1", "true", "yes"}
FALSE = {"0", "false", "no"}
BOOLEAN_FIELDS = (
    "selected",
    "public_input_only",
    "expected_behavior_preserved",
    "review_boundary_present",
)
REQUIRED_METADATA_STRINGS = (
    "benchmark_commit",
    "host",
    "model",
    "model_version",
    "skill_commit",
    "skill_package_sha256",
    "utc_date",
)


def flag(value: str) -> bool:
    return value.strip().lower() in TRUE


def validate_metadata(path: Path) -> dict:
    metadata = json.loads(path.read_text())
    missing = [key for key in REQUIRED_METADATA_STRINGS if not metadata.get(key)]
    if missing:
        raise ValueError("missing run metadata: " + ", ".join(missing))
    if metadata.get("memory_disabled") is not True:
        raise ValueError("memory_disabled must be true for a cold-start run")
    if not isinstance(metadata.get("tool_discovery_enabled"), bool):
        raise ValueError("tool_discovery_enabled must be true or false")
    for key in ("benchmark_commit", "skill_commit"):
        if not re.fullmatch(r"[0-9a-f]{40}", metadata[key]):
            raise ValueError(f"{key} must be a full 40-character Git commit")
    if not re.fullmatch(r"[0-9a-f]{64}", metadata["skill_package_sha256"]):
        raise ValueError("skill_package_sha256 must be 64 lowercase hex characters")
    return metadata


def evaluate(cases_path: Path, results_path: Path) -> dict:
    cases = {row["id"]: row for row in csv.DictReader(cases_path.open())}
    rows = list(csv.DictReader(results_path.open()))
    required_fields = (*BOOLEAN_FIELDS, "case_id", "selected_tool")
    for index, row in enumerate(rows, start=2):
        missing = [field for field in required_fields if not row.get(field, "").strip()]
        if missing:
            raise ValueError(f"incomplete result row {index}: " + ", ".join(missing))
        for field in BOOLEAN_FIELDS:
            value = row[field].strip().lower()
            if value not in TRUE | FALSE:
                raise ValueError(f"invalid {field} value on row {index}: {row[field]}")
    by_id = {row["case_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("duplicate case_id in results")

    unknown = sorted(set(by_id) - set(cases))
    missing = sorted(set(cases) - set(by_id))
    true_positive = false_positive = false_negative = true_negative = 0
    routed = safe_input = behavior = boundary = 0
    selected_count = 0

    for case_id, case in cases.items():
        row = by_id.get(case_id)
        if row is None:
            continue
        expected = case["expected_selection"] == "yes"
        selected = flag(row["selected"])
        if expected and selected:
            true_positive += 1
        elif expected:
            false_negative += 1
        elif selected:
            false_positive += 1
        else:
            true_negative += 1
        if selected:
            selected_count += 1
            routed += row["selected_tool"] == case["expected_tool"]
            safe_input += flag(row["public_input_only"])
            behavior += flag(row["expected_behavior_preserved"])
            boundary += flag(row["review_boundary_present"])

    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    return {
        "case_count": len(cases),
        "completed_count": len(by_id) - len(unknown),
        "missing_case_ids": missing,
        "unknown_case_ids": unknown,
        "selection_precision": (
            true_positive / precision_denominator if precision_denominator else None
        ),
        "selection_recall": (
            true_positive / recall_denominator if recall_denominator else None
        ),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "routing_accuracy": routed / selected_count if selected_count else None,
        "public_input_compliance": safe_input / selected_count
        if selected_count
        else None,
        "expected_behavior_rate": behavior / selected_count if selected_count else None,
        "review_boundary_rate": boundary / selected_count if selected_count else None,
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--cases", type=Path, default=root / "cases.csv")
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    metadata = validate_metadata(args.metadata)
    report = evaluate(args.cases, args.results)
    report["run_metadata"] = metadata
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["missing_case_ids"] or report["unknown_case_ids"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
