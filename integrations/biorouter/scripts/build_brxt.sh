#!/usr/bin/env bash
set -euo pipefail

integration_dir="$(cd "$(dirname "$0")/.." && pwd)"
repository_dir="$(cd "$integration_dir/../.." && pwd)"
output_dir="$integration_dir/dist"
package_dir="$output_dir/package"
bundle="$output_dir/folklore-clinical-variant-interpretation-mcp.brxt"

rm -rf "$output_dir"
mkdir -p "$package_dir"

cp "$integration_dir/manifest.json" "$package_dir/"
cp "$integration_dir/README.md" "$package_dir/"
cp "$integration_dir/pyproject.toml" "$package_dir/"
cp "$repository_dir/LICENSE" "$package_dir/"
cp "$repository_dir/NOTICE" "$package_dir/"
cp -R "$integration_dir/src" "$package_dir/src"
cp -R "$integration_dir/skills" "$package_dir/skills"

(
  cd "$package_dir"
  zip -qr "$bundle" manifest.json README.md pyproject.toml LICENSE NOTICE src skills \
    -x '*/__pycache__/*' '*.pyc' '.venv/*'
)

rm -rf "$package_dir"
printf '%s\n' "$bundle"
