"""Offline HTTP and immutable delivery acceptance for CR024."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from folklore_mcp_service.case_tools.api_client import ApiClient
from folklore_mcp_service.case_tools.commands import Commands
from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.journal import Journal

KEY = "flk_" + "a" * 32 + "." + "b" * 43
A = "11111111-1111-4111-8111-111111111111"
C = "22222222-2222-4222-8222-222222222222"
G = "33333333-3333-4333-8333-333333333333"
F = "44444444-4444-4444-8444-444444444444"


def manifest(raw=b"{}"):
    value = {
        "schema_version": "2",
        "analysis_id": A,
        "case_id": C,
        "generation_id": G,
        "report_id": None,
        "summary": {
            "classifier_version": "fixture",
            "classifier_version_label": None,
            "pathogenic_count": 0,
            "likely_pathogenic_count": 0,
        },
        "artifacts": [
            {
                "artifact_id": F,
                "kind": "json",
                "content_type": "application/json",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "download_url": f"/folklore/v1/analyses/{A}/artifacts/{F}",
            }
        ],
        "warnings": [],
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    value["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()
    return value


@pytest.mark.asyncio
async def test_exact_context_route_and_bearer():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"contexts": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        api = ApiClient(KEY, client=transport)
        assert await api.context() == {"contexts": []}
    assert len(seen) == 1
    assert str(seen[0].url) == "https://api.helena.bio/folklore/v1/context"
    assert seen[0].headers["Authorization"] == "Bearer " + KEY


@pytest.mark.asyncio
async def test_manifest_rejects_identity_and_redirect():
    def handler(request):
        value = manifest()
        value["analysis_id"] = C
        return httpx.Response(200, json=value)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        api = ApiClient(KEY, client=transport)
        with pytest.raises(CaseError):
            await api.manifest(A)

    def redirect(request):
        return httpx.Response(302, headers={"Location": "https://example.invalid/"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as transport:
        with pytest.raises(CaseError):
            await ApiClient(KEY, client=transport).context()


@pytest.mark.asyncio
async def test_duplicate_json_and_wrong_rpc_free_route_fail_closed():
    def handler(request):
        return httpx.Response(
            200,
            content=b'{"contexts":[],"contexts":[]}',
            headers={"Content-Type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        api = ApiClient(KEY, client=transport)
        with pytest.raises(CaseError):
            await api.context()
        with pytest.raises(CaseError):
            await api.request("GET", "https://example.invalid/")
        with pytest.raises(CaseError):
            await api.request("GET", "/folklore/v1/contexts")


@pytest.mark.asyncio
async def test_failed_analysis_is_valid_read_result_and_no_numeric_loss():
    value = {
        "analysis_id": A,
        "case_id": C,
        "status": "failed",
        "stage": "validation",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "error": {"code": "input_validation_failed", "message": "Fixture"},
        "cost": {"reserved_units": 9007199254740993},
        "billing": {"state": "released"},
        "warnings": [],
        "links": {
            "self": f"/folklore/v1/analyses/{A}",
            "results": f"/folklore/v1/analyses/{A}/results",
            "folklore": f"https://folklore.helena.bio/app/analysis/{C}",
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value))
    ) as transport:
        result = await ApiClient(KEY, client=transport).status(A)
    assert result["status"] == "failed"
    assert result["cost"]["reserved_units"] == 9007199254740993


@pytest.mark.asyncio
async def test_download_exact_bytes_atomic_private_file_and_reauthorization(tmp_path):
    raw = b'{"exact":9007199254740993}'
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/results"):
            return httpx.Response(200, json=manifest(raw))
        return httpx.Response(
            200, content=raw, headers={"Content-Type": "application/json"}
        )

    output = tmp_path / "downloads"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        result = await ApiClient(KEY, client=transport).download(A, F, output)
    target = Path(result["local_path"])
    assert target.read_bytes() == raw
    assert target.stat().st_mode & 0o777 == 0o600
    assert output.stat().st_mode & 0o777 == 0o700
    assert calls.count(f"/folklore/v1/analyses/{A}/results") == 2
    assert result["generation_id"] == G
    assert list(output.iterdir()) == [target]


@pytest.mark.asyncio
async def test_revocation_during_download_returns_no_file(tmp_path):
    reads = 0

    def handler(request):
        nonlocal reads
        if request.url.path.endswith("/results"):
            reads += 1
            if reads == 2:
                return httpx.Response(
                    403,
                    json={
                        "error": {
                            "code": "admission_denied",
                            "message": KEY,
                            "retryable": False,
                        },
                        "request_id": A,
                    },
                    headers={"X-Request-ID": A},
                )
            return httpx.Response(200, json=manifest())
        return httpx.Response(
            200, content=b"{}", headers={"Content-Type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(CaseError) as caught:
            await ApiClient(KEY, client=transport).download(
                A, F, tmp_path / "downloads"
            )
    assert KEY not in str(caught.value)
    assert not list((tmp_path / "downloads").iterdir())


def test_credential_grammar_before_http():
    for key in ["", "Bearer " + KEY, KEY + "\n", "ordinary-human-jwt"]:
        with pytest.raises(CaseError) as caught:
            ApiClient(key)
        assert caught.value.code == "credential_type_unverified"


def submit_args():
    return {
        "idempotency_key": "submit-one",
        "context_binding_id": C,
        "profile": "singleton-germline-v1",
        "input": {
            "kind": "s3_object",
            "connection_id": F,
            "bucket": "fixture-bucket",
            "key": "case.vcf",
            "version_id": "immutable-1",
        },
        "max_cost_units": "9223372036854775807",
    }


class CommandApi:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def context(self):
        return {
            "contexts": [
                {
                    "actor_kind": "machine",
                    "context_binding_id": C,
                    "profiles": ["singleton-germline-v1"],
                }
            ]
        }

    async def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path, body, kwargs))
        if self.fail:
            raise CaseError("upstream_unavailable", retryable=True)
        return {"analysis_id": A, "case_id": C, "status": "queued"}

    async def status(self, analysis_id):
        return {"analysis_id": A, "case_id": C, "status": "running"}


@pytest.mark.asyncio
async def test_submit_exact_cost_defaults_and_accepted_replay(tmp_path):
    api = CommandApi()
    journal = Journal(tmp_path / "state", KEY)
    commands = Commands(api, journal)
    assert (await commands.call("submit_case_analysis", submit_args()))[
        "analysis_id"
    ] == A
    assert api.calls[0][2]["max_cost_units"] == 9223372036854775807
    assert api.calls[0][2]["clinical"] == {
        "hpo_ids": [],
        "filtering_preset": "strict",
        "language": "en",
    }
    assert "clinical_profile" not in api.calls[0][2]
    assert api.calls[0][3]["idempotency_key"] == "submit-one"
    await commands.call("submit_case_analysis", submit_args())
    assert len(api.calls) == 2
    assert api.calls[1][2] == api.calls[0][2]
    journal.close()


@pytest.mark.asyncio
async def test_uncertain_write_preserves_original_command_key(tmp_path):
    api = CommandApi()
    api.fail = True
    journal = Journal(tmp_path / "state", KEY)
    commands = Commands(api, journal)
    with pytest.raises(CaseError) as caught:
        await commands.call("submit_case_analysis", submit_args())
    assert caught.value.code == "command_uncertain"
    api.fail = False
    await commands.call("submit_case_analysis", submit_args())
    assert len(api.calls) == 2
    assert all(call[3]["idempotency_key"] == "submit-one" for call in api.calls)
    journal.close()


@pytest.mark.asyncio
async def test_write_commands_validate_before_network(tmp_path):
    api = CommandApi()
    journal = Journal(tmp_path / "state", KEY)
    commands = Commands(api, journal)
    invalid = submit_args()
    invalid["clinical_profile"] = None
    with pytest.raises(CaseError):
        await commands.call("submit_case_analysis", invalid)
    assert not api.calls
    journal.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "delays,expected_waits", [(["20", "20"], [20.0]), (["30", "30"], [30.0])]
)
async def test_retry_after_aggregate_wait_budget(monkeypatch, delays, expected_waits):
    waits, requests = [], []

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(
        "folklore_mcp_service.case_tools.api_client.asyncio.sleep", sleep
    )

    def handler(request):
        requests.append(request)
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "admission_unavailable",
                    "message": "Fixture",
                    "retryable": True,
                },
                "request_id": A,
            },
            headers={
                "X-Request-ID": A,
                "Retry-After": delays[min(len(requests) - 1, 1)],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(CaseError) as caught:
            await ApiClient(KEY, client=transport).context()
    assert waits == expected_waits
    assert len(requests) == 2
    assert caught.value.details["retry_after_seconds"] == int(delays[-1])


@pytest.mark.asyncio
async def test_fallback_retry_waits_one_then_two(monkeypatch):
    waits, calls = [], []

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(
        "folklore_mcp_service.case_tools.api_client.asyncio.sleep", sleep
    )

    def handler(request):
        calls.append(request)
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "admission_unavailable",
                    "message": "Fixture",
                    "retryable": True,
                },
                "request_id": A,
            },
            headers={"X-Request-ID": A},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(CaseError):
            await ApiClient(KEY, client=transport).context()
    assert waits == [1.0, 2.0]
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_declared_download_cap_and_digest_failure_leave_no_file(tmp_path):
    raw = b"{}"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=manifest(raw))
        )
    ) as transport:
        with pytest.raises(CaseError) as caught:
            await ApiClient(KEY, client=transport).download(
                A, F, tmp_path / "cap", max_bytes=1
            )
        assert caught.value.code == "export_budget_exceeded"

    def handler(request):
        if request.url.path.endswith("/results"):
            return httpx.Response(200, json=manifest(raw))
        return httpx.Response(
            200, content=b"!!", headers={"Content-Type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(CaseError) as caught:
            await ApiClient(KEY, client=transport).download(A, F, tmp_path / "digest")
        assert caught.value.code == "artifact_integrity_failed"
    assert not list((tmp_path / "digest").iterdir())


@pytest.mark.asyncio
async def test_request_identity_header_mismatch_not_definitive():
    def handler(request):
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": "admission_denied",
                    "message": "Fixture",
                    "retryable": False,
                },
                "request_id": C,
            },
            headers={"X-Request-ID": A},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(CaseError) as caught:
            await ApiClient(KEY, client=transport).context()
    assert caught.value.code == "source_contract_mismatch"


@pytest.mark.asyncio
async def test_review_and_cancel_use_create_scope_routes_without_status_dependency(
    tmp_path,
):
    api = CommandApi()

    async def forbidden_status(analysis_id):
        raise AssertionError("Write replay must not require analyses:read")

    api.status = forbidden_status
    journal = Journal(tmp_path / "state", KEY)
    commands = Commands(api, journal)
    args = {
        "analysis_id": A,
        "job_id": C,
        "attempt_id": G,
        "manifest_sha256": "e" * 64,
        "acknowledged": True,
    }
    await commands.call("acknowledge_sequencing_qc_review", args)
    await commands.call("acknowledge_sequencing_qc_review", args)
    await commands.call("request_sequencing_analysis_cancellation", {"analysis_id": A})
    assert [call[1] for call in api.calls] == [
        f"/folklore/v1/analyses/{A}/review",
        f"/folklore/v1/analyses/{A}/review",
        f"/folklore/v1/analyses/{A}/cancel",
    ]
    assert api.calls[-1][2] is None
    journal.close()


@pytest.mark.parametrize(
    "profile",
    ["singleton-germline-v1", "singleton-germline-v2", "singleton-sequencing-v1"],
)
def test_normalization_matches_frozen_api_command_contract(profile, monkeypatch):
    from folklore_mcp_service.case_tools.commands import normalize_submit
    from folklore_mcp_service.case_tools.common import json_bytes

    args = submit_args()
    args["profile"] = profile
    if profile == "singleton-germline-v1":
        args["clinical"] = {"hpo_ids": ["HP:0001250", "HP:0001250", "HP:0001263"]}
    else:
        args["clinical_profile"] = {
            "demographics": {"sex": "unknown"},
            "modules": {"enable_screening": True},
            "phenotype": {"hpo_ids": ["HP:0001250", "HP:0001250"]},
            "consent": {"secondary_findings": False, "carrier_results": False},
            "custom_genes": [{"gene_symbol": "TP53", "priority_score": 0.5001}],
        }
    if profile == "singleton-sequencing-v1":
        args["input"] = {
            "kind": "s3_sequencing",
            "connection_id": F,
            "input_type": "FASTQ",
            "objects": [
                {
                    "role": role,
                    "bucket": "fixture-bucket",
                    "key": role + ".fq.gz",
                    "version_id": "v1",
                }
                for role in ["R2", "R1"]
            ],
        }
        args["sequencing"] = {
            "sample": {
                "sample_id": "S1",
                "platform": "ILLUMINA",
                "assay_type": "WES",
                "read_length": 150,
                "library_protocol": "standard",
                "sequencer": "fixture",
            },
            "release_id": "release1",
            "reference_id": "reference1",
        }
    normalized = normalize_submit(args)
    expected = json.loads(
        (Path(__file__).parent / "data/normalized-submit-fixtures.json").read_text()
    )[profile]
    assert json_bytes(normalized) == json_bytes(expected)


@pytest.mark.asyncio
async def test_case_service_oversize_error_obeys_final_output_schema(tmp_path):
    from jsonschema import Draft202012Validator, FormatChecker

    from folklore_mcp_service.case_tools.contracts import OUTPUT_SCHEMAS
    from folklore_mcp_service.case_tools.main import CaseService

    value = manifest()
    value["artifacts"][0]["size_bytes"] = 128 * 1024 * 1024 + 1
    value["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in value.items() if k != "manifest_sha256"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()

    def handler(request):
        assert request.url.path.endswith("/results"), (
            "Oversize must fail before artifact transfer"
        )
        return httpx.Response(200, json=value)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        service = CaseService(
            KEY,
            tmp_path / "state",
            tmp_path / "output",
            api=ApiClient(KEY, client=transport),
        )
        try:
            result = await service.call(
                "download_analysis_result_file", {"analysis_id": A, "artifact_id": F}
            )
        finally:
            await service.close()
    envelope = result.structured_content
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "export_budget_exceeded"
    assert envelope["error"]["details"] == {
        "limit_name": "download_bytes",
        "limit": 128 * 1024 * 1024,
    }
    Draft202012Validator(
        OUTPUT_SCHEMAS["download_analysis_result_file"], format_checker=FormatChecker()
    ).validate(envelope)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "latest",
        "null_version",
        "control",
        "wrong_suffix",
        "source_traversal",
        "both_ages",
        "missing_consent",
        "panel_without_screening",
        "bad_panel_uuid",
        "duplicate_objects",
        "wrong_roles",
        "sequencing_suffix",
    ],
)
async def test_semantic_admission_denies_before_http_and_journal(case):
    class NoApi:
        async def context(self):
            raise AssertionError("Invalid command reached HTTP")

        async def request(self, *args, **kwargs):
            raise AssertionError("Invalid command reached HTTP")

    class NoJournal:
        def prepare(self, *args, **kwargs):
            raise AssertionError("Invalid command reached journal")

    args = submit_args()
    args["profile"] = "singleton-germline-v2"
    args["clinical_profile"] = {"demographics": {"sex": "unknown"}}
    if case == "latest":
        args["input"]["version_id"] = "LATEST"
    elif case == "null_version":
        args["input"]["version_id"] = "null"
    elif case == "control":
        args["input"]["key"] = "bad\nname.vcf"
    elif case == "wrong_suffix":
        args["input"]["key"] = "bad.bam"
    elif case == "source_traversal":
        args["input"]["key"] = "../case.vcf"
    elif case == "both_ages":
        args["clinical_profile"]["demographics"].update(age_years=0, age_days=0)
    elif case == "missing_consent":
        args["clinical_profile"]["modules"] = {"enable_screening": True}
    elif case == "panel_without_screening":
        args["clinical_profile"]["panel_ids"] = [C]
    elif case == "bad_panel_uuid":
        args["clinical_profile"].update(
            modules={"enable_screening": True},
            consent={"secondary_findings": False, "carrier_results": False},
            panel_ids=["not-a-uuid"],
        )
    else:
        args["profile"] = "singleton-sequencing-v1"
        args["sequencing"] = {
            "sample": {
                "sample_id": "S1",
                "platform": "ILLUMINA",
                "assay_type": "WES",
                "read_length": 150,
                "library_protocol": "standard",
                "sequencer": "fixture",
            },
            "release_id": "release1",
            "reference_id": "reference1",
        }
        args["input"] = {
            "kind": "s3_sequencing",
            "input_type": "FASTQ",
            "connection_id": F,
            "objects": [
                {
                    "role": "R1",
                    "bucket": "fixture-bucket",
                    "key": "R1.fq.gz",
                    "version_id": "v1",
                },
                {
                    "role": "R2",
                    "bucket": "fixture-bucket",
                    "key": "R2.fq.gz",
                    "version_id": "v1",
                },
            ],
        }
        if case == "duplicate_objects":
            args["input"]["objects"][1]["key"] = "R1.fq.gz"
        elif case == "wrong_roles":
            args["input"]["objects"].pop()
        else:
            args["input"]["objects"][1]["key"] = "R2.bam"
    with pytest.raises(CaseError) as caught:
        await Commands(NoApi(), NoJournal()).call("submit_case_analysis", args)
    assert caught.value.code == "invalid_input"


@pytest.mark.asyncio
async def test_case_service_full_machine_billing_context_obeys_wire_schema(tmp_path):
    from jsonschema import Draft202012Validator, FormatChecker

    from folklore_mcp_service.case_tools.contracts import OUTPUT_SCHEMAS
    from folklore_mcp_service.case_tools.main import CaseService

    value = {
        "contexts": [
            {
                "installation_id": A,
                "client_id": "fixture-client",
                "actor_kind": "machine",
                "user_id": None,
                "machine_principal_id": C,
                "credential_id": G,
                "contract_id": F,
                "billing_arrangement_id": None,
                "payer_organization_id": None,
                "organization_id": C,
                "organization_type": "laboratory",
                "role": "admin",
                "context_binding_id": C,
                "binding_version": 1,
                "grant_id": None,
                "grant_version": 1,
                "scopes": [
                    "analyses:create",
                    "analyses:read",
                    "results:read",
                    "credits:read",
                ],
                "connections": [
                    {
                        "connection_id": F,
                        "bucket": "fixture-bucket",
                        "key_prefix": "cases/",
                    }
                ],
                "profiles": ["singleton-germline-v2"],
                "context_name": None,
                "payer_name": None,
                "input_kinds": ["s3_object"],
                "billing": {
                    "unit": "credit_unit",
                    "units_per_credit": 1000,
                    "payer_organization_id": C,
                    "balance_status": "active",
                    "available_units": 9007199254740993,
                    "reserved_units": 0,
                    "price_status": "available",
                    "prices": [
                        {
                            "profile": "singleton-germline-v2",
                            "cost_units": 0,
                            "catalog_version": "fixture",
                            "effective_from": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                    "sequencing_prices": [],
                    "observed_at": "2026-01-01T00:00:00+00:00",
                    "billing_url": "https://account.helena.bio/billing",
                },
            }
        ]
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value))
    ) as transport:
        service = CaseService(
            KEY,
            tmp_path / "state",
            tmp_path / "output",
            api=ApiClient(KEY, client=transport),
        )
        try:
            result = await service.call("list_analysis_contexts", {})
        finally:
            await service.close()
    envelope = result.structured_content
    assert envelope["ok"] is True
    context = envelope["data"]["result"]["contexts"][0]
    assert context["binding_version"] == "1"
    assert context["billing"]["units_per_credit"] == "1000"
    assert context["billing"]["available_units"] == "9007199254740993"
    Draft202012Validator(
        OUTPUT_SCHEMAS["list_analysis_contexts"], format_checker=FormatChecker()
    ).validate(envelope)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["analysis_id", "case_id"])
async def test_accepted_replay_rejects_changed_identity_without_overwriting_history(
    tmp_path, field
):
    api = CommandApi()
    journal = Journal(tmp_path / "state", KEY)
    commands = Commands(api, journal)
    original = await commands.call("submit_case_analysis", submit_args())

    async def changed_response(method, path, body=None, **kwargs):
        return dict(original, **{field: G})

    api.request = changed_response
    with pytest.raises(CaseError) as caught:
        await commands.call("submit_case_analysis", submit_args())
    assert caught.value.code == "operation_conflict"
    from folklore_mcp_service.case_tools.commands import normalize_submit

    record = journal.prepare(
        "submit", "submit-one", "/folklore/v1/analyses", normalize_submit(submit_args())
    )
    assert record["state"] == "accepted"
    assert record["response"] == original
    journal.close()
