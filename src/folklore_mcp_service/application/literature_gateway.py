"""Bounded adapter to the public Folklore literature API."""

import json
from typing import Any

import httpx

from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.literature_contracts import (
    PublicationDetailsResponse,
    PublicVariantLiteratureResponse,
    SearchVariantLiteratureArguments,
)


class LiteratureGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class _DuplicateKey(ValueError):
    pass


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


class LiteratureGateway:
    """Read-only client for public Folklore literature contracts."""

    def __init__(
        self, settings: Settings, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.FOLKLORE_API_BASE_URL,
            timeout=httpx.Timeout(
                connect=settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS,
                read=settings.FOLKLORE_MCP_DEADLINE_SECONDS,
                write=settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS,
                pool=settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS,
            ),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
            trust_env=False,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ready(self) -> bool:
        try:
            response = await self._client.get(
                "/folklore/v1/ready",
                timeout=self._settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS,
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200 or len(response.content) > 65_536:
                return False
            payload = response.json()
            dependencies = payload.get("dependencies")
            return (
                payload.get("status") == "ready"
                and isinstance(dependencies, dict)
                and dependencies.get("public_variant_literature") is True
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def search(
        self, arguments: SearchVariantLiteratureArguments
    ) -> PublicVariantLiteratureResponse:
        try:
            response = await self._client.post(
                "/folklore/v1/literature/search",
                json=arguments.model_dump(mode="json"),
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise LiteratureGatewayError(
                "literature_timeout",
                "Folklore literature search timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise LiteratureGatewayError(
                "literature_unavailable",
                "Folklore literature search is temporarily unavailable.",
                retryable=True,
            ) from exc
        return self._validate(
            response,
            PublicVariantLiteratureResponse,
            message="Folklore literature search returned an invalid response.",
        )

    async def get_publication(self, pmid: str) -> PublicationDetailsResponse:
        try:
            response = await self._client.get(
                f"/folklore/v1/literature/publications/{pmid}",
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise LiteratureGatewayError(
                "literature_timeout",
                "Folklore publication details timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise LiteratureGatewayError(
                "literature_unavailable",
                "Folklore publication details are temporarily unavailable.",
                retryable=True,
            ) from exc
        if response.status_code == 404:
            raise LiteratureGatewayError(
                "publication_not_found",
                "The publication was not found.",
                retryable=False,
            )
        return self._validate(
            response,
            PublicationDetailsResponse,
            message="Folklore publication details returned an invalid response.",
        )

    def _validate(self, response: httpx.Response, model: Any, *, message: str) -> Any:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if (
            response.status_code != 200
            or content_type != "application/json"
            or len(response.content) > self._settings.FOLKLORE_MCP_MAX_RESPONSE_BYTES
        ):
            raise LiteratureGatewayError(
                "invalid_literature_response",
                message,
                retryable=response.status_code >= 500,
            )
        try:
            value = json.loads(response.content, object_pairs_hook=_closed_object)
            return model.model_validate(value)
        except (ValueError, TypeError, _DuplicateKey) as exc:
            raise LiteratureGatewayError(
                "invalid_literature_response", message, retryable=False
            ) from exc
