"""Bounded relay to the existing public gene reference authority."""

import asyncio
import json
from typing import Any, Literal
from uuid import uuid4

import httpx

from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.public_gene_contracts import (
    PUBLIC_GENE_ARGUMENTS,
    PUBLIC_GENE_RESPONSES,
    ProfileResponse,
    SectionResponse,
)

PublicGeneOperation = Literal["resolve", "profile", "section", "literature"]


class PublicGeneGatewayError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        available_snapshot_id: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.available_snapshot_id = available_snapshot_id


_ERRORS = {
    (
        409,
        "snapshot_unavailable",
    ): "The reference snapshot changed. Restart with resolve_gene and reload the complete profile.",
    (
        409,
        "gene_withdrawn",
    ): "The requested gene identity is withdrawn. Resolve it and review the returned identity; do not select a replacement automatically.",
    (
        404,
        "gene_not_found",
    ): "The requested HGNC identity has no profile in this public snapshot.",
    (
        400,
        "invalid_gene_cursor",
    ): "The gene section cursor is invalid for this gene and snapshot.",
    (
        400,
        "invalid_gene_literature_cursor",
    ): "The literature cursor is invalid for this gene, snapshot and sort.",
    (
        503,
        "gene_capacity_unavailable",
    ): "The public gene reader is temporarily at capacity.",
    (
        503,
        "gene_snapshot_unavailable",
    ): "The accepted public gene snapshot is temporarily unavailable.",
    (504, "gene_read_timeout"): "The public gene snapshot read timed out.",
    (
        503,
        "gene_literature_capacity_unavailable",
    ): "Gene literature discovery is temporarily at capacity.",
    (
        503,
        "gene_literature_unavailable",
    ): "Gene literature discovery is temporarily unavailable.",
    (504, "gene_literature_timeout"): "Gene literature discovery timed out.",
}


def _closed_json(body: bytes | bytearray) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate upstream JSON key")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("Nonfinite upstream JSON number")

    return json.loads(body, object_pairs_hook=pairs, parse_constant=reject_constant)


