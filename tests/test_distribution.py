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
        "Germline ACMG/AMP classification, genes, disease associations, literature and API-key case analysis."
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
        "Germline ACMG/AMP classification, genes, disease associations, literature and API-key case analysis."
    )
    assert contract["version"] == record["version"] == MCP_ADAPTER_VERSION
    assert contract["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert contract["tools"] == [
        MCP_TOOL_NAME,
        MCP_LITERATURE_TOOL_NAME,
        MCP_PUBLICATION_DETAILS_TOOL_NAME,
        MCP_CORPUS_SEARCH_TOOL_NAME,
        MCP_SUPPORT_TOOL_NAME,
        "get_gene_disease_associations",
        "search_disease_genes",
        "resolve_gene",
        "get_gene_profile",
        "get_gene_section",
        "search_gene_literature",
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
        "get_gene_disease_associations",
        "search_disease_genes",
        "resolve_gene",
        "get_gene_profile",
        "get_gene_section",
        "search_gene_literature",
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
    assert manifest["version"] == "2.0.0"
    assert manifest["tools_count"] == 11
    assert manifest["env_vars"] == []
    assert project["project"]["version"] == manifest["version"]
    assert project["project"]["dependencies"] == [
        "fastmcp==3.4.10",
        "certifi>=2026.10.19",
        "mcp>=1.30.0,<2",
    ]
    assert "Ambiguous candidates are never selected automatically" in skill
    assert "classify_germline_variant" in skill
    assert "snapshot" in skill
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
        assert bundle.testzip() is None
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
        project = tomllib.loads(bundle.read("pyproject.toml").decode())["project"]
        lock = tomllib.loads(bundle.read("uv.lock").decode())
        package = next(
            item for item in lock["package"] if item["name"] == project["name"]
        )
        assert manifest["version"] == project["version"] == package["version"]
        assert manifest["entry_point"] in project["scripts"]
    assert "manifest.json" in names
    assert "uv.lock" in names
    assert "src/folklore_biorouter/server.py" in names
    assert "skills/folklore-clinical-variant-interpretation-mcp/SKILL.md" in names
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)


def test_release_candidate_versions_and_dois_are_consistent() -> None:
    package = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())
    published = json.loads(
        (REPOSITORY / "release-publication/current.json").read_text()
    )
    assert (
        package["project"]["version"] == MCP_ADAPTER_VERSION == __version__ == "2.0.0"
    )
    zenodo = json.loads((REPOSITORY / ".zenodo.json").read_text())
    citation = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text())
    assert zenodo["version"] == citation["version"] == MCP_ADAPTER_VERSION
    assert published["sourceCommit"] == "82e4f3802a908166424530f0989a7f7e20222ecb"
    assert published["tagObject"] == "06aa31b9d738df1e15114668c950cc8cd8a0bdda"
    assert published["officialWorkflowRun"] == 42128335960
    assert published["notes"] == "release-publication/2.0.0.md"
    asset = REPOSITORY / published["asset"]
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == published["assetSha256"]
    assert (
        published["assetSha256"]
        == "22e1d9ce2cb323344a99f68f26af8e65bcf136813961b6d4d5a8f3233fa0f4b9"
    )
    assert citation["doi"] == "10.5281/zenodo.23991190"
    assert str(citation["date-released"]) == "2026-11-05"
    assert citation["doi"] in (REPOSITORY / "README.md").read_text()
    historical = yaml.safe_load(
        (REPOSITORY / "archive/citations/CITATION-1.7.0.cff").read_text()
    )
    assert historical["doi"] == "10.5281/zenodo.23849196"
    assert (
        str(historical["date-released"]) == "2026-10-31"
    )  # Actual GitHub release UTC date.
    old_citation_bytes = (
        REPOSITORY / "archive/citations/CITATION-1.6.0.cff"
    ).read_bytes()
    assert (
        hashlib.sha256(old_citation_bytes).hexdigest()
        == "18942410e8d6349367e9b4fe18a3ca66d72cd81ed23251538d7ee0dc4daa35e0"
    )
    archived = yaml.safe_load(old_citation_bytes)
    previous = json.loads(
        (REPOSITORY / "archive/publication-records/current-1.6.0.json").read_text()
    )
    assert archived["version"] == previous["version"] == "1.6.0"
    assert archived["doi"] == "10.5281/zenodo.23817704"
    assert "2.0.0" in (REPOSITORY / "README.md").read_text()
    assert published["version"] == MCP_ADAPTER_VERSION == "2.0.0"
    historical_publication = json.loads(
        (REPOSITORY / "archive/publication-records/current-1.7.0.json").read_text()
    )
    assert historical_publication["version"] == "1.7.0"
    assert (
        historical_publication["sourceCommit"]
        == "5eb6d77bce88a140418872ec19739459ec50cf8f"
    )
    assert (
        historical_publication["tagObject"]
        == "64dbbc7382f83f900647af46f6a82e4ef088009c"
    )
    assert historical_publication["officialWorkflowRun"] == 41252550340


