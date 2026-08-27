#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "folklore-clinical-variant-interpretation"
SKILL_DIR = ROOT / "skills" / SKILL_NAME
FILES = (Path("SKILL.md"), Path("agents/openai.yaml"))
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def build(output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in FILES:
            source = SKILL_DIR / relative
            info = ZipInfo(f"{SKILL_NAME}/{relative.as_posix()}", ZIP_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(f"{output.suffix}.sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the portable Folklore Agent Skill bundle."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / f"{SKILL_NAME}.zip",
    )
    args = parser.parse_args()
    digest = build(args.output.resolve())
    print(f"{digest}  {args.output.name}")


if __name__ == "__main__":
    main()
