"""Verify the separately versioned discovery cohort can be replayed without drift."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_genomic_discovery_cohort_pairs_locales_and_covers_scope_failures():
    directory = ROOT / "benchmarks/genomic-discovery/v1"
    manifest = json.loads((directory / "manifest.json").read_text())
    with (directory / manifest["query_file"]).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == manifest["query_count"] == 24
    assert len({row["id"] for row in rows}) == len(rows)
    assert {row["locale"] for row in rows} == set(manifest["locales"])
    pairs = {}
    for row in rows:
        assert row["query"].strip()
        assert not any(
            brand in row["query"].lower() for brand in ("folklore", "helena")
        )
        pairs.setdefault(row["category"], []).append(row)
    for pair in pairs.values():
        assert {row["locale"] for row in pair} == {"en", "bg"}
        assert len({row["expected_route"] for row in pair}) == 1
    assert {
        row["category"] for row in rows if row["expected_route"] == "out-of-scope"
    } == {"vcf", "sequence", "diagnosis"}
    assert {"get_gene_disease_associations", "search_disease_genes"} <= {
        row["expected_route"] for row in rows
    }
    assert manifest["status"] == "preregistered-unmeasured"
