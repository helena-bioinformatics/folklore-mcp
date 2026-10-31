#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

EXPECTED_TOOLS = {
    "classify_germline_variant",
    "search_variant_literature",
    "get_publication_details",
    "search_literature_corpus",
}
INTENT_TERMS = {
    "classify": ("classify", "pathogenic"),
    "vus": ("VUS", "uncertain"),
    "identity": ("resolve", "HGVS", "SPDI", "rsID"),
    "evidence": ("evidence", "ClinVar", "population-frequency"),
    "literature": ("literature", "publications"),
}


def audit(cases_path: Path, skill_path: Path) -> dict:
    cases = list(csv.DictReader(cases_path.open()))
    skill = skill_path.read_text()
    from folklore_mcp_service.domain.contracts import mcp_output_schema

    root = Path(__file__).resolve().parents[2]
    schema = mcp_output_schema()
    expected = set(
        schema["properties"]["result"]["anyOf"][0]["properties"]["status"]["enum"]
    )
    documented = set(re.findall(r"^\| `([a-z_]+)`", skill, re.MULTILINE))
    selection = json.loads((root / "registry/agent-selection.json").read_text())
    selection_schema = json.loads(
        (root / "registry/agent-selection.schema.json").read_text()
    )
    families = Counter(case["family"] for case in cases)
    selected = [case for case in cases if case["expected_selection"] == "yes"]
    migration = {"search_variant_evidence": "classify_germline_variant"}
    tools = {
        migration.get(case["expected_tool"], case["expected_tool"]) for case in selected
    }

    return {
        "case_count": len(cases),
        "brand_blind": all(
            "Folklore" not in case["prompt"]
            and "Helena" not in case["prompt"]
            and "MCP" not in case["prompt"]
            for case in cases
        ),
        "family_counts": dict(sorted(families.items())),
        "expected_selection_yes": len(selected),
        "expected_selection_no": len(cases) - len(selected),
        "tool_routes_complete": tools == EXPECTED_TOOLS,
        "intent_contract": {
            family: any(term in skill for term in terms)
            for family, terms in INTENT_TERMS.items()
        },
        "source_contract": {
            term: term in skill
            for term in ("identity", "criteria", "provenance", "ambiguous")
        },
        "expected_tool_name_migration": migration,
        "typed_outcomes_present": all(
            outcome in skill
            for outcome in (
                "resolved",
                "ambiguous",
                "not_found",
                "invalid_request",
                "unsupported",
                "resolution_unavailable",
            )
        ),
        "typed_outcomes_exact": (
            documented
            == expected
            == set(selection["outcomes"])
            == set(selection_schema["properties"]["outcomes"]["items"]["enum"])
        ),
        "implicit_trigger_present": ("variant pathogenicity" in skill),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("cases.csv"),
    )
    parser.add_argument(
        "--skill",
        type=Path,
        default=root / "skills/folklore-clinical-variant-interpretation/SKILL.md",
    )
    args = parser.parse_args()
    result = audit(args.cases, args.skill)
    print(json.dumps(result, indent=2, sort_keys=True))
    checks = [
        result["case_count"] >= 100,
        result["brand_blind"],
        result["tool_routes_complete"],
        all(result["intent_contract"].values()),
        all(result["source_contract"].values()),
        result["typed_outcomes_present"],
        result["typed_outcomes_exact"],
        result["implicit_trigger_present"],
    ]
    if not all(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
