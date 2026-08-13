"""Bounded HTTP adapter to the authoritative Folklore variant API."""

import json
from typing import Any

import httpx

from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.contracts import (
    SearchVariantArguments,
    UpstreamContractError,
    validate_upstream_result,
)


class VariantGatewayError(RuntimeError):
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


class VariantGateway:
    """One-way adapter; it contains no scientific interpretation logic."""

    _ALLOWED_STATUSES = {200, 400, 404, 413, 422, 429, 500, 503, 504}

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
            if payload.get("status") != "ready":
                return False
            dependencies = payload.get("dependencies")
            if not isinstance(dependencies, dict):
                return False
            return dependencies.get("public_variant_search") is True
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def search(self, arguments: SearchVariantArguments) -> dict[str, Any]:
        try:
            response = await self._client.post(
                "/public/v1/variants/search",
                json=arguments.model_dump(mode="json"),
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise VariantGatewayError(
                "upstream_timeout",
                "Folklore variant evidence timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise VariantGatewayError(
                "upstream_unavailable",
                "Folklore variant evidence is temporarily unavailable.",
                retryable=True,
            ) from exc

        content_type = (
            response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        length_header = response.headers.get("content-length")
        if length_header and length_header.isdecimal():
            if int(length_header) > self._settings.FOLKLORE_MCP_MAX_RESPONSE_BYTES:
                raise VariantGatewayError(
                    "invalid_upstream_response",
                    "Folklore returned an invalid response.",
                    retryable=False,
                )
        body = response.content
        if (
            response.status_code not in self._ALLOWED_STATUSES
            or content_type != "application/json"
            or len(body) > self._settings.FOLKLORE_MCP_MAX_RESPONSE_BYTES
        ):
            raise VariantGatewayError(
                "invalid_upstream_response",
                "Folklore returned an invalid response.",
                retryable=False,
            )
        try:
            payload = json.loads(body, object_pairs_hook=_closed_object)
            return validate_upstream_result(payload)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            _DuplicateKey,
            UpstreamContractError,
            ValueError,
            TypeError,
        ) as exc:
            raise VariantGatewayError(
                "invalid_upstream_response",
                "Folklore returned an invalid response.",
                retryable=False,
            ) from exc
