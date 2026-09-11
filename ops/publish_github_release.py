"""Publish a checked-in release request only after verifying immutable public evidence."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "helena-bioinformatics/folklore-mcp"
API = f"https://api.github.com/repos/{REPOSITORY}"
REGISTRY = "https://registry.modelcontextprotocol.io/v0.1/servers/io.github.helena-bioinformatics%2Ffolklore/versions/latest"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def validate_request(request: dict) -> str:
    expected = {
        "version",
        "sourceCommit",
        "tagObject",
        "officialWorkflowRun",
        "notes",
        "asset",
        "assetSha256",
    }
    if set(request) != expected:
        raise ValueError("Release request fields differ from the closed contract")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", request["version"]):
        raise ValueError("Invalid release version")
    for field, size in (("sourceCommit", 40), ("tagObject", 40), ("assetSha256", 64)):
        if not re.fullmatch(rf"[0-9a-f]{{{size}}}", request[field]):
            raise ValueError(f"Invalid {field}")
    if (
        type(request["officialWorkflowRun"]) is not int
        or request["officialWorkflowRun"] <= 0
    ):
        raise ValueError("Invalid official workflow run")
    if request["notes"] != f"release-publication/{request['version']}.md":
        raise ValueError("Release notes must be the version-owned checked-in path")
    if not re.fullmatch(
        r"skills/releases/[0-9]+\.[0-9]+\.[0-9]+/folklore-clinical-variant-interpretation-[0-9]+\.[0-9]+\.[0-9]+\.zip",
        request["asset"],
    ):
        raise ValueError("Asset must be a versioned companion skill archive")
    return f"folklore-mcp-v{request['version']}"


def fetch_json(url: str, *, missing_ok: bool = False) -> dict | None:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Folklore-Release-Publisher/1.0",
    }
    if url.startswith(API + "/") and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:  # noqa: S310 - fixed public API roots
            body = response.read(2_097_153)
            if len(body) > 2_097_152:
                raise ValueError("Oversized release verification response")
            return json.loads(body)
    except HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        raise


def validate_registry(body: dict, declared: dict) -> None:
    official = body.get("_meta", {}).get(
        "io.modelcontextprotocol.registry/official", {}
    )
    observed = body.get("server", {})
    if any(
        observed.get(key) != declared.get(key)
        for key in ("name", "title", "version", "description", "remotes")
    ):
        raise ValueError("Official Registry does not match the tagged public server")
    if official.get("isLatest") is not True or official.get("status") != "active":
        raise ValueError("Official Registry version is not active and latest")


def prepare(request: dict) -> tuple[str, bytes]:
    tag = validate_request(request)
    if git("rev-parse", f"refs/tags/{tag}").decode().strip() != request["tagObject"]:
        raise ValueError(
            "Annotated tag object differs from the reviewed release request"
        )
    if (
        git("rev-parse", f"refs/tags/{tag}^{{commit}}").decode().strip()
        != request["sourceCommit"]
    ):
        raise ValueError("Tag does not resolve to the reviewed source commit")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", request["sourceCommit"], "HEAD"],
        cwd=ROOT,
        check=True,
    )
    declared = json.loads(git("show", f"{tag}:registry/server.json"))
    if declared["version"] != request["version"]:
        raise ValueError("Tagged server version mismatch")
    if not (ROOT / request["notes"]).is_file():
        raise ValueError("Checked-in release notes missing")
    asset = git("show", f"{tag}:{request['asset']}")
    if hashlib.sha256(asset).hexdigest() != request["assetSha256"]:
        raise ValueError("Tagged skill archive checksum mismatch")
    checksum = git("show", f"{tag}:{request['asset']}.sha256").decode()
    if checksum != f"{request['assetSha256']}  {Path(request['asset']).name}\n":
        raise ValueError("Tagged checksum file does not match archive")
    run = fetch_json(f"{API}/actions/runs/{request['officialWorkflowRun']}")
    if not isinstance(run, dict) or any(
        run.get(key) != expected
        for key, expected in {
            "head_sha": request["sourceCommit"],
            "head_branch": tag,
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/publish-official-mcp-registry.yml",
        }.items()
    ):
        raise ValueError(
            "Official Registry workflow did not succeed for this exact tag"
        )
    registry = fetch_json(REGISTRY)
    if not isinstance(registry, dict):
        raise ValueError("Official Registry response missing")
    validate_registry(registry, declared)
    return tag, asset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    request = json.loads((ROOT / "release-publication/current.json").read_text())
    tag, asset = prepare(request)
    existing = fetch_json(f"{API}/releases/tags/{tag}", missing_ok=True)
    if existing is not None:
        if existing.get("tag_name") != tag or existing.get("draft") is not False:
            raise ValueError("Existing release needs operator review")
        print(f"Existing release preserved: {existing['html_url']}")
        return
    if args.prepare_only:
        print(f"Verified immutable {tag}; ready for first GitHub Release publication")
        return
    if not os.environ.get("GH_TOKEN"):
        raise ValueError("Publication requires the scoped GitHub Actions token")
    with tempfile.TemporaryDirectory(prefix="folklore-release-") as directory:
        archive = Path(directory) / Path(request["asset"]).name
        archive.write_bytes(asset)
        checksum = archive.with_suffix(".zip.sha256")
        checksum.write_text(f"{request['assetSha256']}  {archive.name}\n")
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                "--repo",
                REPOSITORY,
                "--verify-tag",
                "--target",
                request["sourceCommit"],
                "--title",
                f"Folklore Clinical Variant Interpretation MCP {request['version']}",
                "--notes-file",
                str(ROOT / request["notes"]),
                str(archive),
                str(checksum),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
