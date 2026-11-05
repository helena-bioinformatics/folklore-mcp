# Bounded operational discovery relay and source-grant projection (CR025).

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from .common import CaseError

PACKET = json.loads(
    (Path(__file__).with_name("data") / "phase2-discovery-contract.json").read_text()
)
TOOLS = tuple(PACKET["input_schemas"])
CASE_TOOLS = frozenset(TOOLS) - {"list_source_connections"}


def _mismatch():
    raise CaseError("source_contract_mismatch")


def validate_records(name, value, args):
    if value["context_binding_id"] != args["context_binding_id"]:
        _mismatch()
    if name == "get_case":
        if value["case"]["case_id"] != args["case_id"]:
            _mismatch()
        records = [value["case"]]
    else:
        records = value["records"]
        if value["returned_count"] != len(records):
            _mismatch()
        if name != "list_source_connections":
            if len(records) > args.get("limit", 25) or value["has_more"] != (
                value["next_cursor"] is not None
            ):
                _mismatch()
            if value["has_more"] and not records:
                _mismatch()
        if name == "list_case_analyses" and value["case_id"] != args["case_id"]:
            _mismatch()
    if name == "list_source_connections":
        for root in records:
            prefix = root["key_prefix"]
            if (
                not prefix.endswith("/")
                or prefix.startswith("/")
                or "\\" in prefix
                or any(part in {".", ".."} for part in prefix.split("/"))
                or any(ord(char) < 32 for char in prefix)
            ):
                _mismatch()
        return
    seen = set()
    for record in records:
        identity = (
            record["analysis_id"] if name == "list_case_analyses" else record["case_id"]
        )
        if identity in seen:
            _mismatch()
        seen.add(identity)
        timed = (
            [record]
            if name == "list_case_analyses"
            else [record, record["latest_analysis"]]
        )
        for item in timed:
            for key in ("created_at", "updated_at"):
                timestamp = datetime.fromisoformat(item[key])
                if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
                    _mismatch()


async def call(api, name, args):
    args = dict(args)
    args["context_binding_id"] = str(UUID(args["context_binding_id"]))
    if name == "list_source_connections":
        admitted = await api.context()
        contexts = [
            item
            for item in admitted["contexts"]
            if item["context_binding_id"] == args["context_binding_id"]
        ]
        if len(contexts) != 1:
            raise CaseError("partner_access_denied")
        records = contexts[0]["connections"]
        result = {
            "context_binding_id": args["context_binding_id"],
            "source_kind": "admitted_s3_root_grants",
            "records": records,
            "returned_count": len(records),
        }
        api._validate(name, result)
        validate_records(name, result, args)
        return result
    return await api.discovery(name, args)
