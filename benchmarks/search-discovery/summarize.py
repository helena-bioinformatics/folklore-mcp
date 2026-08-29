import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

BOOLEAN_FIELDS = (
    "visible",
    "mentioned",
    "cited",
    "recommended",
    "selected",
    "official_page_reached",
    "independent_source",
)
REQUIRED_FIELDS = (
    "run_id",
    "query_id",
    "provider",
    "product",
    "search_mode",
    "country",
    "language",
    "started_at_utc",
) + BOOLEAN_FIELDS


def load_queries(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 60, f"expected 60 queries, found {len(rows)}"
    return {row["id"]: row for row in rows}


def parse_bool(value: str, field: str, line: int) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"line {line}: {field} must be true or false")
    return normalized == "true"


def load_ledger(
    path: Path,
    queries: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing ledger fields: {sorted(missing)}")
        result = []
        for line, row in enumerate(reader, start=2):
            query_id = row["query_id"].strip()
            if query_id not in queries:
                raise ValueError(f"line {line}: unknown query_id {query_id}")
            parsed: dict[str, object] = dict(row)
            for field in BOOLEAN_FIELDS:
                parsed[field] = parse_bool(row[field], field, line)
            rank = row.get("rank", "").strip()
            if rank:
                parsed_rank = int(rank)
                if parsed_rank < 1:
                    raise ValueError(f"line {line}: rank must be positive")
                parsed["rank"] = parsed_rank
            else:
                parsed["rank"] = None
            parsed["cohort"] = queries[query_id]["cohort"]
            result.append(parsed)
    return result


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    groups: dict[
        tuple[str, str, str, str],
        list[dict[str, object]],
    ] = defaultdict(list)
    for row in rows:
        key = (
            str(row["provider"]),
            str(row["product"]),
            str(row["language"]),
            str(row["cohort"]),
        )
        groups[key].append(row)

    summaries = []
    for (provider, product, language, cohort), members in sorted(groups.items()):
        count = len(members)
        rates = {
            field: sum(bool(row[field]) for row in members) / count
            for field in BOOLEAN_FIELDS
        }
        ranked = [int(row["rank"]) for row in members if row["rank"] is not None]
        summaries.append(
            {
                "provider": provider,
                "product": product,
                "language": language,
                "cohort": cohort,
                "query_count": count,
                "rates": rates,
                "best_rank": min(ranked) if ranked else None,
            }
        )
    return {"row_count": len(rows), "groups": summaries}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: summarize.py LEDGER.csv")
    root = Path(__file__).resolve().parent
    queries = load_queries(root / "queries.csv")
    rows = load_ledger(Path(sys.argv[1]), queries)
    print(json.dumps(summarize(rows), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