class PublicGeneGateway:
    """No source acquisition, biological inference, cache or corpus access."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(settings.FOLKLORE_MCP_MAX_CONCURRENT)
        self._client = client or httpx.AsyncClient(
            base_url=settings.FOLKLORE_API_BASE_URL,
            timeout=httpx.Timeout(
                10.0, connect=settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS
            ),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
        )

    async def ready(self) -> bool:
        """Prove that the existing authority can read its accepted gene snapshot."""
        try:
            async with asyncio.timeout(
                self._settings.FOLKLORE_MCP_CONNECT_TIMEOUT_SECONDS
            ):
                await self.request("resolve", {"query": "HGNC:1"})
            return True
        except (PublicGeneGatewayError, TimeoutError):
            return False

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(self, operation: PublicGeneOperation, arguments: dict) -> dict:
        if operation not in PUBLIC_GENE_ARGUMENTS:
            raise ValueError("Unknown public gene operation")
        validated = PUBLIC_GENE_ARGUMENTS[operation].model_validate(arguments)
        payload = validated.model_dump(mode="json", exclude_none=True)
        payload["request_id"] = str(uuid4())
        headers = {"Accept": "application/json"}
        try:
            async with asyncio.timeout(
                min(10.0, self._settings.FOLKLORE_MCP_DEADLINE_SECONDS)
            ):
                async with self._semaphore:
                    async with self._client.stream(
                        "POST",
                        f"/public/v1/genes/{operation}",
                        json=payload,
                        headers=headers,
                    ) as response:
                        media = (
                            response.headers.get("content-type", "")
                            .split(";", 1)[0]
                            .strip()
                            .lower()
                        )
                        if (
                            media != "application/json"
                            or 300 <= response.status_code < 400
                        ):
                            raise ValueError("Unexpected upstream response")
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if (
                                len(body) + len(chunk)
                                > self._settings.FOLKLORE_MCP_MAX_RESPONSE_BYTES
                            ):
                                raise ValueError("Oversized upstream response")
                            body.extend(chunk)
                        result = _closed_json(body)
                        if response.status_code != 200:
                            self._raise_domain_error(response.status_code, result)
                    model = PUBLIC_GENE_RESPONSES[operation].model_validate(result)
                    if model.request_id != payload["request_id"]:
                        raise ValueError("Upstream request identity mismatch")
                    if operation == "resolve":
                        if model.normalized_query != payload["query"].upper():
                            raise ValueError("Upstream gene query mismatch")
                        if (
                            model.status in {"exact", "alias"}
                            and model.candidates[0].identity.status != "Approved"
                        ):
                            raise ValueError("Resolved gene is not approved")
                        if (
                            model.status == "withdrawn"
                            and model.candidates[0].identity.status == "Approved"
                        ):
                            raise ValueError(
                                "Withdrawn response contains approved identity"
                            )
                    if operation != "resolve":
                        if (
                            model.gene_id != payload["gene_id"]
                            or model.snapshot_id != payload["snapshot_id"]
                        ):
                            raise ValueError("Upstream gene or snapshot mismatch")
                    if isinstance(model, ProfileResponse):
                        if model.identity.status != "Approved":
                            raise ValueError("Withdrawn profile identity")
                        if any(
                            key != source.source_id
                            for key, source in model.sources.items()
                        ):
                            raise ValueError("Source identity mismatch")
                        for section in model.sections.values():
                            self._validate_page(section, 20, None)
                    if isinstance(model, SectionResponse):
                        if model.section != payload["section"]:
                            raise ValueError("Upstream section mismatch")
                        self._validate_page(
                            model, payload["limit"], payload.get("cursor")
                        )
                    if operation == "literature":
                        if (
                            model.returned > payload["limit"]
                            or model.owner_returned_count > payload["limit"]
                        ):
                            raise ValueError("Oversized literature page")
                        if (
                            payload.get("cursor") is not None
                            and model.next_cursor == payload["cursor"]
                        ):
                            raise ValueError("Repeated literature cursor")
                    # Return the original validated object, preserving nulls and field absence.
                    return result
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise PublicGeneGatewayError(
                "upstream_timeout", "Public gene evidence timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise PublicGeneGatewayError(
                "upstream_unavailable",
                "Public gene evidence is temporarily unavailable.",
                retryable=True,
            ) from exc
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise PublicGeneGatewayError(
                "invalid_upstream_response",
                "Public gene evidence returned an invalid response.",
                retryable=False,
            ) from exc

    @staticmethod
    def _validate_page(
        section: SectionResponse, limit: int, cursor: str | None
    ) -> None:
        page = section.pagination
        records = getattr(section.data, "records", None)
        if records is not None:
            if page is None or page.returned != len(records) or page.returned > limit:
                raise ValueError("Section page count mismatch")
            if page.observed_total is None or page.returned > page.observed_total:
                raise ValueError("Section observed count mismatch")
            if page.total is not None and page.total != page.observed_total:
                raise ValueError("Section total mismatch")
            if section.coverage != "complete" and page.total is not None:
                raise ValueError("Partial coverage cannot supply a complete total")
            if page.count_unit != getattr(section.data, "count_unit", None):
                raise ValueError("Section count unit mismatch")
        if page is not None and cursor is not None and page.next_cursor == cursor:
            raise ValueError("Repeated section cursor")

    @staticmethod
    def _raise_domain_error(status_code: int, result: Any) -> None:
        if status_code == 429:
            raise PublicGeneGatewayError(
                "gene_capacity_unavailable",
                "The public gene service is temporarily at capacity.",
                retryable=True,
            )
        if (
            not isinstance(result, dict)
            or set(result) != {"detail"}
            or not isinstance(result["detail"], dict)
        ):
            raise ValueError("Unknown upstream error")
        detail = result["detail"]
        code = detail.get("code")
        if (status_code, code) not in _ERRORS:
            raise ValueError("Unknown upstream error code")
        allowed = (
            {"code", "available_snapshot_id"}
            if code == "snapshot_unavailable"
            else {"code"}
        )
        if not set(detail) <= allowed:
            raise ValueError("Unexpected upstream error fields")
        available = detail.get("available_snapshot_id")
        if available is not None:
            import re

            if not isinstance(available, str) or not re.fullmatch(
                r"[a-f0-9]{64}", available
            ):
                raise ValueError("Invalid replacement snapshot")
        raise PublicGeneGatewayError(
            code,
            _ERRORS[(status_code, code)],
            retryable=status_code in {429, 503, 504},
            available_snapshot_id=available,
        )
