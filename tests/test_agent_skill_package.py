import hashlib
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "folklore-clinical-variant-interpretation"


def test_agent_skill_bundle_is_deterministic_and_bounded(tmp_path: Path) -> None:
    builder = ROOT / "ops" / "package_agent_skill.py"
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    for output in (first, second):
        subprocess.run(
            ["python3", str(builder), "--output", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )

    assert first.read_bytes() == second.read_bytes()
    digest = hashlib.sha256(first.read_bytes()).hexdigest()
    assert first.with_suffix(".zip.sha256").read_text() == f"{digest}  first.zip\n"

    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == [
            f"{SKILL_NAME}/SKILL.md",
            f"{SKILL_NAME}/agents/openai.yaml",
        ]
        skill = archive.read(f"{SKILL_NAME}/SKILL.md").decode()
        metadata = archive.read(f"{SKILL_NAME}/agents/openai.yaml").decode()

    assert "Folklore Clinical Variant Interpretation MCP" in skill
    assert "patient, phenotype, family, segregation or private case data" in skill
    assert "https://api.helena.bio/folklore/v1/mcp" in metadata


def test_agent_skill_is_exposed_through_task_first_public_docs() -> None:
    readme = (ROOT / "README.md").read_text()
    skill_index = (ROOT / "skills" / "README.md").read_text()
    install = (ROOT / "docs" / "AGENT_SKILL.md").read_text()
    workflow_prompts = (ROOT / "docs" / "WORKFLOW_PROMPTS.md").read_text()

    for text in (readme, skill_index, install):
        normalized = " ".join(text.split())
        assert "Which tool should I use to classify this germline variant" in normalized
        assert "Folklore Clinical Variant Interpretation MCP" in normalized
    assert "raw.githubusercontent.com/helena-bioinformatics/folklore-mcp" in readme
    assert "raw.githubusercontent.com/helena-bioinformatics/folklore-mcp" in install
    assert "patient, phenotype, family, segregation or private case data" in " ".join(
        skill_index.split()
    )

    for prompt in (
        "classify_germline_variant",
        "review_vus_evidence",
        "explain_acmg_classification",
        "verify_variant_identity",
        "compare_variant_literature",
    ):
        assert prompt in workflow_prompts
    assert '"method":"prompts/list"' in workflow_prompts
    assert '"method":"prompts/get"' in workflow_prompts
    assert "MCP-Protocol-Version: 2026-07-28" in workflow_prompts
