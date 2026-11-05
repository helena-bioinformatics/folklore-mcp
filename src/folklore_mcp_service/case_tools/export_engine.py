"""Exact frozen-export validation and bounded local views for CR024.

This module contains no scientific calculations, credentials or network access.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import time
from decimal import Decimal, InvalidOperation
from functools import cmp_to_key
from typing import Any
from uuid import UUID

from .common import CaseError, json_bytes, parse_json, wire_numbers

_DECIMAL = re.compile(r"^(?:0|-?[1-9][0-9]*|-?(?:0|[1-9][0-9]*)\.[0-9]*[1-9])$")
_INDEX = re.compile(r"^(?:0|[1-9][0-9]*)$")
_STATES = {"not_requested", "failed", "succeeded", "skipped"}
_MODULES = ("phenotype_matches", "screening_results", "literature_results")


def start_query_budget() -> None:
    """The isolated worker replaces this hook after validation completes."""


def _error(code: str = "unsupported_export_shape", **details: Any) -> None:
    raise CaseError(code, details=details)


def _integer(value: Any, nonnegative: bool = True) -> bool:
    return type(value) is int and (not nonnegative or value >= 0)


def _object(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - (optional or set())
    ):
        _error()


def _uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value.lower()
    except (ValueError, AttributeError):
        return False


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _budget(
    packet: dict, name: str, amount: int, code: str = "export_budget_exceeded"
) -> None:
    limit = packet["limits"][name]
    if amount > limit:
        _error(code, limit_name=name, limit=limit)


def _read(path: str, identity: dict, packet: dict) -> dict:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                _error("artifact_integrity_failed")
            _budget(packet, "artifact_bytes", info.st_size)
            expected_size = identity.get(
                "size_bytes", identity.get("artifact_size_bytes")
            )
            if expected_size is not None and info.st_size != expected_size:
                _error("artifact_integrity_failed")
            raw = handle.read(packet["limits"]["artifact_bytes"] + 1)
    except CaseError:
        raise
    except OSError:
        raise CaseError("artifact_integrity_failed") from None
    _budget(packet, "artifact_bytes", len(raw))
    if (
        not _hash(identity.get("artifact_sha256"))
        or hashlib.sha256(raw).hexdigest() != identity["artifact_sha256"]
    ):
        _error("artifact_integrity_failed")
    source = parse_json(raw)
    stack = [(source, 1)]
    while stack:
        item, depth = stack.pop()
        _budget(packet, "json_depth", depth)
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
    return source


def _scalar(value: Any, meta: dict) -> None:
    if value is None:
        if not meta["nullable"]:
            _error()
        return
    kind = meta["source_type"]
    valid = {
        "integer": type(value) is int,
        "number": type(value) is int or isinstance(value, Decimal),
        "boolean": type(value) is bool,
        "string": isinstance(value, str),
        "string_array": isinstance(value, list)
        and all(isinstance(x, str) for x in value),
        "object_array": isinstance(value, list),
    }.get(kind, False)
    if not valid:
        _error()
    if kind == "number" and isinstance(value, Decimal) and not value.is_finite():
        _error()
    if "minimum_source_value" in meta and value < meta["minimum_source_value"]:
        _error("export_integrity_error")


def _rows(source: dict, packet: dict) -> None:
    registry = packet["field_registry"]
    total = 0
    variant_ids: set[int] = set()
    for collection in ["variants", *_MODULES]:
        rows = source[collection]
        if not isinstance(rows, list):
            _error()
        total += len(rows)
        metadata = source["collections"][collection]
        required = {"row_count", "unavailable_fields"}
        optional = set()
        if collection != "variants":
            required.add("state")
            optional = (
                {"reason"}
                if collection == "phenotype_matches"
                else {"analyzed_count"}
                if collection == "screening_results"
                else set()
            )
        _object(metadata, required, optional)
        if not _integer(metadata["row_count"]) or metadata["row_count"] != len(rows):
            _error("export_integrity_error")
        unavailable = metadata["unavailable_fields"]
        if (
            not isinstance(unavailable, list)
            or any(
                not isinstance(f, str) or f not in registry[collection]
                for f in unavailable
            )
            or len(unavailable) != len(set(unavailable))
        ):
            _error()
        if any(registry[collection][f]["source_required"] for f in unavailable):
            _error("export_integrity_error")
        if collection != "variants":
            if metadata["state"] not in _STATES:
                _error()
            if metadata["state"] != "succeeded" and rows:
                _error("export_integrity_error")
        if "reason" in metadata and (
            metadata["reason"] != "no_variants_with_hpo"
            or metadata["state"] != "succeeded"
            or rows
        ):
            _error()
        if (
            "analyzed_count" in metadata
            and metadata["analyzed_count"] is not None
            and not _integer(metadata["analyzed_count"])
        ):
            _error()
        seen = set()
        key = packet["query_rules"]["primary_keys"][collection]
        for row in rows:
            _object(row, set(registry[collection]))
            _budget(packet, "single_record_bytes", len(json_bytes(wire_numbers(row))))
            for field, meta in registry[collection].items():
                _scalar(row[field], meta)
                if field in unavailable and row[field] is not None:
                    _error("export_integrity_error")
            ident = row[key]
            if ident is None or ident in seen:
                _error("export_integrity_error")
            seen.add(ident)
            if collection == "variants":
                variant_ids.add(ident)
            elif (
                collection in ("phenotype_matches", "screening_results")
                and ident not in variant_ids
            ):
                _error("export_integrity_error")
            if collection == "phenotype_matches":
                matches = row["individual_matches"]
                if not isinstance(matches, list):
                    _error()
                for match in matches:
                    keys = set(
                        packet["nested_fields"]["phenotype_matches.individual_matches"][
                            "keys"
                        ]
                    )
                    _object(match, keys)
                    for field in keys - {"similarity_score"}:
                        if match[field] is not None and not isinstance(
                            match[field], str
                        ):
                            _error()
                    score = match["similarity_score"]
                    if (
                        score is not None
                        and type(score) is not int
                        and not isinstance(score, Decimal)
                    ):
                        _error()
    genes = source["gene_summaries"]
    if not isinstance(genes, list) or len(genes) < 2:
        _error("export_integrity_error")
    total += len(genes)
    _budget(packet, "total_records", total)
    for record in genes:
        _budget(packet, "single_record_bytes", len(json_bytes(wire_numbers(record))))
    meta, complete = genes[0], genes[-1]
    _object(
        meta,
        {"type", "total_genes", "total_variants", "impact_by_acmg", "session_id"},
        set(packet["gene_summary_stream"]["metadata_allowed_keys"]),
    )
    _object(complete, {"type", "total_streamed", "session_id"})
    if (
        meta["type"] != "metadata"
        or complete["type"] != "complete"
        or any(r["session_id"] != source["case_id"] for r in [meta, complete])
    ):
        _error("export_integrity_error")
    if not all(
        _integer(v)
        for v in [
            meta["total_genes"],
            meta["total_variants"],
            complete["total_streamed"],
        ]
    ):
        _error()
    if (
        meta["total_genes"] != len(genes) - 2
        or complete["total_streamed"] != len(genes) - 2
    ):
        _error("export_integrity_error")
    if not isinstance(meta["impact_by_acmg"], dict):
        _error()
    for counts in meta["impact_by_acmg"].values():
        _object(
            counts, set(), set(packet["gene_summary_stream"]["impact_allowed_keys"])
        )
        if any(not _integer(v) for v in counts.values()):
            _error()
    for key in ["classifier_version", "classifier_version_label"]:
        if key in meta and meta[key] is not None and not isinstance(meta[key], str):
            _error()
    if "timestamp" in meta and not _integer(meta["timestamp"], False):
        _error()
    panel = meta.get("mtdna_panel")
    if panel is not None:
        _object(
            panel,
            {"mtdna_variant_count"},
            set(packet["gene_summary_stream"]["mtdna_allowed_keys"]),
        )
        if not _integer(panel["mtdna_variant_count"]):
            _error()
        for k, v in panel.items():
            if v is not None and isinstance(v, (dict, list, bool)):
                _error()
            if (
                k in ("mmdwg_predicted_haplogroup", "haplogroup_failure_reason")
                and v is not None
                and not isinstance(v, str)
            ):
                _error()
            if (
                k == "mmdwg_haplogroup_confidence"
                and v is not None
                and type(v) is not int
                and not isinstance(v, Decimal)
            ):
                _error()
    seen_genes = set()
    for row in genes[1:-1]:
        _object(row, {"type", "data"})
        if row["type"] != "gene":
            _error("export_integrity_error")
        fields = registry["gene_summaries"]
        _object(row["data"], {"gene_symbol"}, {f[5:] for f in fields})
        for k, v in row["data"].items():
            _scalar(v, fields["data." + k])
        gene = row["data"]["gene_symbol"]
        if gene in seen_genes:
            _error("export_integrity_error")
        seen_genes.add(gene)


def _validate(source: Any, identity: dict, packet: dict) -> None:
    if not isinstance(source, dict) or source.get("schema_version") != "2":
        _error("unsupported_export_schema")
    _object(source, set(packet["source_root"]["required_keys"]))
    if source["profile"] not in packet["supported_source"]["profiles"]:
        _error("unsupported_export_shape")
    for name in ["analysis_id", "case_id", "generation_id"]:
        if not _uuid(source[name]) or source[name] != identity.get(name):
            _error("export_integrity_error")
    summary = source["summary"]
    _object(summary, set(packet["source_root"]["summary"]))
    for field in ["pathogenic_count", "likely_pathogenic_count"]:
        if not _integer(summary[field]):
            _error()
    for field in ["classifier_version", "classifier_version_label"]:
        if summary[field] is not None and not isinstance(summary[field], str):
            _error()
    provenance = source["provenance"]
    _object(provenance, set(packet["source_root"]["provenance"]))
    if (
        not _hash(provenance["request_sha256"])
        or not _hash(provenance["clinical_profile_sha256"])
        or not isinstance(provenance["accepted_clinical_profile"], dict)
    ):
        _error()
    if (
        provenance["classification"]
        != "recorded_generation_without_mutable_annotation_overlays"
    ):
        _error()
    coverage = source["coverage"]
    _object(coverage, set(packet["source_root"]["coverage"]))
    for key, expected in packet["source_root"]["coverage"].items():
        if key == "filtering_preset":
            if not isinstance(coverage[key], str):
                _error()
        elif coverage[key] != expected or type(coverage[key]) is not type(expected):
            _error()
    _object(source["collections"], {"variants", *_MODULES})
    _rows(source, packet)


def _field(row: dict, field: str, collection: str) -> Any:
    return (
        row["data"].get(field[5:]) if collection == "gene_summaries" else row.get(field)
    )


def _has_field(row: dict, field: str, collection: str) -> bool:
    return field[5:] in row["data"] if collection == "gene_summaries" else field in row


def _threshold(value: Any, meta: dict) -> Any:
    kind = meta["source_type"]
    if kind in ("integer", "number"):
        if (
            not isinstance(value, str)
            or len(value) > 1024
            or not _DECIMAL.fullmatch(value)
        ):
            _error("invalid_input")
        if kind == "integer" and "." in value:
            _error("invalid_input")
        try:
            return Decimal(value)
        except InvalidOperation:
            _error("invalid_input")
    if kind == "boolean":
        if type(value) is not bool:
            _error("invalid_input")
    elif not isinstance(value, str) or len(value) > 2000:
        _error("invalid_input")
    return value


def _matches(value: Any, op: str, wanted: Any) -> bool:
    if op == "is_null":
        return value is None
    if op == "is_not_null":
        return value is not None
    if value is None:
        return False
    if op == "is_empty":
        return not value
    if op in ("contains", "contains_element"):
        return wanted in value
    if op == "starts_with":
        return value.startswith(wanted)
    if op == "in":
        return value in wanted
    return {
        "eq": lambda: value == wanted,
        "ne": lambda: value != wanted,
        "lt": lambda: value < wanted,
        "lte": lambda: value <= wanted,
        "gt": lambda: value > wanted,
        "gte": lambda: value >= wanted,
    }[op]()


def _required_projection_fields(packet: dict, collection: str) -> list[str]:
    # Required scientific headers are part of the frozen output contract, even
    # when a caller requests a smaller projection. Preserve source values only.
    definition = packet["output_schemas"]["query_analysis_export_records"]["$defs"][
        "record_" + collection
    ]
    registry = packet["field_registry"][collection]

    def fields(schema, prefix=""):
        result = []
        for name in schema.get("required", []):
            path = prefix + name
            if path in registry:
                result.append(path)
            else:
                result.extend(
                    fields(schema.get("properties", {}).get(name, {}), path + ".")
                )
        return result

    return fields(definition)


def _query(source: dict, args: dict, packet: dict, cursor: dict | None) -> dict:
    collection = args["collection"]
    registry = packet["field_registry"][collection]
    primary = packet["query_rules"]["primary_keys"][collection]
    all_rows = (
        source["gene_summaries"][1:-1]
        if collection == "gene_summaries"
        else source[collection]
    )
    context = (
        {
            "metadata": source["gene_summaries"][0],
            "completion": source["gene_summaries"][-1],
        }
        if collection == "gene_summaries"
        else source["collections"][collection]
    )
    state = context.get("state", "succeeded")
    unavailable = set(context.get("unavailable_fields", []))
    filters = args.get("filters", [])
    sort = args.get("sort", [])
    projection = args.get(
        "projection", packet["compact_default_projection"][collection]
    )
    limit = args.get("limit", 25)
    if (
        not isinstance(filters, list)
        or len(filters) > 16
        or not isinstance(sort, list)
        or len(sort) > 3
        or not _integer(limit)
        or not 1 <= limit <= 100
    ):
        _error("invalid_input")
    if (
        not isinstance(projection, list)
        or not projection
        or len(projection) > 32
        or any(not isinstance(f, str) or f not in registry for f in projection)
        or len(projection) != len(set(projection))
    ):
        _error("invalid_input")
    compiled = []
    for predicate in filters:
        if not isinstance(predicate, dict):
            _error("invalid_input")
        field, op = predicate.get("field"), predicate.get("operator")
        if field not in registry or op not in registry[field]["filter_operators"]:
            _error("invalid_input")
        required = (
            {"field", "operator"}
            if op in ("is_null", "is_not_null", "is_empty")
            else {"field", "operator", "value"}
        )
        _object(predicate, required)
        if field in unavailable or any(
            not _has_field(r, field, collection) for r in all_rows
        ):
            _error("field_unavailable", field=field, collection=collection)
        value = predicate.get("value")
        if op == "in":
            if not isinstance(value, list) or not 1 <= len(value) <= 32:
                _error("invalid_input")
            value = [_threshold(v, registry[field]) for v in value]
            if len(value) != len(set(value)):
                _error("invalid_input")
        elif op not in ("is_null", "is_not_null", "is_empty"):
            value = _threshold(value, registry[field])
        compiled.append((field, op, value))
    seen_sort = set()
    for order in sort:
        _object(order, {"field", "direction"})
        field = order["field"]
        if (
            field not in registry
            or not registry[field]["sortable"]
            or field in seen_sort
            or order["direction"] not in ("asc", "desc")
        ):
            _error("invalid_input")
        if field in unavailable or any(
            not _has_field(r, field, collection) for r in all_rows
        ):
            _error("field_unavailable", field=field, collection=collection)
        seen_sort.add(field)
    if "gene_symbol" in args:
        gene = args["gene_symbol"]
        if collection == "screening_results":
            matched_ids = {
                r["variant_idx"] for r in source["variants"] if r["gene_symbol"] == gene
            }
            all_rows = [r for r in all_rows if r["variant_idx"] in matched_ids]
        else:
            gene_field = (
                "data.gene_symbol" if collection == "gene_summaries" else "gene_symbol"
            )
            if gene_field in unavailable:
                _error("field_unavailable", field=gene_field, collection=collection)
            all_rows = [
                r for r in all_rows if _field(r, gene_field, collection) == gene
            ]
    rows = [
        r
        for r in all_rows
        if all(_matches(_field(r, f, collection), op, v) for f, op, v in compiled)
    ]
    ordering = list(sort)
    if primary not in seen_sort:
        ordering.append({"field": primary, "direction": "asc"})

    def compare(a: dict, b: dict) -> int:
        for order in ordering:
            x, y = (
                _field(a, order["field"], collection),
                _field(b, order["field"], collection),
            )
            if x is None or y is None:
                result = (x is None) - (y is None)
            else:
                result = (x > y) - (x < y)
                if order["direction"] == "desc":
                    result = -result
            if result:
                return result
        return 0

    rows.sort(key=cmp_to_key(compare))
    fingerprint = hashlib.sha256(
        json_bytes(
            {
                "collection": collection,
                "filters": filters,
                "projection": projection,
                "sort": sort,
                "gene_symbol": args.get("gene_symbol"),
            }
        )
    ).hexdigest()
    offset = 0
    if cursor is not None:
        if (
            not isinstance(cursor, dict)
            or cursor.get("query") != fingerprint
            or not _integer(cursor.get("offset"))
        ):
            _error("invalid_cursor")
        offset = cursor["offset"]
        if offset > len(rows):
            _error("invalid_cursor")
        previous = (
            wire_numbers(
                [
                    _field(rows[offset - 1], item["field"], collection)
                    for item in ordering
                ]
            )
            if offset
            else None
        )
        if cursor.get("last_sort") != previous:
            _error("invalid_cursor")
    page = rows[offset : offset + limit]
    selected_fields = list(
        dict.fromkeys(
            [primary, *_required_projection_fields(packet, collection), *projection]
        )
    )
    result_rows = []
    for row in page:
        if collection == "gene_summaries":
            value = {
                "type": "gene",
                "data": {
                    f[5:]: row["data"][f[5:]]
                    for f in selected_fields
                    if _has_field(row, f, collection)
                },
            }
            unavailable.update(
                f for f in selected_fields if not _has_field(row, f, collection)
            )
        else:
            value = {f: row[f] for f in selected_fields}
        result_rows.append(wire_numbers(value))
    has_more = offset + len(page) < len(rows)
    internal = None
    if has_more:
        internal = {
            "query": fingerprint,
            "offset": offset + len(page),
            "last_sort": wire_numbers(
                [_field(page[-1], item["field"], collection) for item in ordering]
            ),
        }
    result = {
        "collection": collection,
        "availability": "available" if state == "succeeded" else state,
        "collection_context": wire_numbers(context),
        "unavailable_fields": sorted(unavailable),
        "records": result_rows,
        "returned_count": len(result_rows),
        "matched_count": len(rows) if state == "succeeded" else None,
        "has_more": has_more,
        "next_cursor": None,
    }
    if "gene_symbol" in args:
        result["gene_symbol"] = args["gene_symbol"]
    if internal:
        result["__cursor_state"] = internal
    return result


def _execute_view(
    tool_name: str,
    args: dict,
    identity: dict,
    artifact_path: str,
    packet: dict,
    cursor_state: dict | None = None,
) -> dict:
    """Validate the entire frozen source before returning any selected view."""
    if tool_name not in packet["input_schemas"] or not isinstance(args, dict):
        _error("invalid_input")
    if args.get("analysis_id") != identity.get("analysis_id"):
        _error("invalid_input")
    if args.get(
        "expected_generation_id", identity.get("generation_id")
    ) != identity.get("generation_id"):
        _error("generation_conflict")
    source = _read(artifact_path, identity, packet)
    _validate(source, identity, packet)
    start_query_budget()
    started = time.process_time()
    common_names = packet["tool_outputs"]["common"]
    data = {k: identity[k] for k in common_names if k in identity}
    data.update(
        contract_version="1.0.0",
        source_view=tool_name,
        source_schema_version="2",
        source_profile=source["profile"],
        numeric_encoding="canonical_decimal_string",
    )
    if "source_expires_at" not in data and "expires_at" in identity:
        data["source_expires_at"] = identity["expires_at"]
    genes = {
        "metadata": source["gene_summaries"][0],
        "completion": source["gene_summaries"][-1],
    }
    if tool_name == "get_analysis_export_summary":
        data.update(
            summary=wire_numbers(source["summary"]),
            coverage=source["coverage"],
            collections=wire_numbers(source["collections"]),
            gene_summary_context=wire_numbers(genes),
        )
    elif tool_name == "get_analysis_export_provenance":
        data.update(
            provenance=wire_numbers(source["provenance"]),
            coverage=source["coverage"],
            classifier_identity={
                "summary": wire_numbers(source["summary"]),
                "gene_metadata_classifier_version": genes["metadata"].get(
                    "classifier_version"
                ),
                "gene_metadata_classifier_version_label": genes["metadata"].get(
                    "classifier_version_label"
                ),
            },
        )
    elif tool_name == "get_analysis_export_variant":
        index = args.get("variant_idx")
        if not isinstance(index, str) or len(index) > 64 or not _INDEX.fullmatch(index):
            _error("invalid_input")
        row = next(
            (r for r in source["variants"] if r["variant_idx"] == int(index)), None
        )
        if row is None:
            _error("record_not_found")
        data.update(
            record=wire_numbers(row),
            unavailable_fields=source["collections"]["variants"]["unavailable_fields"],
        )
    elif tool_name == "get_analysis_export_schema":
        registry = {}
        for collection, fields in packet["field_registry"].items():
            unavailable = (
                source["collections"].get(collection, {}).get("unavailable_fields", [])
            )
            rows = (
                source["gene_summaries"][1:-1]
                if collection == "gene_summaries"
                else source[collection]
            )
            registry[collection] = {
                field: {
                    k: meta[k]
                    for k in [
                        "source_type",
                        "wire_type",
                        "nullable",
                        "filter_operators",
                        "sortable",
                        "projectable",
                    ]
                }
                | {
                    "source_available": field not in unavailable
                    and all(_has_field(r, field, collection) for r in rows)
                }
                for field, meta in fields.items()
            }
        data["schema"] = {
            "field_registry": registry,
            "primary_keys": packet["query_rules"]["primary_keys"],
            "query_limits": {
                k: packet["limits"][k]
                for k in [
                    "predicates",
                    "in_values",
                    "projection_fields",
                    "sort_fields",
                    "page_default",
                    "page_maximum",
                ]
            },
            "nested_fields": {
                "phenotype_matches.individual_matches": "Closed HPO source objects; similarity_score is a canonical decimal string. Projection only.",
                "literature_string_arrays": "Exact source strings; no canonical identity or allele joins.",
            },
        }
    else:
        collection = args.get("collection")
        if (
            collection not in packet["field_registry"]
            or tool_name == "get_analysis_export_gene_records"
            and collection == "literature_results"
        ):
            _error("invalid_input")
        if tool_name == "get_analysis_export_gene_records" and (
            not isinstance(args.get("gene_symbol"), str)
            or not 1 <= len(args["gene_symbol"]) <= 200
        ):
            _error("invalid_input")
        data.update(_query(source, args, packet, cursor_state))
    if time.process_time() - started > packet["limits"]["query_cpu_seconds"]:
        _error(
            "query_budget_exceeded",
            limit_name="query_cpu_seconds",
            limit=packet["limits"]["query_cpu_seconds"],
        )
    public = {k: v for k, v in data.items() if k != "__cursor_state"}
    _budget(
        packet,
        "response_bytes",
        len(json_bytes({"ok": True, "data": public})),
        "response_budget_exceeded",
    )
    return data


def execute_view(
    tool_name: str,
    args: dict,
    identity: dict,
    artifact_path: str,
    packet: dict,
    cursor_state: dict | None = None,
) -> dict:
    """Reject malformed source structures with a typed, nonclinical error."""
    try:
        return _execute_view(
            tool_name, args, identity, artifact_path, packet, cursor_state
        )
    except CaseError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        raise CaseError("unsupported_export_shape") from None
