#!/usr/bin/env python3
"""Read-only reconciliation of Folklore MCP discovery surfaces.

The script never mutates a registry, directory, runtime, or repository. It compares
bounded public observations with registry/discovery-contract.json and emits a report
that separates release-blocking canonical drift from non-blocking aggregator drift.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = SERVICE_ROOT / "registry" / "discovery-contract.json"
USER_AGENT = "Helena-Folklore-Discovery-Reconciler/1.0"


@dataclass(frozen=True)
class Observation:
    surface: str
    tier: str
    status: str
    observed: dict[str, Any]
    detail: str


JsonFetcher = Callable[..., Any]
TextFetcher = Callable[..., str]


def fetch_json(
    url: str,
    *,
    timeout: float,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    request = Request(
        url, data=body, headers=request_headers, method="POST" if body else "GET"
    )
    for attempt in range(2):
        try:
            with urlopen(  # noqa: S310 - fixed public URLs
                request, timeout=timeout
            ) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                try:
                    retry_after = float(exc.headers.get("Retry-After", "1"))
                except ValueError:
                    retry_after = 1
                time.sleep(min(max(retry_after, 1), 5))
                continue
            raise RuntimeError(f"request failed: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"request failed: {type(exc).__name__}") from exc
    raise RuntimeError("request failed after bounded retry")


def fetch_text(url: str, *, timeout: float) -> str:
    request = Request(url, headers={"Accept": "text/html", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed public URLs
            return response.read(2_000_000).decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"request failed: {type(exc).__name__}") from exc


def _observation(
    surface: str,
    tier: str,
    matches: bool,
    observed: dict[str, Any],
    detail: str,
) -> Observation:
    return Observation(
        surface=surface,
        tier=tier,
        status="in_sync" if matches else "drift",
        observed=observed,
        detail=detail,
    )


def _failed(surface: str, tier: str, exc: Exception) -> Observation:
    return Observation(
        surface=surface,
        tier=tier,
        status="unavailable",
        observed={},
        detail=str(exc),
    )


def _mcp_payload(contract: dict[str, Any], method: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": contract["protocolVersion"],
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "folklore-discovery-reconciler",
                    "version": "1.0",
                },
            }
        },
    }


def _mcp_headers(contract: dict[str, Any], method: str) -> dict[str, str]:
    return {
        "MCP-Protocol-Version": contract["protocolVersion"],
        "Mcp-Method": method,
    }


def reconcile(
    contract: dict[str, Any],
    *,
    timeout: float,
    json_fetcher: JsonFetcher = fetch_json,
    text_fetcher: TextFetcher = fetch_text,
) -> list[Observation]:
    observations: list[Observation] = []

    def capture(surface: str, tier: str, probe: Callable[[], Observation]) -> None:
        try:
            observations.append(probe())
        except (KeyError, IndexError, TypeError, RuntimeError, ValueError) as exc:
            observations.append(_failed(surface, tier, exc))

    def health_probe() -> Observation:
        body = json_fetcher(contract["health"], timeout=timeout)
        observed = {"status": body.get("status"), "service": body.get("service")}
        return _observation(
            "runtime_health",
            "canonical",
            observed["status"] == "healthy",
            observed,
            "Health must report healthy.",
        )

    def readiness_probe() -> Observation:
        body = json_fetcher(contract["readiness"], timeout=timeout)
        dependencies = body.get("dependencies", {})
        observed = {
            "status": body.get("status"),
            "public_variant_search": dependencies.get("public_variant_search"),
            "public_variant_literature": dependencies.get("public_variant_literature"),
        }
        matches = observed == {
            "status": "ready",
            "public_variant_search": True,
            "public_variant_literature": True,
        }
        return _observation(
            "runtime_readiness",
            "canonical",
            matches,
            observed,
            "Both public authorities must be ready.",
        )

    def registry_probe() -> Observation:
        body = json_fetcher(contract["surfaces"]["officialRegistry"], timeout=timeout)
        records = body.get("servers", [])
        record = records[0] if len(records) == 1 else {}
        server = record.get("server", {})
        official = record.get("_meta", {}).get(
            "io.modelcontextprotocol.registry/official", {}
        )
        observed = {
            "count": len(records),
            "name": server.get("name"),
            "title": server.get("title"),
            "version": server.get("version"),
            "description": server.get("description"),
            "isLatest": official.get("isLatest"),
            "status": official.get("status"),
        }
        matches = observed == {
            "count": 1,
            "name": contract["registryName"],
            "title": contract["title"],
            "version": contract["version"],
            "description": contract["description"],
            "isLatest": True,
            "status": "active",
        }
        return _observation(
            "official_registry_latest",
            "canonical",
            matches,
            observed,
            "The version=latest query must return exactly one active canonical record.",
        )

    def server_card_probe() -> Observation:
        body = json_fetcher(contract["serverCard"], timeout=timeout)
        info = body.get("serverInfo", {})
        observed = {
            "name": info.get("name"),
            "title": info.get("title"),
            "version": info.get("version"),
            "description": body.get("description"),
            "endpoint": body.get("transport", {}).get("endpoint"),
            "tools": [tool.get("name") for tool in body.get("tools", [])],
            "resources": [
                resource.get("uri") for resource in body.get("resources", [])
            ],
            "prompts": [prompt.get("name") for prompt in body.get("prompts", [])],
        }
        matches = observed == {
            "name": contract["registryName"],
            "title": contract["title"],
            "version": contract["version"],
            "description": contract["serverCardDescription"],
            "endpoint": contract["endpoint"],
            "tools": contract["tools"],
            "resources": contract["resources"],
            "prompts": contract["prompts"],
        }
        return _observation(
            "server_card",
            "canonical",
            matches,
            observed,
            "The domain Server Card must exactly match the discovery contract.",
        )

    def discover_probe() -> Observation:
        method = "server/discover"
        body = json_fetcher(
            contract["endpoint"],
            timeout=timeout,
            payload=_mcp_payload(contract, method),
            headers=_mcp_headers(contract, method),
        )
        result = body.get("result", {})
        info = result.get("_meta", {}).get("io.modelcontextprotocol/serverInfo", {})
        observed = {
            "title": info.get("title"),
            "version": info.get("version"),
            "supportedVersions": result.get("supportedVersions"),
        }
        matches = observed == {
            "title": contract["title"],
            "version": contract["version"],
            "supportedVersions": [contract["protocolVersion"]],
        }
        return _observation(
            "mcp_server_discover",
            "canonical",
            matches,
            observed,
            "MCP 2026-07-28 uses server/discover; initialize is retired.",
        )

    def tools_probe() -> Observation:
        method = "tools/list"
        body = json_fetcher(
            contract["endpoint"],
            timeout=timeout,
            payload=_mcp_payload(contract, method),
            headers=_mcp_headers(contract, method),
        )
        observed = {
            "tools": [
                tool.get("name") for tool in body.get("result", {}).get("tools", [])
            ]
        }
        return _observation(
            "mcp_tools",
            "canonical",
            observed["tools"] == contract["tools"],
            observed,
            "The live tool catalog must preserve deterministic canonical order.",
        )

    def resources_probe() -> Observation:
        method = "resources/list"
        body = json_fetcher(
            contract["endpoint"],
            timeout=timeout,
            payload=_mcp_payload(contract, method),
            headers=_mcp_headers(contract, method),
        )
        observed = {
            "resources": [
                resource.get("uri")
                for resource in body.get("result", {}).get("resources", [])
            ]
        }
        return _observation(
            "mcp_resources",
            "canonical",
            observed["resources"] == contract["resources"],
            observed,
            "The live resource catalog must match the discovery contract.",
        )

    def prompts_probe() -> Observation:
        method = "prompts/list"
        body = json_fetcher(
            contract["endpoint"],
            timeout=timeout,
            payload=_mcp_payload(contract, method),
            headers=_mcp_headers(contract, method),
        )
        observed = {
            "prompts": [
                prompt.get("name")
                for prompt in body.get("result", {}).get("prompts", [])
            ]
        }
        return _observation(
            "mcp_prompts",
            "canonical",
            observed["prompts"] == contract["prompts"],
            observed,
            "The live prompt catalog must preserve deterministic canonical order.",
        )

    def first_party_text_probe(
        surface: str, key: str, required: list[str]
    ) -> Observation:
        body = text_fetcher(contract["surfaces"][key], timeout=timeout)
        missing = [value for value in required if value not in body]
        return _observation(
            surface,
            "canonical",
            not missing,
            {"missingCanonicalMarkers": missing},
            "The first-party task surface must preserve its exact selection markers.",
        )

    capture("runtime_health", "canonical", health_probe)
    capture("runtime_readiness", "canonical", readiness_probe)
    capture("official_registry_latest", "canonical", registry_probe)
    capture("server_card", "canonical", server_card_probe)
    capture("mcp_server_discover", "canonical", discover_probe)
    capture("mcp_tools", "canonical", tools_probe)
    capture("mcp_resources", "canonical", resources_probe)
    capture("mcp_prompts", "canonical", prompts_probe)
    capture(
        "agent_skill_raw",
        "canonical",
        lambda: first_party_text_probe(
            "agent_skill_raw",
            "agentSkillRaw",
            [
                contract["title"],
                "Trigger even when the user does not mention Folklore",
                "search_variant_evidence",
                "qualified professional review",
            ],
        ),
    )
    capture(
        "agent_task_hub",
        "canonical",
        lambda: first_party_text_probe(
            "agent_task_hub",
            "agentHub",
            [contract["title"], "classify", "ACMG/AMP"],
        ),
    )
    capture(
        "acmg_intent_page",
        "canonical",
        lambda: first_party_text_probe(
            "acmg_intent_page",
            "acmgIntent",
            [contract["title"], "ACMG/AMP", "GRCh38"],
        ),
    )

    def html_probe(surface: str, key: str, required: list[str]) -> Observation:
        body = text_fetcher(contract["surfaces"][key], timeout=timeout)
        missing = [value for value in required if value not in body]
        observed = {"missingCanonicalMarkers": missing}
        return _observation(
            surface,
            "aggregator",
            not missing,
            observed,
            "Public HTML is compared by bounded canonical identity markers.",
        )

    capture(
        "glama_connector",
        "aggregator",
        lambda: html_probe(
            "glama_connector", "glamaConnector", [contract["title"], *contract["tools"]]
        ),
    )

    def glama_repository_probe() -> Observation:
        body = json_fetcher(contract["surfaces"]["glamaRepository"], timeout=timeout)
        observed = {
            "title": body.get("name"),
            "tools": [
                tool.get("name")
                for tool in body.get("tools", [])
                if isinstance(tool, dict)
            ],
        }
        matches = observed == {"title": contract["title"], "tools": contract["tools"]}
        return _observation(
            "glama_repository_listing",
            "aggregator",
            matches,
            observed,
            "This repository-derived listing is distinct from the claimed connector.",
        )

    capture("glama_repository_listing", "aggregator", glama_repository_probe)

    def mcp_beat_probe() -> Observation:
        body = text_fetcher(contract["surfaces"]["mcpBeat"], timeout=timeout)
        version = re.search(r'"softwareVersion":"([^"]+)"', body)
        name = re.search(r'"featureList":"[^"]*","name":"([^"]+)"', body)
        observed = {
            "title": name.group(1) if name else None,
            "version": version.group(1) if version else None,
            "toolsPresent": all(tool in body for tool in contract["tools"]),
        }
        matches = observed == {
            "title": contract["title"],
            "version": contract["version"],
            "toolsPresent": True,
        }
        return _observation(
            "mcp_beat",
            "aggregator",
            matches,
            observed,
            "Live tools and cached Registry identity are evaluated independently.",
        )

    capture("mcp_beat", "aggregator", mcp_beat_probe)
    capture(
        "mcpservers_org",
        "aggregator",
        lambda: html_probe("mcpservers_org", "mcpServersOrg", [contract["title"]]),
    )

    def github_submission_probe(
        surface: str,
        key: str,
        required: list[str],
        *,
        include_file_patches: bool = False,
    ) -> Observation:
        url = contract["surfaces"][key]
        body = json_fetcher(url, timeout=timeout)
        combined = f"{body.get('title', '')}\n{body.get('body', '')}"
        if include_file_patches:
            files = json_fetcher(f"{url}/files", timeout=timeout)
            combined = "\n".join(
                [
                    combined,
                    *[
                        file.get("patch", "")
                        for file in files
                        if isinstance(file, dict)
                    ],
                ]
            )
        missing = [value for value in required if value not in combined]
        observed = {"state": body.get("state"), "missingCanonicalMarkers": missing}
        return _observation(
            surface,
            "editorial",
            not missing,
            observed,
            "Editorial state is reported separately from metadata correctness.",
        )

    capture(
        "mcp_so_submission",
        "editorial",
        lambda: github_submission_probe(
            "mcp_so_submission",
            "mcpSoSubmission",
            [contract["title"], contract["version"], *contract["tools"]],
        ),
    )
    capture(
        "awesome_mcp_servers",
        "editorial",
        lambda: github_submission_probe(
            "awesome_mcp_servers",
            "awesomeMcpServers",
            [contract["title"], contract["version"]],
            include_file_patches=True,
        ),
    )
    return observations


def render_text(observations: list[Observation]) -> str:
    lines = []
    for item in observations:
        observed = json.dumps(item.observed, sort_keys=True, separators=(",", ":"))
        lines.append(
            f"{item.status.upper():11} {item.tier:10} {item.surface}: "
            f"{item.detail} observed={observed}"
        )
    return "\n".join(lines)


def exit_code(observations: list[Observation], *, strict_aggregators: bool) -> int:
    if any(
        item.tier == "canonical" and item.status != "in_sync" for item in observations
    ):
        return 2
    if strict_aggregators and any(item.status != "in_sync" for item in observations):
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--strict-aggregators", action="store_true")
    args = parser.parse_args(argv)
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    observations = reconcile(contract, timeout=args.timeout)
    if args.json_output:
        print(
            json.dumps(
                [asdict(item) for item in observations], indent=2, sort_keys=True
            )
        )
    else:
        print(render_text(observations))
    return exit_code(observations, strict_aggregators=args.strict_aggregators)


if __name__ == "__main__":
    sys.exit(main())
