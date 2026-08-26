#!/usr/bin/env python3
"""Build the reproducible Folklore Clinical Variant Interpretation MCP BRXT."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o100644 << 16


def source_files(integration_dir: Path, repository_dir: Path) -> list[tuple[Path, str]]:
    files = [
        (integration_dir / "manifest.json", "manifest.json"),
        (integration_dir / "README.md", "README.md"),
        (integration_dir / "pyproject.toml", "pyproject.toml"),
        (integration_dir / "uv.lock", "uv.lock"),
        (repository_dir / "LICENSE", "LICENSE"),
        (repository_dir / "NOTICE", "NOTICE"),
    ]
    for directory in ("src", "skills"):
        root = integration_dir / directory
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            ):
                files.append((path, path.relative_to(integration_dir).as_posix()))
    return sorted(files, key=lambda item: item[1])


def build(output: Path) -> str:
    integration_dir = Path(__file__).resolve().parents[1]
    repository_dir = integration_dir.parents[1]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for path, archive_name in source_files(integration_dir, repository_dir):
            info = zipfile.ZipInfo(archive_name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FILE_MODE
            info.create_system = 3
            bundle.writestr(info, path.read_bytes(), compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n"
    )
    return digest


def main() -> None:
    integration_dir = Path(__file__).resolve().parents[1]
    default_output = (
        integration_dir / "dist" / "folklore-clinical-variant-interpretation-mcp.brxt"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()
    digest = build(args.output.resolve())
    print(args.output.resolve())
    print(digest)


if __name__ == "__main__":
    main()
