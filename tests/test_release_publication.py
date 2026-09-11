"""Release publishing must fail closed on drift and preserve existing releases."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_publisher", ROOT / "ops/publish_github_release.py"
)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


def request():
    return json.loads((ROOT / "release-publication/current.json").read_text())


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "1.5.0;echo bad"),
        ("sourceCommit", "main"),
        ("tagObject", "a" * 39),
        ("officialWorkflowRun", True),
        ("notes", "../../private.md"),
        ("asset", "skills/releases/../../private.zip"),
        ("assetSha256", "bad"),
    ],
)
def test_release_request_rejects_unreviewable_values(field, value):
    data = request()
    data[field] = value
    with pytest.raises(ValueError):
        publisher.validate_request(data)


def test_registry_must_match_exact_active_latest_release():
    declared = {
        "name": "server",
        "title": "title",
        "version": "1.5.0",
        "description": "evidence",
        "remotes": [],
    }
    data = {
        "server": declared.copy(),
        "_meta": {
            "io.modelcontextprotocol.registry/official": {
                "status": "active",
                "isLatest": True,
            }
        },
    }
    publisher.validate_registry(data, declared)
    data["server"]["version"] = "1.4.2"
    with pytest.raises(ValueError):
        publisher.validate_registry(data, declared)
    data["server"] = declared.copy()
    data["_meta"]["io.modelcontextprotocol.registry/official"]["isLatest"] = False
    with pytest.raises(ValueError):
        publisher.validate_registry(data, declared)


def test_existing_release_is_not_mutated(monkeypatch, capsys):
    tag = "folklore-mcp-v1.5.0"
    monkeypatch.setattr(publisher, "prepare", lambda _: (tag, b"archive"))
    monkeypatch.setattr(
        publisher,
        "fetch_json",
        lambda *a, **k: {
            "tag_name": tag,
            "draft": False,
            "html_url": "https://github.com/release",
        },
    )
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda *a, **k: pytest.fail("Existing release must not be changed"),
    )
    monkeypatch.setattr("sys.argv", ["publish_github_release.py", "--publish"])
    publisher.main()
    assert "Existing release preserved" in capsys.readouterr().out


def test_new_release_cannot_publish_without_scoped_authority(monkeypatch):
    monkeypatch.setattr(
        publisher, "prepare", lambda _: ("folklore-mcp-v1.5.0", b"archive")
    )
    monkeypatch.setattr(publisher, "fetch_json", lambda *a, **k: None)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["publish_github_release.py", "--publish"])
    with pytest.raises(ValueError, match="scoped GitHub Actions token"):
        publisher.main()


@pytest.fixture
def transport(monkeypatch):
    from unittest.mock import Mock

    opener = Mock()
    sleep = Mock()
    monkeypatch.setattr(publisher, "urlopen", opener)
    monkeypatch.setattr(publisher.time, "sleep", sleep)
    return opener, sleep


def response(body=b'{"ok": true}'):
    from io import BytesIO

    return BytesIO(body)


@pytest.mark.parametrize("during_read", [False, True])
def test_registry_recovers_from_timeout(transport, during_read):
    from unittest.mock import MagicMock

    opener, sleep = transport
    error = TimeoutError("read timed out")
    if during_read:
        failed_response = MagicMock()
        failed_response.__enter__.return_value.read.side_effect = error
        opener.side_effect = [failed_response, response()]
    else:
        opener.side_effect = [error, response()]
    assert publisher.fetch_json(publisher.REGISTRY) == {"ok": True}
    assert opener.call_count == 2
    sleep.assert_called_once_with(2)
    if during_read:
        failed_response.__exit__.assert_called_once()


def test_registry_stops_after_three_retries(transport):
    from unittest.mock import call

    opener, sleep = transport
    opener.side_effect = TimeoutError("read timed out")
    with pytest.raises(TimeoutError):
        publisher.fetch_json(publisher.REGISTRY)
    assert opener.call_count == 4
    assert sleep.call_args_list == [call(2), call(4), call(8)]


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_registry_retries_transient_http_errors(transport, status):
    from urllib.error import HTTPError

    opener, sleep = transport
    body = response(b"temporary")
    opener.side_effect = [
        HTTPError(publisher.REGISTRY, status, "temporary", {}, body),
        response(),
    ]
    assert publisher.fetch_json(publisher.REGISTRY) == {"ok": True}
    assert body.closed
    sleep.assert_called_once_with(2)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_registry_does_not_retry_permanent_http_errors(transport, status):
    from urllib.error import HTTPError

    opener, sleep = transport
    opener.side_effect = HTTPError(publisher.REGISTRY, status, "permanent", {}, None)
    with pytest.raises(HTTPError):
        publisher.fetch_json(publisher.REGISTRY)
    assert opener.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("body", [b"not json", b"x" * 2_097_153])
def test_registry_does_not_retry_invalid_responses(transport, body):
    opener, sleep = transport
    opener.return_value = response(body)
    with pytest.raises(ValueError):
        publisher.fetch_json(publisher.REGISTRY)
    assert opener.call_count == 1
    sleep.assert_not_called()


def test_github_timeout_is_not_retried(transport):
    opener, sleep = transport
    opener.side_effect = TimeoutError("read timed out")
    with pytest.raises(TimeoutError):
        publisher.fetch_json(f"{publisher.API}/actions/runs/1")
    assert opener.call_count == 1
    sleep.assert_not_called()


def test_missing_github_release_remains_optional(transport):
    from urllib.error import HTTPError

    opener, sleep = transport
    url = f"{publisher.API}/releases/tags/example"
    opener.side_effect = HTTPError(url, 404, "missing", {}, None)
    assert publisher.fetch_json(url, missing_ok=True) is None
    sleep.assert_not_called()


@pytest.mark.parametrize("wrapped", [False, True])
def test_registry_retries_connection_reset(transport, wrapped):
    from urllib.error import URLError

    opener, sleep = transport
    error = ConnectionResetError("reset")
    opener.side_effect = [URLError(error) if wrapped else error, response()]
    assert publisher.fetch_json(publisher.REGISTRY) == {"ok": True}
    sleep.assert_called_once_with(2)


def test_certificate_failure_is_not_retried(transport):
    import ssl
    from urllib.error import URLError

    opener, sleep = transport
    opener.side_effect = URLError(ssl.SSLCertVerificationError("invalid certificate"))
    with pytest.raises(URLError):
        publisher.fetch_json(publisher.REGISTRY)
    assert opener.call_count == 1
    sleep.assert_not_called()


def test_exhausted_registry_retries_prevent_publication(transport, monkeypatch):
    opener, _ = transport
    opener.side_effect = TimeoutError("read timed out")
    monkeypatch.setattr(
        publisher, "prepare", lambda _: publisher.fetch_json(publisher.REGISTRY)
    )
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda *a, **k: pytest.fail("Cannot publish after verification failure"),
    )
    monkeypatch.setattr("sys.argv", ["publish_github_release.py", "--publish"])
    with pytest.raises(TimeoutError):
        publisher.main()
    assert opener.call_count == 4


def test_registry_version_mismatch_is_not_retried(transport):
    opener, sleep = transport
    opener.return_value = response(b'{"server": {"version": "1.4.2"}}')
    body = publisher.fetch_json(publisher.REGISTRY)
    with pytest.raises(ValueError, match="does not match"):
        publisher.validate_registry(body, {"version": "1.5.0"})
    assert opener.call_count == 1
    sleep.assert_not_called()
