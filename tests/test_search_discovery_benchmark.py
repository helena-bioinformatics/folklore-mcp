import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "search-discovery"


def load_module():
    path = BENCHMARK / "summarize.py"
    spec = importlib.util.spec_from_file_location("search_discovery_summary", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_query_corpus_is_versioned_brand_blind_and_balanced() -> None:
    with (BENCHMARK / "queries.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 60
    assert len({row["id"] for row in rows}) == 60
    assert {row["locale"] for row in rows} == {"en-US"}

    cohorts = {}
    for row in rows:
        cohorts[row["cohort"]] = cohorts.get(row["cohort"], 0) + 1
        forbidden = row["brand_terms_forbidden"].split("|")
        assert all(term.casefold() not in row["query"].casefold() for term in forbidden)

    assert cohorts == {
        "exact_category": 10,
        "capability_mcp": 10,
        "task_first": 10,
        "concrete_variant": 10,
        "alternative_selection": 10,
        "safety_control": 10,
    }


def test_ledger_schema_and_template_agree() -> None:
    schema = json.loads((BENCHMARK / "ledger.schema.json").read_text(encoding="utf-8"))
    with (BENCHMARK / "ledger-template.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        fields = csv.DictReader(handle).fieldnames

    assert fields == schema["required"]
    assert schema["additionalProperties"] is False


def test_summary_keeps_metrics_separate(tmp_path: Path) -> None:
    module = load_module()
    queries = module.load_queries(BENCHMARK / "queries.csv")
    ledger = tmp_path / "ledger.csv"
    fields = (
        (BENCHMARK / "ledger-template.csv")
        .read_text(encoding="utf-8")
        .strip()
        .split(",")
    )
    row = dict.fromkeys(fields, "")
    row.update(
        {
            "run_id": "baseline-1",
            "query_id": "SD101",
            "provider": "Example Search",
            "product": "Web",
            "search_mode": "search",
            "country": "US",
            "language": "en-US",
            "started_at_utc": "2026-08-29T00:00:00Z",
            "rank": "2",
            "visible": "true",
            "mentioned": "true",
            "cited": "false",
            "recommended": "false",
            "selected": "false",
            "official_page_reached": "true",
            "independent_source": "false",
        }
    )
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)

    result = module.summarize(module.load_ledger(ledger, queries))
    assert result["row_count"] == 1
    rates = result["groups"][0]["rates"]
    assert rates["visible"] == 1.0
    assert rates["cited"] == 0.0
    assert rates["official_page_reached"] == 1.0
