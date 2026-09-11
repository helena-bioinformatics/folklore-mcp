"""Bounded transport to the authoritative public gene-disease reference API."""

import asyncio
import json
from typing import Literal

import httpx

from folklore_mcp_service.application.gateway import _closed_object
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.gene_disease_contracts import (
    GeneDiseaseResponse,
)


class GeneDiseaseGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class GeneDiseaseGateway:
    """Relay reference assertions without adding scientific interpretation."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.FOLKLORE_MCP_MAX_CONCURRENT)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.FOLKLORE_API_BASE_URL,
            timeout=httpx.Timeout(
                settings.FOLKLORE_MCP_DEADLINE_SECONDS,
                connect=settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS,
            ),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ready(self) -> bool:
        try:
            async with asyncio.timeout(
                self._settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS
            ):
                async with self._client.stream("GET", "/folklore/v1/ready") as response:
                    if (
                        response.status_code != 200
                        or response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                        != "application/json"
                    ):
                        return False
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 65536:
                            return False
                state = json.loads(body, object_pairs_hook=_closed_object)
                return (
                    isinstance(state, dict)
                    and state.get("status") == "ready"
                    and isinstance(state.get("dependencies"), dict)
                    and state["dependencies"].get("public_gene_disease") is True
                )
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, TimeoutError):
            return False

    async def search(
        self, kind: Literal["genes", "diseases"], payload: dict
    ) -> GeneDiseaseResponse:
        try:
            async with asyncio.timeout(self._settings.FOLKLORE_MCP_DEADLINE_SECONDS):
                async with self._semaphore:
                    return await self._search(kind, payload)
        except TimeoutError as exc:
            raise GeneDiseaseGatewayError(
                "upstream_timeout",
                "Gene-disease reference evidence timed out.",
                retryable=True,
            ) from exc

    async def _search(
        self, kind: Literal["genes", "diseases"], payload: dict
    ) -> GeneDiseaseResponse:
        if kind not in {"genes", "diseases"}:
            raise ValueError("Unknown reference operation")
        headers = {"Accept": "application/json"}
        try:
            # Stream and cap decoded bytes, including when Content-Length is absent.
            async with self._client.stream(
                "POST",
                f"/folklore/v1/gene-disease/{kind}/search",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code in {429, 503, 504}:
                    raise GeneDiseaseGatewayError(
                        "upstream_unavailable",
                        "Gene-disease reference evidence is temporarily unavailable.",
                        retryable=True,
                    )
                if (
                    response.status_code != 200
                    or response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                    != "application/json"
                ):
                    raise ValueError("Unexpected reference response")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._settings.FOLKLORE_MCP_MAX_RESPONSE_BYTES:
                        raise ValueError("Oversized reference response")
            result = GeneDiseaseResponse.model_validate(
                json.loads(body, object_pairs_hook=_closed_object)
            )
            expected_kind = "gene" if kind == "genes" else "disease"
            expected_value = payload[expected_kind].strip()
            expected_match = (
                "exact"
                if expected_kind == "gene"
                or expected_value.upper().startswith("MONDO:")
                else "name_contains"
            )
            if (
                result.query.kind != expected_kind
                or result.query.value.casefold() != expected_value.casefold()
                or result.query.match != expected_match
                or result.pagination.limit != payload.get("limit", 20)
                or result.pagination.offset != payload.get("offset", 0)
            ):
                raise ValueError("Reference response does not match request")
            return result
        except httpx.TimeoutException as exc:
            raise GeneDiseaseGatewayError(
                "upstream_timeout",
                "Gene-disease reference evidence timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise GeneDiseaseGatewayError(
                "upstream_unavailable",
                "Gene-disease reference evidence is temporarily unavailable.",
                retryable=True,
            ) from exc
        except (ValueError, TypeError) as exc:
            raise GeneDiseaseGatewayError(
                "invalid_upstream_response",
                "Gene-disease reference evidence returned an invalid response.",
                retryable=False,
            ) from exc
