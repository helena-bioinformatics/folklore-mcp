import json
import tomllib
from pathlib import Path

from folklore_mcp_service import __version__
from folklore_mcp_service.presentation.mcp import (
    MCP_ADAPTER_VERSION,
    MCP_CORPUS_SEARCH_TOOL_NAME,
    MCP_LITERATURE_TOOL_NAME,
    MCP_PROTOCOL_VERSION,
    MCP_PUBLICATION_DETAILS_TOOL_NAME,
    MCP_TOOL_NAME,
    MCP_UI_RESOURCE_URI,
)

REPOSITORY = Path(__file__).resolve().parents[1]


def test_registry_identity_and_remote_are_exact() -> None:
    record = json.loads((REPOSITORY / "registry" / "server.json").read_text())
    contract = json.loads(
        (REPOSITORY / "registry" / "discovery-contract.json").read_text()
    )
    assert record["name"] == "io.github.helena-bioinformatics/folklore"
    assert record["title"] == "Folklore Clinical Variant Interpretation MCP"
    assert record["description"] == (
        "Helena Bioinformatics MCP for clinical variant interpretation, "
        "ACMG/AMP evidence and literature."
    )
    assert record["remotes"] == [
        {
            "type": "streamable-http",
            "url": "https://api.helena.bio/folklore/v1/mcp",
        }
    ]
    assert contract["registryName"] == record["name"]
    assert contract["title"] == record["title"]
    assert contract["description"] == record["description"]
    assert contract["version"] == record["version"] == MCP_ADAPTER_VERSION
    assert contract["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert contract["tools"] == [
        MCP_TOOL_NAME,
        MCP_LITERATURE_TOOL_NAME,
        MCP_PUBLICATION_DETAILS_TOOL_NAME,
        MCP_CORPUS_SEARCH_TOOL_NAME,
    ]
    assert contract["resources"] == [MCP_UI_RESOURCE_URI]


def test_release_candidate_versions_and_dois_are_consistent() -> None:
    package = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())
    zenodo = json.loads((REPOSITORY / ".zenodo.json").read_text())
    citation = (REPOSITORY / "CITATION.cff").read_text()
    readme = (REPOSITORY / "README.md").read_text()

    assert package["project"]["version"] == MCP_ADAPTER_VERSION == __version__
    assert zenodo["version"] == MCP_ADAPTER_VERSION
    assert f"version: {MCP_ADAPTER_VERSION}" in citation
    assert "doi: 10.5281/zenodo.21922951" in citation
    assert "Current release: `1.3.3`" in readme
    assert "Latest published Registry version: `1.3.3`" in readme
    assert "historical version `1.3.1`" in readme
    assert "10.5281/zenodo.22093164" in readme
    assert "Release `1.3.3` does not have a version DOI yet" in readme


def test_public_tree_has_only_generic_deployment_assets() -> None:
    assert not (REPOSITORY / "ops" / "production-compose.yaml").exists()
    assert not (
        REPOSITORY
        / "src"
        / "folklore_mcp_service"
        / "application"
        / "variant_literature_service.py"
    ).exists()
    settings = (
        REPOSITORY / "src" / "folklore_mcp_service" / "config" / "settings.py"
    ).read_text()
    assert 'FOLKLORE_API_BASE_URL: str = "https://api.helena.bio"' in settings


def test_package_is_apache_licensed_and_standalone() -> None:
    pyproject = (REPOSITORY / "pyproject.toml").read_text()
    dockerfile = (REPOSITORY / "Dockerfile.adapter").read_text()
    registry_bridge = (REPOSITORY / "Dockerfile").read_text()
    assert 'license = "Apache-2.0"' in pyproject
    assert (REPOSITORY / "LICENSE").is_file()
    assert "WORKDIR /build/folklore-mcp" in dockerfile
    assert "COPY src/ ./src/" in dockerfile
    assert "ghcr.io/sparfenyuk/mcp-proxy:v0.12.0" in registry_bridge
    assert "https://api.helena.bio/folklore/v1/mcp" in registry_bridge
