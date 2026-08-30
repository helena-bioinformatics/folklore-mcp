import hashlib
import json
import py_compile
import subprocess
import tomllib
import zipfile
from pathlib import Path

import yaml

from folklore_mcp_service import __version__
from folklore_mcp_service.presentation.mcp import (
    MCP_ADAPTER_VERSION,
    MCP_CORPUS_SEARCH_TOOL_NAME,
    MCP_LITERATURE_TOOL_NAME,
    MCP_PROTOCOL_VERSION,
    MCP_PUBLICATION_DETAILS_TOOL_NAME,
    MCP_SUPPORT_TOOL_NAME,
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
    assert record["repository"] == {
        "url": "https://github.com/helena-bioinformatics/folklore-mcp",
        "source": "github",
        "id": "1331454884",
    }
    assert contract["registryName"] == record["name"]
    assert contract["title"] == record["title"]
    assert contract["description"] == record["description"]
    assert contract["serverCardDescription"] == (
        "Classify germline variants under ACMG/AMP with structured evidence, "
        "provenance and literature."
    )
    assert contract["version"] == record["version"] == MCP_ADAPTER_VERSION
    assert contract["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert contract["tools"] == [
        MCP_TOOL_NAME,
        MCP_LITERATURE_TOOL_NAME,
        MCP_PUBLICATION_DETAILS_TOOL_NAME,
        MCP_CORPUS_SEARCH_TOOL_NAME,
        MCP_SUPPORT_TOOL_NAME,
    ]
    assert contract["resources"] == [MCP_UI_RESOURCE_URI]


def test_biomni_recipe_uses_the_hardened_pinned_stdio_bridge() -> None:
    client_configs = json.loads(
        (REPOSITORY / "registry" / "platforms" / "client-configs.json").read_text()
    )
    config_path = REPOSITORY / client_configs["clients"]["biomni"]["config"]
    biomni = yaml.safe_load(config_path.read_text())
    server = biomni["mcp_servers"]["folklore_clinical_variant_interpretation_mcp"]
    command = server["command"]

    assert client_configs["tools"] == [
        MCP_TOOL_NAME,
        MCP_LITERATURE_TOOL_NAME,
        MCP_PUBLICATION_DETAILS_TOOL_NAME,
        MCP_CORPUS_SEARCH_TOOL_NAME,
        MCP_SUPPORT_TOOL_NAME,
    ]
    assert client_configs["clients"]["biomni"]["title"] == (
        "Folklore Clinical Variant Interpretation MCP"
    )
    assert client_configs["clients"]["biomni"]["publisher"] == ("Helena Bioinformatics")
    assert server["enabled"] is True
    assert server["description"].startswith(
        "Folklore Clinical Variant Interpretation MCP by Helena Bioinformatics"
    )
    assert command[:3] == ["docker", "run", "-i"]
    assert "--rm" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert "--user=65532:65532" in command
    assert "ghcr.io/sparfenyuk/mcp-proxy:v0.12.0@sha256:" in command[8]
    assert command[-5:] == [
        "--transport",
        "streamablehttp",
        "--log-level",
        "WARNING",
        "https://api.helena.bio/folklore/v1/mcp",
    ]


def test_biorouter_recipe_preserves_identity_version_and_safety() -> None:
    client_configs = json.loads(
        (REPOSITORY / "registry" / "platforms" / "client-configs.json").read_text()
    )
    biorouter = client_configs["clients"]["biorouter"]
    manifest_path = REPOSITORY / biorouter["manifest"]
    manifest = json.loads(manifest_path.read_text())
    project = tomllib.loads(
        (REPOSITORY / "integrations" / "biorouter" / "pyproject.toml").read_text()
    )
    skill = (
        REPOSITORY
        / "integrations"
        / "biorouter"
        / "skills"
        / "folklore-clinical-variant-interpretation-mcp"
        / "SKILL.md"
    ).read_text()
    server = (
        REPOSITORY
        / "integrations"
        / "biorouter"
        / "src"
        / "folklore_biorouter"
        / "server.py"
    ).read_text()
    cli = (
        REPOSITORY
        / "integrations"
        / "biorouter"
        / "src"
        / "folklore_biorouter"
        / "cli.py"
    ).read_text()

    assert biorouter == {
        "title": "Folklore Clinical Variant Interpretation MCP",
        "publisher": "Helena Bioinformatics",
        "mode": "BRXT stdio bridge to hosted Streamable HTTP",
        "authentication": "none",
        "manifest": "integrations/biorouter/manifest.json",
    }
    assert manifest["name"] == "folklore-clinical-variant-interpretation-mcp"
    assert manifest["display_name"] == "Folklore Clinical Variant Interpretation MCP"
    assert manifest["version"] == MCP_ADAPTER_VERSION == "1.4.1"
    assert manifest["tools_count"] == 5
    assert manifest["env_vars"] == []
    assert project["project"]["version"] == MCP_ADAPTER_VERSION
    assert project["project"]["dependencies"] == ["fastmcp==3.4.2"]
    assert "Ambiguous candidates are never selected automatically" in skill
    assert "patient, phenotype, family, segregation" in skill
    assert "qualified professional review" in skill
    assert 'ENDPOINT = "https://api.helena.bio/folklore/v1/mcp"' in server
    assert "create_proxy" in server
    assert 'transport="stdio"' in cli


def test_biorouter_brxt_contains_only_the_public_bridge_assets(tmp_path: Path) -> None:
    source = REPOSITORY / "integrations" / "biorouter"
    first = tmp_path / "first.brxt"
    second = tmp_path / "second.brxt"
    builder = source / "scripts" / "build_brxt.py"
    subprocess.run(
        ["python3", str(builder), "--output", str(first)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["python3", str(builder), "--output", str(second)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert first.read_bytes() == second.read_bytes()
    digest = hashlib.sha256(first.read_bytes()).hexdigest()
    assert first.with_suffix(".brxt.sha256").read_text() == f"{digest}  first.brxt\n"
    with zipfile.ZipFile(first) as bundle:
        names = set(bundle.namelist())
    assert "manifest.json" in names
    assert "uv.lock" in names
    assert "src/folklore_biorouter/server.py" in names
    assert "skills/folklore-clinical-variant-interpretation-mcp/SKILL.md" in names
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)


def test_release_candidate_versions_and_dois_are_consistent() -> None:
    package = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())
    zenodo = json.loads((REPOSITORY / ".zenodo.json").read_text())
    citation = (REPOSITORY / "CITATION.cff").read_text()
    readme = (REPOSITORY / "README.md").read_text()

    assert package["project"]["version"] == MCP_ADAPTER_VERSION == __version__
    assert zenodo["version"] == MCP_ADAPTER_VERSION
    assert f"version: {MCP_ADAPTER_VERSION}" in citation
    assert "doi: 10.5281/zenodo.21922951" in citation
    assert "Current release: `1.4.1`" in readme
    assert "Latest published Registry version: `1.4.1`" in readme
    assert "prior 1.3.3 archive remains available" in readme
    assert "10.5281/zenodo.22102783" in readme


def test_public_benchmark_manifest_is_bounded_and_citable() -> None:
    benchmark = REPOSITORY / "benchmarks" / "variant-interpretation"
    manifest = json.loads((benchmark / "benchmark-manifest.json").read_text())
    method = (benchmark / "COMPARISON_METHOD.md").read_text()
    citation = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text())

    assert manifest["server"] == "Folklore Clinical Variant Interpretation MCP"
    assert manifest["adapter_release"] == MCP_ADAPTER_VERSION
    assert manifest["endpoint"] == "https://api.helena.bio/folklore/v1/mcp"
    assert manifest["case_set"] == "cases.csv"
    assert manifest["capture_harness"] == "capture_folklore.py"
    assert "patient data" in manifest["input_scope"]["excluded"]
    assert "Concordance is not accuracy." in manifest["interpretation_limits"]
    assert "independent validation" in method
    assert "Do not add patient, phenotype, family, segregation" in method
    reference_urls = {reference["url"] for reference in citation["references"]}
    assert any(
        url.endswith("benchmarks/variant-interpretation") for url in reference_urls
    )
    assert any(url.endswith("COMPARISON_METHOD.md") for url in reference_urls)


def test_preregistered_protocol_fixes_public_source_and_review_gate() -> None:
    benchmark = REPOSITORY / "benchmarks" / "variant-interpretation"
    protocol = (benchmark / "PREREGISTRATION.md").read_text()
    template = json.loads((benchmark / "dataset-manifest.template.json").read_text())
    assert "No comparative result or superiority claim" in protocol
    assert "ClinVar is an archive of submitted assertions" in protocol
    assert "independent" in protocol
    assert "reviewer" in protocol
    assert template["assembly"] == "GRCh38"
    assert "patient data" in template["exclusion"]
    assert "review status" in template["strata"]


def test_public_dx_and_adoption_docs_preserve_safety_boundaries() -> None:
    compatibility = (REPOSITORY / "docs" / "COMPATIBILITY.md").read_text()
    troubleshooting = (REPOSITORY / "docs" / "TROUBLESHOOTING.md").read_text()
    outcomes = (REPOSITORY / "docs" / "TYPED_OUTCOMES.md").read_text()
    adoption = (REPOSITORY / "docs" / "ADOPTION_MEASUREMENT.md").read_text()
    smoke = REPOSITORY / "ops" / "public_smoke.py"

    assert "server/discover" in compatibility
    assert "patient, phenotype, family, segregation" in compatibility
    assert "Do not select" in troubleshooting
    for status in (
        "resolved",
        "ambiguous",
        "not_found",
        "invalid",
        "unsupported",
        "temporarily_unavailable",
    ):
        assert f"`{status}`" in outcomes
    assert "Variant expressions" in adoption
    assert "IP addresses" in adoption
    assert "Do not infer individuals" in adoption
    py_compile.compile(str(smoke), doraise=True)


def test_openai_agents_and_direct_http_examples_preserve_boundaries(
    tmp_path: Path,
) -> None:
    integration = REPOSITORY / "integrations" / "openai-agents-python"
    source = integration / "main.py"
    guide = (integration / "README.md").read_text()
    direct = (
        REPOSITORY / "integrations" / "direct-streamable-http" / "README.md"
    ).read_text()
    py_compile.compile(source, cfile=str(tmp_path / "main.pyc"), doraise=True)
    source_text = source.read_text()
    assert "https://api.helena.bio/folklore/v1/mcp" in source_text
    assert "create_static_tool_filter" in source_text
    assert "patient, phenotype" in source_text
    assert "qualified professional review" in source_text
    assert "official OpenAI Agents SDK" in guide
    assert "never convert invalid" in direct
    assert "private case data" in direct


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
