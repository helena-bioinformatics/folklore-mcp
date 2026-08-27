from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "folklore-clinical-variant-interpretation"


def _frontmatter(text: str) -> dict[str, str]:
    parts = text.split("---", 2)
    assert len(parts) == 3
    assert not parts[0].strip()
    return yaml.safe_load(parts[1])


def test_agent_skill_has_task_selection_metadata() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text()
    metadata = _frontmatter(text)

    assert metadata.keys() == {"name", "description"}
    assert metadata["name"] == "folklore-clinical-variant-interpretation"
    description = metadata["description"]
    for trigger in (
        "pathogenic",
        "VUS",
        "HGVS",
        "rsID",
        "ClinVar",
        "population-frequency",
    ):
        assert trigger in description
    assert "does not mention Folklore" in description


def test_agent_skill_preserves_contract_and_safety() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text()
    for tool in (
        "search_variant_evidence",
        "search_variant_literature",
        "get_publication_details",
        "search_literature_corpus",
    ):
        assert tool in text
    for outcome in (
        "resolved",
        "ambiguous",
        "not_found",
        "invalid",
        "unsupported",
        "temporarily_unavailable",
    ):
        assert f"`{outcome}`" in text
    assert "patient, phenotype, family, segregation or private case data" in text
    assert "not a diagnosis, treatment recommendation" in text
    assert "https://api.helena.bio/folklore/v1/mcp" in text


def test_openai_metadata_declares_the_hosted_dependency() -> None:
    metadata = yaml.safe_load((SKILL_DIR / "agents" / "openai.yaml").read_text())
    assert metadata["policy"]["allow_implicit_invocation"] is True
    dependency = metadata["dependencies"]["tools"][0]
    assert dependency["type"] == "mcp"
    assert dependency["transport"] == "streamable_http"
    assert dependency["url"] == "https://api.helena.bio/folklore/v1/mcp"
