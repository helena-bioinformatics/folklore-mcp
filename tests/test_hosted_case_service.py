"""Hosted authority, isolation, durable recovery and verified remote handoff."""

import asyncio
import copy
import hashlib
import os
from uuid import uuid4

import httpx
import pytest
from jsonschema import Draft202012Validator

from folklore_mcp_service.case_tools.api_client import ApiClient
from folklore_mcp_service.case_tools.common import CaseError, json_bytes
from folklore_mcp_service.case_tools.contracts import INPUT_SCHEMAS, OUTPUT_SCHEMAS
from folklore_mcp_service.case_tools.hosted import (
    CALL_DISK_RESERVE,
    HOSTED_OUTPUT_SCHEMAS,
    HostedCaseManager,
    hosted_tools,
)
from folklore_mcp_service.case_tools.main import CaseService

KEY = "flk_" + "a" * 32 + "." + "b" * 43
OTHER = "flk_" + "c" * 32 + "." + "d" * 43
SECRET = b"s" * 32
A = "11111111-1111-4111-8111-111111111111"
C = "22222222-2222-4222-8222-222222222222"
G = "33333333-3333-4333-8333-333333333333"
F = "44444444-4444-4444-8444-444444444444"
TOOL = "list_analysis_contexts"


def payload(result):
    return result.structured_content


class API:
    def __init__(self, key, owner):
        self.key, self.owner = key, owner
        self.closed = False

    async def context(self):
        self.owner.auth.append(self.key)
        if self.key in self.owner.denied:
            raise CaseError("authentication_failed")
        return {"contexts": []}

    async def close(self):
        self.closed = True


class Factory:
    def __init__(self):
        self.auth = []
        self.denied = set()
        self.created = []

    def api(self, key):
        return API(key, self)

    def service(self, key, state, output):
        service = CaseService(key, state, output, api=self.api(key))
        self.created.append(service)
        return service

    def manager(self, path, **kwargs):
        return HostedCaseManager(
            path, SECRET, api_factory=self.api, service_factory=self.service, **kwargs
        )


