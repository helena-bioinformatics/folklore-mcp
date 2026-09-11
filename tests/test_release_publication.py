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
