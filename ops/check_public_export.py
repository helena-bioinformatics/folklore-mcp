"""Check the public source tree and an explicitly selected committed delta."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "private_filesystem": re.compile(rb"/(?:root|Users)/[A-Za-z0-9_.-]+"),
    "private_backend_source": re.compile(
        rb"(?:services/(?:session_orchestration|user_management|external_connector)_service|from (?:session_orchestration_service|user_management_service))"
    ),
    "private_key": re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "github_credential": re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"
    ),
    "aws_credential": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "private_runtime": re.compile(
        rb"(?:FLOWLINES_"
        + rb"API_KEY|NOODLE_"
        + rb"TELEMETRY_KEY|helix-"
        + rb"dev-[a-z]|ssh"
        + rb" helena)"
    ),
}


def findings(data: bytes) -> list[str]:
    return [
        name
        for name, pattern in RULES.items()
        if pattern.search(data.replace(b"/root/.local", b"builder-package-prefix"))
    ]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def check(base: str) -> dict:
    git("rev-parse", "--verify", base + "^{commit}")
    git("merge-base", "--is-ancestor", base, "HEAD")
    tracked = set(git("ls-files", "-z").decode().split("\0")) - {""}
    pending = set(
        git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
    ) - {""}
    paths = sorted(
        path
        for path in tracked | pending
        if not any(
            part.startswith(".venv")
            or part in {"__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in Path(path).parts
        )
    )
    errors = []
    checked = 0
    for name in paths:
        file = ROOT / name
        if file.is_symlink():
            errors.append({"path": name, "rules": ["symlink_not_exported"]})
            continue
        if not file.is_file():
            continue
        checked += 1
        for rule in findings(file.read_bytes()):
            errors.append({"path": name, "rules": [rule]})
    # Scan every newly introduced line in each commit, including material later removed.
    commits = git("rev-list", "--reverse", base + "..HEAD").decode().splitlines()
    for commit in commits:
        patch = git("show", "--format=", "--no-ext-diff", "--unified=0", commit, "--")
        additions = b"\n".join(
            line[1:]
            for line in patch.splitlines()
            if line.startswith(b"+") and not line.startswith(b"+++")
        )
        for rule in findings(additions):
            errors.append({"commit": commit, "rules": [rule]})
    return {
        "status": "FAIL" if errors else "PASS",
        "base": git("rev-parse", base).decode().strip(),
        "head": git("rev-parse", "HEAD").decode().strip(),
        "files_checked": checked,
        "commits_checked": len(commits),
        "tracked_and_pending_source": True,
        "note": "Pattern checks supplement manual allowlist review; they do not prove absence of every secret.",
        "findings": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    try:
        result = check(args.base)
    except (OSError, subprocess.CalledProcessError, ValueError):
        print(json.dumps({"status": "FAIL", "error": "source_scope_unavailable"}))
        return 1
    print(json.dumps(result, indent=2))
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