@pytest.mark.asyncio
async def test_rejected_and_malformed_keys_create_no_namespace(tmp_path):
    f = Factory()
    f.denied.add(KEY)
    manager = f.manager(tmp_path / "root")
    try:
        assert (
            payload(await manager.call(KEY, TOOL, {}))["error"]["code"]
            == "authentication_failed"
        )
        assert (
            payload(await manager.call("not-a-key", TOOL, {}))["error"]["code"]
            == "authentication_required"
        )
        assert not [p for p in manager.root.iterdir() if p.is_dir()]
        assert f.created == []
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_authorize_catalog_is_ephemeral_and_closes_client(tmp_path):
    clients = []
    f = Factory()

    def api(key):
        client = f.api(key)
        clients.append(client)
        return client

    manager = HostedCaseManager(tmp_path / "root", SECRET, api_factory=api)
    try:
        assert await manager.authorize(KEY) == {"contexts": []}
        assert clients[0].closed
        assert not any(p.is_dir() for p in manager.root.iterdir())
        f.denied.add(KEY)
        with pytest.raises(CaseError):
            await manager.authorize(KEY)
        assert clients[1].closed
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_two_keys_separate_real_journals_same_idempotency_and_no_raw_key_on_disk(
    tmp_path,
):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    try:
        for key in (KEY, OTHER):
            assert payload(await manager.call(key, TOOL, {}))["ok"]
        first, second = f.created
        assert first.state_dir != second.state_dir
        for service in (first, second):
            record = service.journal.prepare(
                "submit",
                "same-key",
                "/folklore/v1/analyses",
                {"scope": str(service.state_dir)},
            )
            assert record["body"]["scope"] == str(service.state_dir)
        for path in manager.root.rglob("*"):
            assert KEY not in str(path) and OTHER not in str(path)
            if path.is_file():
                raw = path.read_bytes()
                assert KEY.encode() not in raw and OTHER.encode() not in raw
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_same_key_each_call_and_replay_rechecks_current_admission(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    try:
        assert payload(await manager.call(KEY, TOOL, {}))["ok"]
        service = f.created[0]
        calls = []
        original = service.call

        async def tracked(*args):
            calls.append(args)
            return await original(*args)

        service.call = tracked
        f.denied.add(KEY)
        result = payload(
            await manager.call(
                KEY, "request_sequencing_analysis_cancellation", {"analysis_id": A}
            )
        )
        assert result["error"]["code"] == "authentication_failed"
        assert "data" not in result and calls == []
        f.denied.clear()
        assert payload(await manager.call(KEY, TOOL, {}))["ok"]
        assert len(f.created) == 1 and f.auth.count(KEY) >= 4
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_idle_eviction_retains_encrypted_uncertain_command_and_reopens(tmp_path):
    f = Factory()
    now = [0]
    manager = f.manager(tmp_path / "root", clock=lambda: now[0], idle_seconds=1)
    try:
        await manager.call(KEY, TOOL, {})
        old = f.created[0]
        record = old.journal.prepare(
            "submit", "original", "/folklore/v1/analyses", {"identity": "original"}
        )
        old.journal.sending(record["id"])
        now[0] = 2
        assert payload(await manager.call(KEY, TOOL, {}))["ok"]
        assert len(f.created) == 2
        recovered = f.created[1].journal.prepare(
            "submit", "original", "/folklore/v1/analyses", {"identity": "original"}
        )
        assert recovered["state"] == "uncertain" and recovered["id"] == record["id"]
        assert (old.state_dir / "commands.sqlite3").exists()
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_active_service_not_evicted_close_waits_and_capacity_is_typed(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root", max_services=1)
    await manager.call(KEY, TOOL, {})
    entered, release = asyncio.Event(), asyncio.Event()
    original = f.created[0].call

    async def blocked(*args):
        entered.set()
        await release.wait()
        return await original(*args)

    f.created[0].call = blocked
    running = asyncio.create_task(manager.call(KEY, TOOL, {}))
    await entered.wait()
    assert (
        payload(await manager.call(OTHER, TOOL, {}))["error"]["code"]
        == "hosted_capacity_exceeded"
    )
    closing = asyncio.create_task(manager.close())
    await asyncio.sleep(0)
    assert not closing.done()
    release.set()
    assert payload(await running)["ok"]
    await closing
    assert manager._entries == {} and manager._reserved == 0


@pytest.mark.asyncio
async def test_cancelled_request_releases_active_lease(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    await manager.call(KEY, TOOL, {})
    entered = asyncio.Event()

    async def blocked(*args):
        entered.set()
        await asyncio.Event().wait()

    f.created[0].call = blocked
    task = asyncio.create_task(manager.call(KEY, TOOL, {}))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert manager._reserved == 0
    await manager.close()


@pytest.mark.asyncio
async def test_total_durable_namespace_limit_survives_restart_and_eviction(tmp_path):
    f = Factory()
    root = tmp_path / "root"
    manager = f.manager(root, max_services=1, max_namespaces=1)
    await manager.call(KEY, TOOL, {})
    await manager.close()
    manager = f.manager(root, max_services=1, max_namespaces=1)
    try:
        result = payload(await manager.call(OTHER, TOOL, {}))
        assert result["error"]["code"] == "hosted_capacity_exceeded"
        assert payload(await manager.call(KEY, TOOL, {}))["ok"]
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_disk_admission_and_single_worker_and_secret_loss_fail_closed(tmp_path):
    f = Factory()
    root = tmp_path / "root"
    manager = f.manager(root, max_disk_bytes=CALL_DISK_RESERVE)
    try:
        assert (
            payload(await manager.call(KEY, TOOL, {}))["error"]["code"]
            == "hosted_capacity_exceeded"
        )
        with pytest.raises(CaseError) as caught:
            f.manager(root)
        assert caught.value.code == "hosted_state_in_use"
    finally:
        await manager.close()
    with pytest.raises(CaseError) as caught:
        HostedCaseManager(root, b"x" * 32)
    assert caught.value.code == "hosted_state_unreadable"


@pytest.mark.asyncio
async def test_symlink_namespace_refused_without_following(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    try:
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        (manager.root / ("a" * 64)).symlink_to(outside)
        assert (
            payload(await manager.call(KEY, TOOL, {}))["error"]["code"]
            == "hosted_state_unreadable"
        )
    finally:
        await manager.close()


def manifest(raw):
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
    value["manifest_sha256"] = hashlib.sha256(json_bytes(value)).hexdigest()
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [None, "corrupt", "redirect", "revoked_after", "generation_changed"]
)
async def test_real_client_verified_download_remote_link_and_cleanup(tmp_path, failure):
    raw = b'{"synthetic":true}'
    value = manifest(raw)
    seen = []
    manifests = 0

    def handler(request):
        nonlocal manifests
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer " + KEY
        if request.url.path == "/folklore/v1/context":
            return httpx.Response(200, json={"contexts": []})
        if request.url.path.endswith("/results"):
            manifests += 1
            if failure == "revoked_after" and manifests >= 3:
                return httpx.Response(
                    401,
                    json={
                        "error": {
                            "code": "unauthorized",
                            "message": "Denied",
                            "retryable": False,
                        }
                    },
                )
            result = copy.deepcopy(value)
            if failure == "generation_changed" and manifests >= 3:
                result["generation_id"] = C
                result["manifest_sha256"] = hashlib.sha256(
                    json_bytes(
                        {k: v for k, v in result.items() if k != "manifest_sha256"}
                    )
                ).hexdigest()
            return httpx.Response(200, json=result)
        if failure == "redirect":
            return httpx.Response(
                302, headers={"Location": "https://foreign.invalid/private"}
            )
        return httpx.Response(
            200,
            content=b"wrong" if failure == "corrupt" else raw,
            headers={"Content-Type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:

        def api(key):
            return ApiClient(key, client=client)

        manager = HostedCaseManager(
            tmp_path / "root",
            SECRET,
            api_factory=api,
            service_factory=lambda key, state, output: CaseService(
                key, state, output, api=api(key)
            ),
        )
        try:
            result = await manager.call(
                KEY,
                "download_analysis_result_file",
                {"analysis_id": A, "artifact_id": F},
            )
            body = payload(result)
            Draft202012Validator(
                HOSTED_OUTPUT_SCHEMAS["download_analysis_result_file"]
            ).validate(body)
            assert body["ok"] == (failure is None)
            if failure is None:
                file = body["data"]["file"]
                assert (
                    file["download_url"]
                    == f"https://api.helena.bio/folklore/v1/analyses/{A}/artifacts/{F}"
                )
                assert (
                    "local_path" not in file
                    and file["sha256"] == hashlib.sha256(raw).hexdigest()
                )
                assert (
                    len(result.content) == 2
                    and result.content[1].type == "resource_link"
                )
            assert not list(manager.root.rglob("*.json")) and not list(
                manager.root.rglob("*.partial")
            )
            assert all(request.url.host == "api.helena.bio" for request in seen)
        finally:
            await manager.close()


def test_hosted_schema_delta_only_download_and_all_inputs_unchanged():
    assert len(INPUT_SCHEMAS) == len(HOSTED_OUTPUT_SCHEMAS) == 18
    for name in HOSTED_OUTPUT_SCHEMAS:
        Draft202012Validator.check_schema(HOSTED_OUTPUT_SCHEMAS[name])
        if name != "download_analysis_result_file":
            assert HOSTED_OUTPUT_SCHEMAS[name] == OUTPUT_SCHEMAS[name]
    assert "local_path" in str(OUTPUT_SCHEMAS["download_analysis_result_file"])
    assert "local_path" not in str(
        HOSTED_OUTPUT_SCHEMAS["download_analysis_result_file"]
    )
    tools = hosted_tools()
    assert len(tools) == 18
    for tool in tools:
        assert tool.input_schema == INPUT_SCHEMAS[tool.name]
        assert tool.output_schema == HOSTED_OUTPUT_SCHEMAS[tool.name]
    tools[0].input_schema.clear()
    assert hosted_tools()[0].input_schema


@pytest.mark.asyncio
async def test_cancellation_after_file_publication_removes_owned_temporary_original(
    tmp_path,
):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    await manager.call(KEY, TOOL, {})
    service = f.created[0]
    entered = asyncio.Event()

    async def interrupted(*args):
        path = service.output_dir / (str(uuid4()) + ".json")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(b"synthetic")
        entered.set()
        await asyncio.Event().wait()

    service.call = interrupted
    task = asyncio.create_task(
        manager.call(
            KEY, "download_analysis_result_file", {"analysis_id": A, "artifact_id": F}
        )
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert list(service.output_dir.iterdir()) == []
    assert manager._reserved == 0
    await manager.close()


@pytest.mark.asyncio
async def test_replay_different_normalized_body_remains_journal_conflict(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    try:
        await manager.call(KEY, TOOL, {})
        journal = f.created[0].journal
        journal.prepare("submit", "original", "/folklore/v1/analyses", {"input": "one"})
        with pytest.raises(CaseError) as caught:
            journal.prepare(
                "submit", "original", "/folklore/v1/analyses", {"input": "two"}
            )
        assert caught.value.code == "operation_conflict"
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_revoke_during_blocked_call_prevents_disclosure(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    await manager.call(KEY, TOOL, {})
    service = f.created[0]
    entered, release = asyncio.Event(), asyncio.Event()
    original = service.call

    async def blocked(*args):
        entered.set()
        await release.wait()
        return await original(*args)

    service.call = blocked
    running = asyncio.create_task(manager.call(KEY, TOOL, {}))
    await entered.wait()
    f.denied.add(KEY)
    release.set()
    result = payload(await running)
    assert result["error"]["code"] == "authentication_failed" and "data" not in result
    await manager.close()


@pytest.mark.asyncio
async def test_same_key_active_calls_bounded_without_unlimited_queue(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root", max_services=1)
    await manager.call(KEY, TOOL, {})
    entered, release = asyncio.Event(), asyncio.Event()
    original = f.created[0].call

    async def blocked(*args):
        entered.set()
        await release.wait()
        return await original(*args)

    f.created[0].call = blocked
    running = asyncio.create_task(manager.call(KEY, TOOL, {}))
    await entered.wait()
    assert (
        payload(await manager.call(KEY, TOOL, {}))["error"]["code"]
        == "hosted_capacity_exceeded"
    )
    release.set()
    assert payload(await running)["ok"]
    await manager.close()


@pytest.mark.asyncio
async def test_catalog_authorization_has_failfast_global_io_bound(tmp_path):
    f = Factory()
    entered, release = asyncio.Event(), asyncio.Event()

    class BlockedAPI(API):
        async def context(self):
            entered.set()
            await release.wait()
            return {"contexts": []}

    manager = HostedCaseManager(
        tmp_path / "root",
        SECRET,
        max_services=1,
        api_factory=lambda key: BlockedAPI(key, f),
    )
    request = asyncio.create_task(manager.authorize(KEY))
    await entered.wait()
    with pytest.raises(CaseError) as caught:
        await manager.authorize(OTHER)
    assert caught.value.code == "hosted_capacity_exceeded"
    assert not any(p.is_dir() for p in manager.root.iterdir())
    release.set()
    await request
    assert manager._authorizing == 0
    await manager.close()


@pytest.mark.asyncio
async def test_namespace_reopen_sweeps_only_owned_crash_downloads_even_for_context(
    tmp_path,
):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    await manager.call(KEY, TOOL, {})
    service = f.created[0]
    output = service.output_dir
    journal = service.state_dir / "commands.sqlite3"
    await manager.close()
    leftovers = [
        output / (str(uuid4()) + ".json"),
        output / ("." + str(uuid4()) + ".partial"),
    ]
    for path in leftovers:
        path.write_bytes(b"synthetic")
        path.chmod(0o600)
    unrelated = output / "retained-unrelated.txt"
    unrelated.write_text("keep")
    unrelated.chmod(0o600)
    manager = f.manager(manager.root)
    try:
        assert payload(await manager.call(KEY, TOOL, {}))["ok"]
        assert all(not path.exists() for path in leftovers)
        assert unrelated.read_text() == "keep" and journal.exists()
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_repeated_cancel_while_release_waits_does_not_leak_lease(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    await manager.call(KEY, TOOL, {})
    entered = asyncio.Event()

    async def blocked(*args):
        entered.set()
        await asyncio.Event().wait()

    f.created[0].call = blocked
    running = asyncio.create_task(manager.call(KEY, TOOL, {}))
    await entered.wait()
    await manager._condition.acquire()
    try:
        running.cancel()
        await asyncio.sleep(0)
        running.cancel()
        await asyncio.sleep(0)
        assert manager._reserved > 0
    finally:
        manager._condition.release()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert manager._reserved == 0 and all(
        entry.active == 0 for entry in manager._entries.values()
    )
    await asyncio.wait_for(manager.close(), 1)


@pytest.mark.asyncio
async def test_reopen_does_not_sweep_before_exclusive_journal_ownership(tmp_path):
    f = Factory()
    manager = f.manager(tmp_path / "root")
    state = manager.root / manager._namespace(KEY)
    state.mkdir(mode=0o700)
    output = state / "downloads"
    output.mkdir(mode=0o700)
    external = f.service(KEY, state, output)
    original = output / (str(uuid4()) + ".json")
    original.write_bytes(b"synthetic")
    original.chmod(0o600)
    try:
        result = payload(await manager.call(KEY, TOOL, {}))
        assert result["error"]["code"] == "journal_in_use"
        assert original.read_bytes() == b"synthetic"
    finally:
        await external.close()
        await manager.close()


@pytest.mark.asyncio
async def test_authority_timeout_is_typed_bounded_and_cleans_up(tmp_path, monkeypatch):
    import folklore_mcp_service.case_tools.hosted as hosted

    monkeypatch.setattr(hosted, "AUTHORIZATION_TIMEOUT_SECONDS", 0.01)
    f = Factory()
    clients = []

    class SlowAPI(API):
        async def context(self):
            await asyncio.Event().wait()

    def api(key):
        client = SlowAPI(key, f)
        clients.append(client)
        return client

    manager = HostedCaseManager(tmp_path / "root", SECRET, api_factory=api)
    try:
        with pytest.raises(CaseError) as caught:
            await asyncio.wait_for(manager.authorize(KEY), 1)
        assert caught.value.code == "upstream_unavailable" and caught.value.retryable
        assert clients[0].closed and manager._authorizing == 0
        assert not any(p.is_dir() for p in manager.root.iterdir())
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_first_catalog_authorization_redacts_transport_debug_before_service(
    tmp_path, caplog
):
    import logging

    f = Factory()
    previous = logging.getLogRecordFactory()

    class LoggingAPI(API):
        async def context(self):
            logging.getLogger("httpx").debug(
                "Authorization Bearer %s /private-case", self.key
            )
            return {"contexts": []}

    manager = HostedCaseManager(
        tmp_path / "root", SECRET, api_factory=lambda key: LoggingAPI(key, f)
    )
    try:
        with caplog.at_level(logging.DEBUG, logger="httpx"):
            await manager.authorize(KEY)
        assert not manager._entries
        assert "Private protocol transport event" in caplog.text
        assert KEY not in caplog.text and "/private-case" not in caplog.text
    finally:
        await manager.close()
    assert logging.getLogRecordFactory() is previous
