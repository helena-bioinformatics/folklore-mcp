import importlib.util
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
SERVICE = REPOSITORY
SCRIPT = SERVICE / "ops" / "reconcile_discovery.py"
SPEC = importlib.util.spec_from_file_location("reconcile_discovery", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def contract() -> dict:
    return json.loads((SERVICE / "registry" / "discovery-contract.json").read_text())


def canonical_json_fetcher(url, *, timeout, payload=None, headers=None):
    expected = contract()
    del timeout, headers
    if url == expected["health"]:
        return {"status": "healthy", "service": "folklore-mcp-service"}
    if url == expected["readiness"]:
        return {
            "status": "ready",
            "dependencies": {
                "public_variant_search": True,
                "public_variant_literature": True,
            },
        }
    if url == expected["surfaces"]["officialRegistry"]:
        return {
            "servers": [
                {
                    "server": {
                        "name": expected["registryName"],
                        "title": expected["title"],
                        "version": expected["version"],
                        "description": expected["description"],
                    },
                    "_meta": {
                        "io.modelcontextprotocol.registry/official": {
                            "isLatest": True,
                            "status": "active",
                        }
                    },
                }
            ]
        }
    if url == expected["serverCard"]:
        return {
            "serverInfo": {
                "name": expected["registryName"],
                "title": expected["title"],
                "version": expected["version"],
            },
            "description": expected["serverCardDescription"],
            "transport": {"endpoint": expected["endpoint"]},
            "tools": [{"name": name} for name in expected["tools"]],
            "resources": [{"uri": uri} for uri in expected["resources"]],
        }
    if url == expected["endpoint"]:
        method = payload["method"]
        if method == "server/discover":
            return {
                "result": {
                    "supportedVersions": [expected["protocolVersion"]],
                    "_meta": {
                        "io.modelcontextprotocol/serverInfo": {
                            "title": expected["title"],
                            "version": expected["version"],
                        }
                    },
                }
            }
        if method == "tools/list":
            return {"result": {"tools": [{"name": name} for name in expected["tools"]]}}
        if method == "resources/list":
            return {
                "result": {"resources": [{"uri": uri} for uri in expected["resources"]]}
            }
    if url == expected["surfaces"]["glamaRepository"]:
        return {
            "name": expected["title"],
            "tools": [{"name": name} for name in expected["tools"]],
        }
    if url in {
        expected["surfaces"]["mcpSoSubmission"],
        expected["surfaces"]["awesomeMcpServers"],
    }:
        return {
            "title": expected["title"],
            "body": (
                f"{expected['version']} {expected['endpoint']} "
                f"{' '.join(expected['tools'])}"
            ),
            "state": "open",
        }
    if url == f"{expected['surfaces']['awesomeMcpServers']}/files":
        return [
            {
                "filename": "README.md",
                "patch": f"{expected['title']} {expected['version']}",
            }
        ]
    raise AssertionError(f"unexpected URL: {url}")


def canonical_text_fetcher(url, *, timeout):
    expected = contract()
    del timeout
    if url == expected["surfaces"]["mcpBeat"]:
        return (
            f'"featureList":"4 tools","name":"{expected["title"]}",'
            f'"softwareVersion":"{expected["version"]}" ' + " ".join(expected["tools"])
        )
    return f"{expected['title']} {' '.join(expected['tools'])}"


def test_reconciler_accepts_exact_canonical_and_aggregator_state() -> None:
    observations = MODULE.reconcile(
        contract(),
        timeout=1,
        json_fetcher=canonical_json_fetcher,
        text_fetcher=canonical_text_fetcher,
    )
    assert {item.status for item in observations} == {"in_sync"}
    assert MODULE.exit_code(observations, strict_aggregators=True) == 0


def test_reconciler_blocks_canonical_drift_but_not_default_aggregator_drift() -> None:
    expected = contract()

    def stale_json_fetcher(url, **kwargs):
        result = canonical_json_fetcher(url, **kwargs)
        if url == expected["surfaces"]["officialRegistry"]:
            result["servers"][0]["server"]["version"] = "1.1.3"
        if url == expected["surfaces"]["glamaRepository"]:
            return {"name": "Folklore Variant Evidence", "tools": []}
        return result

    observations = MODULE.reconcile(
        expected,
        timeout=1,
        json_fetcher=stale_json_fetcher,
        text_fetcher=canonical_text_fetcher,
    )
    assert (
        next(
            item for item in observations if item.surface == "official_registry_latest"
        ).status
        == "drift"
    )
    assert (
        next(
            item for item in observations if item.surface == "glama_repository_listing"
        ).status
        == "drift"
    )
    assert MODULE.exit_code(observations, strict_aggregators=False) == 2


def test_reconciler_reports_aggregator_drift_without_failing_default_mode() -> None:
    expected = contract()

    def stale_json_fetcher(url, **kwargs):
        if url == expected["surfaces"]["glamaRepository"]:
            return {"name": "Folklore Variant Evidence", "tools": []}
        return canonical_json_fetcher(url, **kwargs)

    observations = MODULE.reconcile(
        expected,
        timeout=1,
        json_fetcher=stale_json_fetcher,
        text_fetcher=canonical_text_fetcher,
    )
    assert MODULE.exit_code(observations, strict_aggregators=False) == 0
    assert MODULE.exit_code(observations, strict_aggregators=True) == 3