def test_public_benchmark_manifest_is_bounded_and_citable() -> None:
    benchmark = REPOSITORY / "benchmarks" / "variant-interpretation"
    manifest = json.loads((benchmark / "benchmark-manifest.json").read_text())
    method = (benchmark / "COMPARISON_METHOD.md").read_text()
    citation = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text())

    assert manifest["server"] == "Folklore Clinical Variant Interpretation MCP"
    # The preregistered benchmark retains its original release pin.
    assert manifest["adapter_release"] == "1.7.0"
    assert manifest["endpoint"] == "https://api.helena.bio/folklore/v1/mcp"
    assert manifest["case_set"] == "cases.csv"
    assert manifest["capture_harness"] == "capture_folklore.py"
    assert manifest["input_scope"]["assembly"] == "GRCh38"
    assert "identity" in json.dumps(manifest).lower()
    assert "curated reference set" in method
    reference_urls = {reference["url"] for reference in citation["references"]}
    assert any(
        url.endswith("benchmarks/variant-interpretation") for url in reference_urls
    )
    assert any(url.endswith("COMPARISON_METHOD.md") for url in reference_urls)


def test_preregistered_protocol_fixes_public_source_and_review_gate() -> None:
    benchmark = REPOSITORY / "benchmarks" / "variant-interpretation"
    protocol = (benchmark / "PREREGISTRATION.md").read_text()
    template = json.loads((benchmark / "dataset-manifest.template.json").read_text())
    assert "identity resolution" in protocol
    assert "ClinVar supplies dated submitted assertions" in protocol
    assert "prespecified acceptance criteria" in protocol
    assert "adjudication" in protocol
    assert template["assembly"] == "GRCh38"
    assert "structural variant" in template["exclusion"]
    assert "review status" in template["strata"]


def test_public_dx_and_adoption_docs_preserve_scientific_contracts() -> None:
    compatibility = (REPOSITORY / "docs/COMPATIBILITY.md").read_text()
    outcomes = (REPOSITORY / "docs/TYPED_OUTCOMES.md").read_text()
    assert "server/discover" in compatibility
    assert "2026-07-28" in compatibility
    for status in (
        "resolved",
        "ambiguous",
        "not_found",
        "invalid_request",
        "unsupported",
        "resolution_unavailable",
    ):
        assert f"`{status}`" in outcomes
    assert "classify_germline_variant" in (REPOSITORY / "README.md").read_text()
    assert "usage_boundary" not in compatibility


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
    assert "classify_germline_variant" in source_text
    assert "Preserve typed outcomes" in source_text
    assert "official OpenAI Agents SDK" in guide
    assert "resolve_gene" in direct
    assert "snapshot" in direct


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
    dify = REPOSITORY / "integrations/dify"
    with zipfile.ZipFile(
        dify / "dist/folklore-clinical-variant-interpretation-0.2.0.difypkg"
    ) as archive:
        assert archive.read("LICENSE") == (REPOSITORY / "LICENSE").read_bytes()
        assert archive.read("NOTICE") == (REPOSITORY / "NOTICE").read_bytes()
        for name in archive.namelist():
            assert archive.read(name) == (dify / name).read_bytes()

    assert "WORKDIR /build/folklore-mcp" in dockerfile
    assert "COPY src/ ./src/" in dockerfile
    assert "ghcr.io/sparfenyuk/mcp-proxy:v0.12.0" in registry_bridge
    assert "https://api.helena.bio/folklore/v1/mcp" in registry_bridge
