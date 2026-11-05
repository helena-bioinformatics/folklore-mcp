"""Actual spawn/isolation checks against synthetic frozen export files."""

import asyncio
import os
from copy import deepcopy
from pathlib import Path

import pytest
from test_case_exports import frozen as _frozen_fixture
from test_case_exports import packet as _packet_fixture

from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.export_worker import run_view

frozen = _frozen_fixture
packet = _packet_fixture


@pytest.mark.asyncio
async def test_actual_child_environment_has_no_credentials(frozen, packet, monkeypatch):
    monkeypatch.setenv("FOLKLORE_API_KEY", "synthetic-parent-only-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic-other-secret")
    original = asyncio.create_subprocess_exec
    observed = []

    async def launch(*args, **kwargs):
        process = await original(*args, **kwargs)
        observed.append(Path(f"/proc/{process.pid}/environ").read_bytes())
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    await run_view(
        "get_analysis_export_summary",
        {"analysis_id": frozen[1]["analysis_id"]},
        frozen[1],
        str(frozen[2]),
        packet,
    )
    assert observed
    assert all(
        b"FOLKLORE_API_KEY=" not in env and b"AWS_SECRET_ACCESS_KEY=" not in env
        for env in observed
    )
    assert os.environ["FOLKLORE_API_KEY"] == "synthetic-parent-only-secret"


@pytest.mark.asyncio
async def test_spawned_view_returns_exact_numbers(frozen, packet):
    identity = frozen[1]
    result = await run_view(
        "get_analysis_export_variant",
        {"analysis_id": identity["analysis_id"], "variant_idx": "0"},
        identity,
        str(frozen[2]),
        packet,
    )
    assert result["record"]["global_af"] == "0.1"
    assert result["record"]["variant_idx"] == "0"


@pytest.mark.asyncio
async def test_worker_parse_deadline(frozen, packet):
    bounded = deepcopy(packet)
    bounded["limits"]["parse_index_seconds"] = 0.00001
    with pytest.raises(CaseError) as failure:
        await run_view(
            "get_analysis_export_summary",
            {"analysis_id": frozen[1]["analysis_id"]},
            frozen[1],
            str(frozen[2]),
            bounded,
        )
    assert failure.value.code == "query_budget_exceeded"


@pytest.mark.asyncio
async def test_worker_query_cpu_deadline(frozen, packet):
    source = frozen[0]
    base = source["variants"][0]
    source["variants"] = [dict(base, variant_idx=index) for index in range(1000)]
    source["collections"]["variants"]["row_count"] = 1000
    source["gene_summaries"][0]["total_variants"] = 1000
    frozen[3]()
    bounded = deepcopy(packet)
    bounded["limits"]["query_cpu_seconds"] = 0.000000001
    with pytest.raises(CaseError) as failure:
        await run_view(
            "query_analysis_export_records",
            {"analysis_id": frozen[1]["analysis_id"], "collection": "variants"},
            frozen[1],
            str(frozen[2]),
            bounded,
        )
    assert failure.value.code == "query_budget_exceeded"


@pytest.mark.asyncio
async def test_worker_enforces_memory(frozen, packet):
    bounded = deepcopy(packet)
    bounded["limits"]["worker_memory_bytes"] = 1024
    with pytest.raises(CaseError) as failure:
        await run_view(
            "get_analysis_export_summary",
            {"analysis_id": frozen[1]["analysis_id"]},
            frozen[1],
            str(frozen[2]),
            bounded,
        )
    assert failure.value.code == "query_budget_exceeded"


@pytest.mark.asyncio
async def test_worker_propagates_integrity_failure(frozen, packet):
    frozen[2].write_bytes(b"changed")
    with pytest.raises(CaseError) as failure:
        await run_view(
            "get_analysis_export_summary",
            {"analysis_id": frozen[1]["analysis_id"]},
            frozen[1],
            str(frozen[2]),
            packet,
        )
    assert failure.value.code == "artifact_integrity_failed"
