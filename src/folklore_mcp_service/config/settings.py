"""Strict environment-backed settings for the Folklore MCP adapter."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, StrictBool, StrictFloat, StrictInt, field_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

BOOLEAN_SETTING_NAMES = {"FOLKLORE_MCP_ENABLED", "FOLKLORE_LITERATURE_ENABLED"}
INTEGER_SETTING_NAMES = {
    "PORT",
    "FOLKLORE_MCP_MAX_BODY_BYTES",
    "FOLKLORE_MCP_MAX_RESPONSE_BYTES",
    "FOLKLORE_MCP_MAX_CONCURRENT",
}
FLOAT_SETTING_NAMES = {
    "FOLKLORE_MCP_DEADLINE_SECONDS",
    "FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS",
}


class StrictEnvironmentSource(EnvSettingsSource):
    """Decode environment text before strict scalar validation."""

    def prepare_field_value(
        self,
        field_name: str,
        field: object,
        value: object,
        value_is_complex: bool,
    ) -> object:
        if field_name in BOOLEAN_SETTING_NAMES and isinstance(value, str):
            if value == "true":
                return True
            if value == "false":
                return False
        if (
            field_name in INTEGER_SETTING_NAMES
            and isinstance(value, str)
            and value.isdecimal()
        ):
            return int(value)
        if field_name in FLOAT_SETTING_NAMES and isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        return super().prepare_field_value(
            field_name,
            field,
            value,
            value_is_complex,
        )


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Runtime configuration; the public MCP capability is OFF by default."""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    SERVICE_NAME: Literal["folklore-mcp-service"] = "folklore-mcp-service"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    HOST: str = "0.0.0.0"
    PORT: Annotated[StrictInt, Field(ge=1, le=65_535)] = 9017
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    FOLKLORE_MCP_ENABLED: StrictBool = False
    FOLKLORE_LITERATURE_ENABLED: StrictBool = False
    FOLKLORE_API_BASE_URL: str = "https://api.helena.bio"
    FOLKLORE_MCP_DEADLINE_SECONDS: Annotated[
        StrictFloat, Field(ge=5.0, le=140.0, allow_inf_nan=False)
    ] = 138.0
    FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS: Annotated[
        StrictFloat, Field(ge=0.1, le=10.0, allow_inf_nan=False)
    ] = 2.0
    FOLKLORE_MCP_MAX_BODY_BYTES: Annotated[StrictInt, Field(ge=1024, le=65_536)] = (
        16_384
    )
    FOLKLORE_MCP_MAX_RESPONSE_BYTES: Annotated[
        StrictInt, Field(ge=65_536, le=4_194_304)
    ] = 2_097_152
    FOLKLORE_MCP_MAX_CONCURRENT: Annotated[StrictInt, Field(ge=1, le=32)] = 8
    FOLKLORE_MCP_ALLOWED_ORIGINS: str = (
        "https://claude.ai,"
        "https://chatgpt.com,"
        "https://platform.openai.com,"
        "https://gemini.google.com,"
        "https://perplexity.ai,"
        "https://www.perplexity.ai,"
        "https://grok.com,"
        "https://x.com,"
        "https://copilot.microsoft.com,"
        "https://m365.cloud.microsoft,"
        "https://glama.ai,"
        "https://folklore.helena.bio,"
        "https://helena.bio,"
        "https://www.helena.bio"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Keep constructor values strict while accepting canonical env text."""
        return (
            init_settings,
            StrictEnvironmentSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    @field_validator("HOST")
    @classmethod
    def validate_host(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 255
            or any(ord(ch) < 32 for ch in normalized)
        ):
            raise ValueError("HOST must be bounded printable text")
        return normalized

    @field_validator("FOLKLORE_API_BASE_URL")
    @classmethod
    def validate_upstream_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Folklore API base URL must be one HTTP(S) origin")
        if parsed.hostname not in {"api.helena.bio", "127.0.0.1", "localhost"}:
            raise ValueError("Folklore API host is not approved")
        if parsed.hostname == "api.helena.bio" and parsed.scheme != "https":
            raise ValueError("the hosted Folklore API requires HTTPS")
        return value.strip().rstrip("/")

    @field_validator("FOLKLORE_MCP_ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",") if item.strip()]
        if not origins or len(origins) > 32 or len(origins) != len(set(origins)):
            raise ValueError("MCP allowed origins must be a unique bounded list")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or origin.endswith("/")
            ):
                raise ValueError("each MCP allowed origin must be one HTTPS origin")
        return ",".join(origins)

    @property
    def folklore_mcp_allowed_origin_set(self) -> frozenset[str]:
        return frozenset(self.FOLKLORE_MCP_ALLOWED_ORIGINS.split(","))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
