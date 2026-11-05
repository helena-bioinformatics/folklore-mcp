"""Independent synthetic authorization/cache/cursor acceptance for CR024."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from folklore_mcp_service.case_tools import store as module
from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.store import ExportStore

AID = "11111111-1111-4111-8111-111111111111"
GID = "22222222-2222-4222-8222-222222222222"
RAW = b'{"synthetic":"private-fixture"}'


class FixtureApi:
    def __init__(self):
        self.reads = 0
        self.downloads = 0
        self.fail_at = None
        self.failure = "authorization_failed"
        self.generation = GID

    async def manifest(self, _analysis):
        self.reads += 1
        if self.reads == self.fail_at:
            raise CaseError(self.failure)
        return {
            "analysis_id": AID,
            "case_id": "33333333-3333-4333-8333-333333333333",
            "generation_id": self.generation,
            "manifest_sha256": "a" * 64,
            "expires_at": "2099-01-01T00:00:00Z",
            "artifacts": [
                {
                    "kind": "json",
                    "artifact_id": "44444444-4444-4444-8444-444444444444",
                    "size_bytes": len(RAW),
                    "sha256": sha256(RAW).hexdigest(),
                }
            ],
        }

    async def download(self, _analysis, _artifact, directory, **_kwargs):
        self.downloads += 1
        path = directory / "synthetic-original.json"
        path.write_bytes(RAW)
        path.chmod(0o600)
        return {"local_path": str(path)}


@pytest.fixture
def harness(tmp_path, monkeypatch):
    state = tmp_path / "private"
    state.mkdir(mode=0o700)
    api = FixtureApi()
    journal = SimpleNamespace(state_key=b"x" * 32, credential_fingerprint="first-key")
    worker_calls = []

    async def view(name, args, identity, path, packet, cursor):
        assert Path(path).read_bytes() == RAW
        worker_calls.append((name, deepcopy(args), deepcopy(identity), cursor))
        return {
            "records": [{"synthetic": "private-fixture"}],
            "has_more": True,
            "next_cursor": None,
            "__cursor_state": {"offset": 1, "last_sort": ["private-fixture"]},
        }

    monkeypatch.setattr(module, "run_view", view)
    instance = ExportStore(api, journal, state)
    yield instance, api, worker_calls, state, journal
    instance.close()


def arguments(**changes):
    return {"analysis_id": AID, "collection": "variants", **changes}


@pytest.mark.asyncio
async def test_cache_requires_two_current_manifest_reads_per_disclosure(harness):
    instance, api, calls, state, _ = harness
    await instance.call("query_analysis_export_records", arguments())
    await instance.call("query_analysis_export_records", arguments())
    assert api.reads == 4
    assert api.downloads == 1
    assert len(calls) == 2
    assert not list((state / "staging").iterdir())
    encrypted = next((state / "cache").iterdir()).read_bytes()
    assert RAW not in encrypted
    assert b"private-fixture" not in encrypted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["authorization_failed", "source_expired", "rate_limited", "upstream_unavailable"],
)
async def test_failed_current_authorization_cannot_disclose_cached_data(
    harness, failure
):
    instance, api, calls, state, _ = harness
    await instance.call("query_analysis_export_records", arguments())
    api.fail_at, api.failure = api.reads + 1, failure
    with pytest.raises(CaseError, match=failure.replace("_", " ").capitalize()):
        await instance.call("query_analysis_export_records", arguments())
    assert len(calls) == 1
    assert api.downloads == 1
    assert not instance.entries and not instance.cursors
    assert not list((state / "cache").iterdir())


@pytest.mark.asyncio
async def test_revocation_during_worker_discards_result_and_cursor(harness):
    instance, api, calls, state, _ = harness
    api.fail_at = 2
    with pytest.raises(CaseError):
        await instance.call("query_analysis_export_records", arguments())
    assert len(calls) == 1
    assert not instance.entries and not instance.cursors
    assert not list((state / "cache").iterdir())
    assert not list((state / "staging").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"projection": ["variant_idx"]},
        {"limit": 1},
        {"filters": [{"field": "gene_symbol", "operator": "eq", "value": "OTHER"}]},
    ],
)
async def test_cursor_cannot_change_query_or_pagination(harness, change):
    instance, api, calls, _, _ = harness
    result = await instance.call("query_analysis_export_records", arguments())
    token = result["next_cursor"]
    assert "private-fixture" not in token
    with pytest.raises(CaseError) as error:
        await instance.call(
            "query_analysis_export_records", arguments(cursor=token, **change)
        )
    assert error.value.code == "invalid_cursor"
    assert len(calls) == 1
    assert api.downloads == 1


@pytest.mark.asyncio
async def test_cursor_cannot_follow_changed_generation(harness):
    instance, api, calls, _, _ = harness
    result = await instance.call("query_analysis_export_records", arguments())
    api.generation = "55555555-5555-4555-8555-555555555555"
    with pytest.raises(CaseError) as error:
        await instance.call(
            "query_analysis_export_records", arguments(cursor=result["next_cursor"])
        )
    assert error.value.code == "stale_cursor"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_tampered_cache_never_reaches_worker(harness):
    instance, api, calls, _, _ = harness
    await instance.call("query_analysis_export_records", arguments())
    entry = next(iter(instance.entries.values()))["path"]
    raw = bytearray(entry.read_bytes())
    raw[-1] ^= 1
    entry.write_bytes(raw)
    with pytest.raises(CaseError) as error:
        await instance.call("query_analysis_export_records", arguments())
    assert error.value.code == "artifact_integrity_failed"
    assert len(calls) == 1
    assert not instance.entries and not instance.cursors


@pytest.mark.asyncio
async def test_restart_or_credential_rotation_invalidates_old_cursor(harness):
    instance, api, calls, state, journal = harness
    result = await instance.call("query_analysis_export_records", arguments())
    instance.close()
    rotated = SimpleNamespace(
        state_key=journal.state_key, credential_fingerprint="second-key"
    )
    replacement = ExportStore(api, rotated, state)
    try:
        with pytest.raises(CaseError) as error:
            await replacement.call(
                "query_analysis_export_records", arguments(cursor=result["next_cursor"])
            )
        assert error.value.code == "invalid_cursor"
        assert len(calls) == 1
    finally:
        replacement.close()


def test_discovery_pruning_preserves_all_reachable_schema_constraints():
    """Only unreachable definitions disappear; referenced content stays identical."""
    import json

    from jsonschema import Draft202012Validator

    from folklore_mcp_service.case_tools import contracts

    original_inputs = json.loads(
        (contracts._DATA / "phase1-tool-input-schemas.json").read_text()
    )["tools"]
    original_inputs.update(contracts.DISCOVERY_PACKET["input_schemas"])
    original_inputs[contracts.SOURCE_BROWSE_TOOL] = contracts.SOURCE_BROWSE_PACKET[
        "input_schema"
    ]
    pairs = [
        (original_inputs[name], contracts.INPUT_SCHEMAS[name])
        for name in contracts.TOOLS
    ]
    pairs += [
        (contracts.output_schema(name), contracts.OUTPUT_SCHEMAS[name])
        for name in contracts.TOOLS
    ]
    for original, emitted in pairs:
        Draft202012Validator.check_schema(emitted)
        before = {key: value for key, value in original.items() if key != "$defs"}
        after = {key: value for key, value in emitted.items() if key != "$defs"}
        assert before == after
        for name, definition in emitted.get("$defs", {}).items():
            assert original["$defs"][name] == definition
        # This corpus has no anchors, dynamic references or nested base URI
        # changes that could make an otherwise unreferenced definition visible.
        pending = [original]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                assert (
                    not {
                        "$id",
                        "$anchor",
                        "$dynamicAnchor",
                        "$dynamicRef",
                        "$recursiveRef",
                    }
                    & node.keys()
                )
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
        pending = [emitted]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if "$ref" in node:
                    assert node["$ref"].startswith("#/")
                    target = emitted
                    for segment in node["$ref"][2:].split("/"):
                        target = target[segment.replace("~1", "/").replace("~0", "~")]
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
        # A mixed set catches accidental root or enum/type changes in addition
        # to the structural identity proof above.
        for value in ({}, {"unexpected": 1}, None, [], True, {"analysis_id": AID}):
            assert Draft202012Validator(original).is_valid(
                value
            ) == Draft202012Validator(emitted).is_valid(value)
