import pytest
from pydantic import ValidationError

from folklore_mcp_service.config.settings import Settings


def test_environment_scalars_are_decoded_strictly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOLKLORE_MCP_ENABLED", "true")
    monkeypatch.setenv("PORT", "9017")
    monkeypatch.setenv("FOLKLORE_MCP_DEADLINE_SECONDS", "138")
    settings = Settings()
    assert settings.FOLKLORE_MCP_ENABLED is True
    assert settings.PORT == 9017
    assert settings.FOLKLORE_MCP_DEADLINE_SECONDS == 138.0


def test_noncanonical_environment_boolean_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOLKLORE_MCP_ENABLED", "TRUE")
    with pytest.raises(ValidationError):
        Settings()


def test_upstream_authority_is_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(FOLKLORE_API_BASE_URL="https://example.org")
    with pytest.raises(ValidationError):
        Settings(FOLKLORE_API_BASE_URL="http://api.helena.bio")
    with pytest.raises(ValidationError):
        Settings(FOLKLORE_API_BASE_URL="http://localhost:9001/path")

    assert Settings(
        FOLKLORE_API_BASE_URL="http://127.0.0.1:9001"
    ).FOLKLORE_API_BASE_URL == ("http://127.0.0.1:9001")
