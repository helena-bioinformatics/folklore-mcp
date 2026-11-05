"""Synthetic producer-shaped export acceptance for CR024."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.export_engine import execute_view


@pytest.fixture
def packet():
    return json.loads(
        (
            Path(__file__).parents[1]
            / "src/folklore_mcp_service/case_tools/data/phase1-export-contract.json"
        ).read_text()
    )


@pytest.fixture
def frozen(tmp_path, packet):
    ids = dict(
        zip(
            ["analysis_id", "case_id", "generation_id", "artifact_id"],
            [
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
                "33333333-3333-4333-8333-333333333333",
                "44444444-4444-4444-8444-444444444444",
            ],
            strict=True,
        )
    )
    variants = []
    for idx, gene, af in [(0, "GENE1", 0.1), (1, "GENE2", None), (2, "GENE1", 0.1)]:
        row = dict.fromkeys(packet["field_registry"]["variants"])
        row.update(
            variant_idx=idx,
            gene_symbol=gene,
            chromosome="1",
            position=100 + idx,
            reference_allele="A",
            alternate_allele="G",
            acmg_class="VUS",
            global_af=af,
        )
        variants.append(row)
    source = {k: ids[k] for k in ["analysis_id", "case_id", "generation_id"]}
    source.update(
        schema_version="2",
        profile="singleton-germline-v2",
        summary={
            "classifier_version": "source-v1",
            "classifier_version_label": None,
            "pathogenic_count": 0,
            "likely_pathogenic_count": 0,
        },
        provenance={
            "request_sha256": "a" * 64,
            "clinical_profile_sha256": "b" * 64,
            "accepted_clinical_profile": {"demographics": {"age_years": 42}},
            "classification": "recorded_generation_without_mutable_annotation_overlays",
        },
        coverage={
            "variants": "all_processed_rows_after_filtering_preset",
            "filtering_preset": "strict",
            "variant_identity": "variant_idx_is_generation_local; allele_fields_are_recorded",
            "raw_input_variants": False,
        },
        collections={"variants": {"row_count": 3, "unavailable_fields": []}},
        variants=variants,
    )
    for collection in ["phenotype_matches", "screening_results", "literature_results"]:
        source[collection] = []
        source["collections"][collection] = {
            "state": "not_requested",
            "row_count": 0,
            "unavailable_fields": [],
        }
    source["gene_summaries"] = [
        {
            "type": "metadata",
            "session_id": ids["case_id"],
            "total_genes": 2,
            "total_variants": 3,
            "impact_by_acmg": {},
        },
        {"type": "gene", "data": {"gene_symbol": "GENE1", "variant_count": 2}},
        {"type": "gene", "data": {"gene_symbol": "GENE2", "variant_count": 1}},
        {"type": "complete", "session_id": ids["case_id"], "total_streamed": 2},
    ]
    identity = dict(
        ids, manifest_sha256="c" * 64, source_expires_at="2099-01-01T00:00:00+00:00"
    )
    path = tmp_path / "export.json"

    def save(value=source, raw=None):
        data = (
            raw
            if raw is not None
            else json.dumps(value, separators=(",", ":")).encode()
        )
        path.write_bytes(data)
        identity.update(
            artifact_sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)
        )
        return str(path)

    save()
    return source, identity, path, save


def invoke(name, frozen, packet, **args):
    _, identity, path, _ = frozen
    return execute_view(
        name,
        dict(analysis_id=identity["analysis_id"], **args),
        identity,
        str(path),
        packet,
    )


def test_all_six_views_and_numeric_wire(frozen, packet):
    for name in packet["input_schemas"]:
        args = {}
        if name == "query_analysis_export_records":
            args = {"collection": "variants"}
        if name == "get_analysis_export_variant":
            args = {"variant_idx": "0"}
        if name == "get_analysis_export_gene_records":
            args = {"gene_symbol": "GENE1", "collection": "variants"}
        result = invoke(name, frozen, packet, **args)
        assert result["source_view"] == name
        assert result["generation_id"] == frozen[1]["generation_id"]
        Draft202012Validator(
            packet["output_schemas"][name], format_checker=FormatChecker()
        ).validate({"ok": True, "data": result})
    variant = invoke("get_analysis_export_variant", frozen, packet, variant_idx="0")[
        "record"
    ]
    assert variant["variant_idx"] == "0" and variant["global_af"] == "0.1"
    assert variant["acmg_rule_evidence"] is None


def test_decimal_precision_above_binary_float(frozen, packet):
    source, _, _, save = frozen
    raw = json.dumps(source, separators=(",", ":")).replace(
        '"global_af":0.1', '"global_af":0.10000000000000000001', 1
    )
    save(raw=raw.encode())
    result = invoke(
        "query_analysis_export_records",
        frozen,
        packet,
        collection="variants",
        filters=[
            {"field": "global_af", "operator": "eq", "value": "0.10000000000000000001"}
        ],
        projection=["global_af"],
    )
    from folklore_mcp_service.case_tools.common import wire_numbers

    required = [
        "variant_idx",
        "position",
        "chromosome",
        "reference_allele",
        "alternate_allele",
        "acmg_class",
    ]
    expected = wire_numbers({field: source["variants"][0][field] for field in required})
    expected["global_af"] = "0.10000000000000000001"
    assert result["records"] == [expected]
    Draft202012Validator(
        packet["output_schemas"]["query_analysis_export_records"],
        format_checker=FormatChecker(),
    ).validate({"ok": True, "data": result})


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(schema_version="1"),
        lambda s: s.update(profile="unknown-profile"),
        lambda s: s["collections"]["variants"].update(row_count=True),
        lambda s: s["variants"][0].update(position=True),
        lambda s: s["collections"]["variants"].update(unavailable_fields=[{}]),
    ],
)
def test_unsupported_or_malformed_source_typed(frozen, packet, change):
    change(frozen[0])
    frozen[3]()
    with pytest.raises(CaseError):
        invoke("get_analysis_export_summary", frozen, packet)


def test_source_nullable_classifier_is_preserved(frozen, packet):
    frozen[0]["variants"][0]["acmg_class"] = None
    frozen[3]()
    assert (
        invoke("get_analysis_export_variant", frozen, packet, variant_idx="0")[
            "record"
        ]["acmg_class"]
        is None
    )


def test_symlink_artifact_refused(frozen, packet, tmp_path):
    link = tmp_path / "export-link.json"
    link.symlink_to(frozen[2])
    with pytest.raises(CaseError):
        execute_view(
            "get_analysis_export_summary",
            {"analysis_id": frozen[1]["analysis_id"]},
            frozen[1],
            str(link),
            packet,
        )


def test_exact_numeric_filter_stable_sort_and_continuation(frozen, packet):
    args = {
        "collection": "variants",
        "filters": [{"field": "global_af", "operator": "eq", "value": "0.1"}],
        "sort": [{"field": "global_af", "direction": "desc"}],
        "limit": 1,
    }
    first = invoke("query_analysis_export_records", frozen, packet, **args)
    assert [r["variant_idx"] for r in first["records"]] == ["0"]
    assert first["matched_count"] == 2 and first["has_more"]
    second = execute_view(
        "query_analysis_export_records",
        dict(analysis_id=frozen[1]["analysis_id"], **args),
        frozen[1],
        str(frozen[2]),
        packet,
        first["__cursor_state"],
    )
    assert [r["variant_idx"] for r in second["records"]] == ["2"]
    assert not second["has_more"]


def test_unavailable_and_null_are_different(frozen, packet):
    source, _, _, save = frozen
    source["collections"]["variants"]["unavailable_fields"] = ["genome_build"]
    save()
    with pytest.raises(CaseError, match="unavailable"):
        invoke(
            "query_analysis_export_records",
            frozen,
            packet,
            collection="variants",
            filters=[{"field": "genome_build", "operator": "is_null"}],
        )
    result = invoke(
        "query_analysis_export_records",
        frozen,
        packet,
        collection="variants",
        filters=[{"field": "global_af", "operator": "is_null"}],
    )
    assert [r["variant_idx"] for r in result["records"]] == ["1"]


@pytest.mark.parametrize("state", ["not_requested", "failed", "skipped"])
def test_module_availability_not_empty_success(frozen, packet, state):
    source, _, _, save = frozen
    source["collections"]["phenotype_matches"]["state"] = state
    save()
    r = invoke(
        "query_analysis_export_records", frozen, packet, collection="phenotype_matches"
    )
    assert r["availability"] == state and r["matched_count"] is None
    assert r["records"] == [] and not r["has_more"]


def test_succeeded_no_hpo_empty(frozen, packet):
    source, _, _, save = frozen
    source["collections"]["phenotype_matches"].update(
        state="succeeded", reason="no_variants_with_hpo"
    )
    save()
    result = invoke(
        "query_analysis_export_records", frozen, packet, collection="phenotype_matches"
    )
    assert result["availability"] == "available" and result["matched_count"] == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s["variants"].append(deepcopy(s["variants"][0])),
        lambda s: s["gene_summaries"][-1].update(total_streamed=3),
        lambda s: s.update(generation_id="55555555-5555-4555-8555-555555555555"),
    ],
)
def test_integrity_rejection(frozen, packet, mutate):
    source, _, _, save = frozen
    mutate(source)
    save()
    with pytest.raises(CaseError):
        invoke("get_analysis_export_summary", frozen, packet)


def test_digest_mismatch(frozen, packet):
    frozen[2].write_bytes(frozen[2].read_bytes() + b" ")
    with pytest.raises(CaseError):
        invoke("get_analysis_export_summary", frozen, packet)


def test_generation_and_variant_identity(frozen, packet):
    with pytest.raises(CaseError) as failure:
        invoke("get_analysis_export_variant", frozen, packet, variant_idx="999")
    assert failure.value.code == "record_not_found"
    with pytest.raises(CaseError) as failure:
        invoke(
            "get_analysis_export_summary",
            frozen,
            packet,
            expected_generation_id="55555555-5555-4555-8555-555555555555",
        )
    assert failure.value.code == "generation_conflict"


def test_gene_exact_and_screening_index_link(frozen, packet):
    source, _, _, save = frozen
    row = dict.fromkeys(packet["field_registry"]["screening_results"])
    row.update(variant_idx=2, total_score=0.25)
    source["screening_results"] = [row]
    source["collections"]["screening_results"].update(
        state="succeeded", row_count=1, analyzed_count=3
    )
    save()
    result = invoke(
        "get_analysis_export_gene_records",
        frozen,
        packet,
        gene_symbol="GENE1",
        collection="screening_results",
    )
    assert [r["variant_idx"] for r in result["records"]] == ["2"]
    assert "gene_symbol" not in result["records"][0]


def test_no_duplicate_json_keys_or_nonfinite_numbers(frozen, packet):
    for raw in [b'{"schema_version":"2","schema_version":"2"}', b'{"x":NaN}']:
        frozen[3](raw=raw)
        with pytest.raises(CaseError):
            invoke("get_analysis_export_summary", frozen, packet)


def test_record_and_response_budgets(frozen, packet):
    smaller = deepcopy(packet)
    smaller["limits"]["single_record_bytes"] = 10
    with pytest.raises(CaseError) as failure:
        invoke("get_analysis_export_summary", frozen, smaller)
    assert failure.value.code == "export_budget_exceeded"
    smaller = deepcopy(packet)
    smaller["limits"]["response_bytes"] = 100
    with pytest.raises(CaseError) as failure:
        invoke("get_analysis_export_variant", frozen, smaller, variant_idx="0")
    assert failure.value.code == "response_budget_exceeded"


@pytest.mark.asyncio
async def test_case_service_all_export_views_real_http_client_and_worker(
    frozen, packet, tmp_path
):
    import httpx
    from test_case_api import KEY, manifest

    from folklore_mcp_service.case_tools.api_client import ApiClient
    from folklore_mcp_service.case_tools.main import CaseService

    raw = frozen[2].read_bytes()
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer " + KEY
        if request.url.path.endswith("/results"):
            return httpx.Response(200, json=manifest(raw))
        return httpx.Response(
            200, content=raw, headers={"Content-Type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = CaseService(
            KEY,
            tmp_path / "state",
            tmp_path / "output",
            api=ApiClient(KEY, client=http),
        )
        try:
            for name in packet["input_schemas"]:
                args = {"analysis_id": frozen[1]["analysis_id"]}
                if name == "query_analysis_export_records":
                    args.update(collection="variants", limit=1)
                if name == "get_analysis_export_variant":
                    args.update(variant_idx="0")
                if name == "get_analysis_export_gene_records":
                    args.update(gene_symbol="GENE1", collection="variants", limit=1)
                response = await service.call(name, args)
                envelope = response.model_dump(by_alias=True)["structuredContent"]
                assert envelope["ok"], (name, envelope)
                assert (
                    len(
                        json.dumps(
                            response.model_dump(mode="json"), separators=(",", ":")
                        ).encode()
                    )
                    <= 65536
                )
                if envelope["data"].get("has_more"):
                    args["cursor"] = envelope["data"]["next_cursor"]
                    assert isinstance(args["cursor"], str)
                    second = await service.call(name, args)
                    assert second.model_dump(by_alias=True)["structuredContent"][
                        "ok"
                    ], second.model_dump(by_alias=True)["structuredContent"]
                    assert (
                        second.model_dump(by_alias=True)["structuredContent"]["data"][
                            "records"
                        ]
                        != envelope["data"]["records"]
                    )
            assert sum("/artifacts/" in path for path in calls) == 1
            assert not list(service.exports.staging_dir.iterdir())
        finally:
            await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_at", [5, 6])
async def test_case_service_cache_never_bypasses_before_or_after_auth(
    frozen, tmp_path, fail_at
):
    import httpx
    from test_case_api import KEY, A, manifest

    from folklore_mcp_service.case_tools.api_client import ApiClient
    from folklore_mcp_service.case_tools.main import CaseService

    raw = frozen[2].read_bytes()
    reads = 0
    downloads = 0

    def handler(request):
        nonlocal reads, downloads
        if request.url.path.endswith("/results"):
            reads += 1
            if reads >= fail_at:
                return httpx.Response(
                    403,
                    json={
                        "error": {
                            "code": "admission_denied",
                            "message": "Denied",
                            "retryable": False,
                        },
                        "request_id": A,
                    },
                    headers={"X-Request-ID": A},
                )
            return httpx.Response(200, json=manifest(raw))
        downloads += 1
        return httpx.Response(
            200, content=raw, headers={"Content-Type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = CaseService(
            KEY,
            tmp_path / "state",
            tmp_path / "output",
            api=ApiClient(KEY, client=http),
        )
        try:
            args = {"analysis_id": A}
            first = await service.call("get_analysis_export_summary", args)
            assert first.model_dump(by_alias=True)["structuredContent"]["ok"]
            second = await service.call("get_analysis_export_summary", args)
            result = second.model_dump(by_alias=True)["structuredContent"]
            assert (
                result["ok"] is False and result["error"]["code"] == "admission_denied"
            )
            assert downloads == 1
            assert not service.exports.entries and not service.exports.cursors
            assert not list(service.exports.staging_dir.iterdir())
        finally:
            await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["query_analysis_export_records", "get_analysis_export_gene_records"]
)
async def test_narrow_variant_projection_keeps_contract_required_source_header(
    frozen, packet, tmp_path, name
):
    import httpx
    from test_case_api import KEY, manifest

    from folklore_mcp_service.case_tools.api_client import ApiClient
    from folklore_mcp_service.case_tools.common import wire_numbers
    from folklore_mcp_service.case_tools.main import CaseService

    raw = frozen[2].read_bytes()

    def handler(request):
        assert request.headers["Authorization"] == "Bearer " + KEY
        if request.url.path.endswith("/results"):
            return httpx.Response(200, json=manifest(raw))
        return httpx.Response(
            200, content=raw, headers={"Content-Type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = CaseService(
            KEY,
            tmp_path / "state",
            tmp_path / "output",
            api=ApiClient(KEY, client=http),
        )
        try:
            args = {
                "analysis_id": frozen[1]["analysis_id"],
                "collection": "variants",
                "projection": ["gene_symbol"],
                "limit": 1,
            }
            if name == "get_analysis_export_gene_records":
                args["gene_symbol"] = "GENE1"
            response = await service.call(name, args)
            envelope = response.structured_content
            assert envelope["ok"], envelope
            required = packet["output_schemas"]["query_analysis_export_records"][
                "$defs"
            ]["record_variants"]["required"]
            first = envelope["data"]["records"][0]
            source = frozen[0]["variants"][0]
            assert set(first) == set(required) | {"gene_symbol"}
            assert first == wire_numbers(
                {field: source[field] for field in [*required, "gene_symbol"]}
            )
            assert envelope["data"]["has_more"] is True
            second = await service.call(
                name, {**args, "cursor": envelope["data"]["next_cursor"]}
            )
            assert second.structured_content["ok"]
            assert set(second.structured_content["data"]["records"][0]) == set(first)
            assert (
                second.structured_content["data"]["records"][0]["variant_idx"]
                != first["variant_idx"]
            )
        finally:
            await service.close()


@pytest.mark.parametrize(
    "collection,name",
    [
        (collection, name)
        for collection in (
            "variants",
            "gene_summaries",
            "phenotype_matches",
            "screening_results",
            "literature_results",
        )
        for name in (
            "query_analysis_export_records",
            "get_analysis_export_gene_records",
        )
        if not (
            name == "get_analysis_export_gene_records"
            and collection == "literature_results"
        )
    ],
)
def test_required_headers_survive_narrow_projection_for_every_collection(
    frozen, packet, collection, name
):
    from folklore_mcp_service.case_tools.common import wire_numbers

    source, _, _, save = frozen
    for module in ("phenotype_matches", "screening_results", "literature_results"):
        row = dict.fromkeys(packet["field_registry"][module])
        if module == "literature_results":
            row.update(pmid="001234", title="Synthetic paper")
        else:
            row["variant_idx"] = 0
        if module == "phenotype_matches":
            row.update(
                gene_symbol="GENE1", individual_matches=[], phenotype_match_score=0.125
            )
        if module == "screening_results":
            row["total_score"] = 0.25
        source[module] = [row]
        source["collections"][module].update(state="succeeded", row_count=1)
    save()
    projection = {
        "variants": "gene_symbol",
        "gene_summaries": "data.variant_count",
        "phenotype_matches": "phenotype_match_score",
        "screening_results": "total_score",
        "literature_results": "title",
    }[collection]
    args = {"collection": collection, "projection": [projection]}
    if name == "get_analysis_export_gene_records":
        args["gene_symbol"] = "GENE1"
    result = invoke(name, frozen, packet, **args)
    assert result["records"]
    result.pop("__cursor_state", None)
    Draft202012Validator(
        packet["output_schemas"][name], format_checker=FormatChecker()
    ).validate({"ok": True, "data": result})
    row = result["records"][0]
    if collection == "gene_summaries":
        assert row == {
            "type": "gene",
            "data": {"gene_symbol": "GENE1", "variant_count": "2"},
        }
    else:
        required = {
            "variants": {
                "variant_idx",
                "position",
                "chromosome",
                "reference_allele",
                "alternate_allele",
                "acmg_class",
            },
            "phenotype_matches": {"variant_idx"},
            "screening_results": {"variant_idx"},
            "literature_results": {"pmid"},
        }[collection]
        assert set(row) == required | {projection}
        from folklore_mcp_service.case_tools.common import parse_json

        original = parse_json(frozen[2].read_bytes())[collection][0]
        assert row == wire_numbers(
            {field: original[field] for field in required | {projection}}
        )


@pytest.mark.asyncio
async def test_genuine_sdk_narrow_query_and_gene_projection(frozen, tmp_path):
    import os
    import sys

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from test_case_api import KEY

    source = Path(__file__).parents[1] / "src"
    launch = (
        "import sys,socket;sys.path.insert(0,"
        + repr(str(Path(__file__).parent))
        + ");from pathlib import Path;import httpx;from test_case_api import manifest;from folklore_mcp_service.case_tools import main;from folklore_mcp_service.case_tools.api_client import ApiClient;raw=Path("
        + repr(str(frozen[2]))
        + ").read_bytes();handler=lambda request:httpx.Response(200,json=manifest(raw)) if request.url.path.endswith('/results') else httpx.Response(200,content=raw,headers={'Content-Type':'application/json'});main.ApiClient=lambda key:ApiClient(key,client=httpx.AsyncClient(transport=httpx.MockTransport(handler)));socket.socket.connect=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Network prohibited'));main.main()"
    )
    env = {
        "FOLKLORE_API_KEY": KEY,
        "FOLKLORE_CASE_STATE_DIR": str(tmp_path / "state"),
        "FOLKLORE_CASE_OUTPUT_DIR": str(tmp_path / "output"),
        "PYTHONPATH": str(source),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if os.environ.get("FOLKLORE_CASE_TEST_INSTALLED") == "1":
        env.pop("PYTHONPATH")
    with (tmp_path / "sdk-stderr").open("w") as err:
        async with stdio_client(
            StdioServerParameters(command=sys.executable, args=["-c", launch], env=env),
            errlog=err,
        ) as streams:
            async with ClientSession(*streams, read_timeout_seconds=15) as session:
                await session.initialize()
                for name in (
                    "query_analysis_export_records",
                    "get_analysis_export_gene_records",
                ):
                    args = {
                        "analysis_id": frozen[1]["analysis_id"],
                        "collection": "variants",
                        "projection": ["gene_symbol"],
                        "limit": 1,
                    }
                    if name == "get_analysis_export_gene_records":
                        args["gene_symbol"] = "GENE1"
                    result = await session.call_tool(name, args)
                    assert not result.is_error, result.structured_content
                    row = result.structured_content["data"]["records"][0]
                    assert set(row) == {
                        "variant_idx",
                        "position",
                        "chromosome",
                        "reference_allele",
                        "alternate_allele",
                        "acmg_class",
                        "gene_symbol",
                    }
                    assert row["variant_idx"] == "0" and row["gene_symbol"] == "GENE1"
