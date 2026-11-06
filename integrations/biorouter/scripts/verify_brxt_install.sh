#!/usr/bin/env bash
set -euo pipefail

integration_dir="$(cd "$(dirname "$0")/.." && pwd)"
bundle="${1:-$integration_dir/dist/folklore-clinical-variant-interpretation-mcp.brxt}"
install_dir="$(mktemp -d "${TMPDIR:-/tmp}/folklore-biorouter-install.XXXXXX")"
trap 'rm -rf "$install_dir"' EXIT

python3 - "$bundle" "$install_dir" <<'PY'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as archive:
    archive.extractall(sys.argv[2])
PY

uv sync --frozen --directory "$install_dir"
uv run --frozen --directory "$install_dir" python - "$install_dir/manifest.json" <<'PY'
import json
import sys
from importlib.metadata import version
from pathlib import Path
from folklore_biorouter import __version__
from folklore_biorouter.server import ENDPOINT, SERVER_NAME

manifest = json.loads(Path(sys.argv[1]).read_text())
assert __version__ == manifest["version"] == version(
    "folklore-clinical-variant-interpretation-mcp-biorouter"
)
assert SERVER_NAME == "Folklore Clinical Variant Interpretation MCP"
assert ENDPOINT == "https://api.helena.bio/folklore/v1/mcp"
print(json.dumps({"installed": True, "version": __version__, "server": SERVER_NAME}))
PY
