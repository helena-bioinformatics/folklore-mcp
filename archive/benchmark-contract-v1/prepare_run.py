#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

RESULT_FIELDS = [
    "case_id",
    "selected",
    "selected_tool",
    "public_input_only",
    "expected_behavior_preserved",
    "review_boundary_present",
    "notes",
]


def prepare_run(
    cases_path: Path,
    metadata_template_path: Path,
    output_dir: Path,
) -> tuple[Path, Path, int]:
    cases = list(csv.DictReader(cases_path.open()))
    case_ids = [case["id"] for case in cases]
    if not case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("cases must contain unique non-empty ids")

    results_path = output_dir / "results.csv"
    metadata_path = output_dir / "run-metadata.json"
    existing = [path for path in (results_path, metadata_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite: " + ", ".join(str(path) for path in existing)
        )

    metadata = json.loads(metadata_template_path.read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    with results_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for case_id in case_ids:
            writer.writerow({"case_id": case_id})
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return results_path, metadata_path, len(case_ids)


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--cases", type=Path, default=root / "cases.csv")
    parser.add_argument(
        "--metadata-template",
        type=Path,
        default=root / "run-metadata-template.json",
    )
    args = parser.parse_args()
    results_path, metadata_path, count = prepare_run(
        args.cases,
        args.metadata_template,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "case_count": count,
                "metadata": str(metadata_path),
                "results": str(results_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
