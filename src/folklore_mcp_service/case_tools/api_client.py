"""Bounded first-party Partner Analysis HTTP client (CR024)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from jsonschema import Draft202012Validator, FormatChecker

from . import source_browse
from .common import (
    API_ORIGIN,
    API_PREFIX,
    CaseError,
    json_bytes,
    parse_json,
    private_directory,
)
from .discovery import CASE_TOOLS, validate_records
from .discovery import PACKET as DISCOVERY_PACKET

KEY_PATTERN = re.compile(r"flk_[0-9a-f]{32}\.[A-Za-z0-9_-]{43}")
MAX_API_BYTES = 2 * 1024 * 1024
UUID_PART = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
CASE_PATH = re.compile(API_PREFIX + "/cases/(" + UUID_PART + r")(?:/(analyses))?")
ANALYSIS_PATH = re.compile(
    API_PREFIX + "/analyses/(" + UUID_PART + r")(?:/(results|review|cancel))?"
)
ARTIFACT_PATH = re.compile(
    API_PREFIX + "/analyses/(" + UUID_PART + ")/artifacts/(" + UUID_PART + ")"
)


def identifier(value):
    try:
        if not isinstance(value, str):
            raise ValueError
        return str(UUID(value))
    except ValueError:
        raise CaseError("invalid_input") from None


class ApiClient:
    def __init__(self, api_key: str, *, client=None):
        if not isinstance(api_key, str) or KEY_PATTERN.fullmatch(api_key) is None:
            raise CaseError("credential_type_unverified")
        self._key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=60, write=60, pool=10),
            follow_redirects=False,
            trust_env=False,
        )
        packet = json.loads(
            (Path(__file__).parent / "data" / "phase1-api-schemas.json").read_text()
        )
        self._validators = {}
        for name, value in packet["api_output_structural_contracts"].items():
            if "source_schema" in value:
                self._validators[name] = Draft202012Validator(
                    {"$defs": packet["$defs"], **value["source_schema"]},
                    format_checker=FormatChecker(),
                )

        for name, schema in DISCOVERY_PACKET["api_result_schemas"].items():
            self._validators[name] = Draft202012Validator(
                {"$defs": DISCOVERY_PACKET["$defs"], **schema},
                format_checker=FormatChecker(),
            )

        self._validators[source_browse.TOOL] = Draft202012Validator(
            {
                "$defs": source_browse.PACKET["$defs"],
                **source_browse.PACKET["api_result_schema"],
            },
            format_checker=FormatChecker(),
        )

    async def close(self):
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _route(method, path):
        if method == "GET" and path == API_PREFIX + "/context":
            return "list_analysis_contexts", 200
        if method == "POST" and path == API_PREFIX + "/source-objects":
            return source_browse.TOOL, 200
        if method == "POST" and path == API_PREFIX + "/analyses":
            return "submit_case_analysis", 202
        if method == "GET" and path == API_PREFIX + "/cases":
            return "list_cases", 200
        case = CASE_PATH.fullmatch(path)
        if method == "GET" and case:
            return ("list_case_analyses" if case[2] else "get_case"), 200
        found = ANALYSIS_PATH.fullmatch(path)
        if found:
            suffix = found[2]
            operations = {
                ("GET", None): ("get_case_analysis_status", 200),
                ("GET", "results"): ("get_case_analysis_result_manifest", 200),
                ("POST", "review"): ("acknowledge_sequencing_qc_review", 202),
                ("POST", "cancel"): ("request_sequencing_analysis_cancellation", 202),
            }
            if (method, suffix) in operations:
                return operations[method, suffix]
        raise CaseError("invalid_input", details={"reason": "unsupported_route"})

    @staticmethod
    def _retry_delay(header, attempt=0):
        if header is None:
            return float(attempt + 1)
        try:
            if len(header) > 128:
                return None
            delay = (
                float(header)
                if header.isdigit()
                else (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
            )
            return max(0.0, delay) if math.isfinite(delay) else None
        except (ValueError, TypeError, OverflowError):
            return float(attempt + 1)

    @staticmethod
    async def _wait(delay, waited):
        if delay is None or delay > 30 - waited:
            return None
        started = time.monotonic()
        await asyncio.sleep(delay)
        return waited + max(delay, time.monotonic() - started)

    def _error(self, response, payload):
        request_id = response.headers.get("X-Request-ID")
        error = payload.get("error") if isinstance(payload, dict) else None
        body_id = payload.get("request_id") if isinstance(payload, dict) else None
        if request_id is not None:
            try:
                request_id = identifier(request_id)
            except CaseError:
                raise CaseError("source_contract_mismatch") from None
            if body_id != request_id:
                raise CaseError("source_contract_mismatch")
        elif body_id is not None:
            try:
                request_id = identifier(body_id)
            except CaseError:
                raise CaseError("source_contract_mismatch") from None
        if (
            not isinstance(error, dict)
            or set(error) != {"code", "message", "retryable"}
            or not isinstance(error["code"], str)
            or re.fullmatch(r"[a-z][a-z0-9_]{0,79}", error["code"]) is None
            or not isinstance(error["message"], str)
            or not isinstance(error["retryable"], bool)
        ):
            code = (
                "authorization_failed"
                if response.status_code in {401, 403}
                else "upstream_unavailable"
            )
            return CaseError(
                code, retryable=response.status_code >= 500, request_id=request_id
            )
        # Only the closed technical code and server UUID cross the private error boundary.
        return CaseError(
            error["code"],
            retryable=error["retryable"],
            request_id=request_id,
            details={
                "http_status": response.status_code,
                "definitive_response": request_id is not None,
            },
        )

    @staticmethod
    async def _body(response, limit=MAX_API_BYTES):
        header = response.headers.get("Content-Length")
        if header is not None:
            try:
                if int(header) < 0 or int(header) > limit:
                    raise ValueError
            except ValueError:
                raise CaseError("source_contract_mismatch") from None
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            if len(raw) + len(chunk) > limit:
                raise CaseError("source_contract_mismatch")
            raw.extend(chunk)
        return bytes(raw)

    def _validate(self, name, value):
        try:
            self._validators[name].validate(value)
        except Exception:
            raise CaseError("source_contract_mismatch") from None

    async def request(
        self,
        method,
        relative_path,
        body=None,
        idempotency_key=None,
        expected_status=None,
        params=None,
    ):
        name, status = self._route(method, relative_path)
        if name == source_browse.TOOL:
            from .contracts import validate_input

            if params is not None or idempotency_key is not None:
                raise CaseError("invalid_input")
            body = validate_input(name, body)
        if params is not None:
            if name not in CASE_TOOLS or not isinstance(params, dict):
                raise CaseError("invalid_input")
            allowed = {"context_binding_id"}
            if name == "list_cases":
                allowed.update(("query", "limit", "cursor"))
            elif name == "list_case_analyses":
                allowed.update(("limit", "cursor"))
            if set(params) - allowed:
                raise CaseError("invalid_input")
            from .contracts import validate_input

            values = dict(params)
            if name != "list_cases":
                values["case_id"] = CASE_PATH.fullmatch(relative_path)[1]
            validate_input(name, values)
        elif name in CASE_TOOLS:
            raise CaseError("invalid_input")
        if expected_status is not None and expected_status != status:
            raise CaseError("invalid_input")
        if method == "GET" and body is not None:
            raise CaseError("invalid_input")
        headers = {"Authorization": "Bearer " + self._key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if name == "submit_case_analysis":
            if (
                not isinstance(idempotency_key, str)
                or re.fullmatch(r"[ -~]{1,200}", idempotency_key) is None
            ):
                raise CaseError("invalid_input")
            headers["Idempotency-Key"] = idempotency_key
        content = json_bytes(body) if body is not None else None
        waited = 0.0
        for attempt in range(3 if method == "GET" else 1):
            try:
                async with self._client.stream(
                    method,
                    API_ORIGIN + relative_path,
                    content=content,
                    params=params,
                    headers=headers,
                    follow_redirects=False,
                ) as response:
                    media = (
                        response.headers.get("Content-Type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if (
                        response.status_code in {429, 503}
                        and method == "GET"
                        and name not in CASE_TOOLS
                        and attempt < 2
                    ):
                        delay = self._retry_delay(
                            response.headers.get("Retry-After"), attempt
                        )
                        if delay is not None and delay <= 30 - waited:
                            await response.aclose()
                            waited = await self._wait(delay, waited)
                            if waited is not None:
                                continue
                    raw = await self._body(
                        response,
                        limit=(
                            source_browse.MAX_API_BYTES
                            if name == source_browse.TOOL
                            else 524288
                            if name in CASE_TOOLS
                            else MAX_API_BYTES
                        ),
                    )
                    if media != "application/json":
                        if response.status_code in {401, 403}:
                            raise CaseError("authorization_failed")
                        raise CaseError("source_contract_mismatch")
                    try:
                        value = parse_json(raw)
                    except CaseError:
                        raise CaseError("source_contract_mismatch") from None
                    if response.status_code != status:
                        if 300 <= response.status_code < 400:
                            raise CaseError("source_contract_mismatch")
                        error = self._error(response, value)
                        if (
                            name in CASE_TOOLS
                            and error.retryable
                            and response.status_code in {429, 503}
                            and attempt < 2
                        ):
                            delay = self._retry_delay(
                                response.headers.get("Retry-After"), attempt
                            )
                            if delay is not None and delay <= 30 - waited:
                                await response.aclose()
                                waited = await self._wait(delay, waited)
                                if waited is not None:
                                    continue
                        if response.status_code in {429, 503}:
                            delay = self._retry_delay(
                                response.headers.get("Retry-After"), attempt
                            )
                            if delay is not None and delay <= 9007199254740991:
                                error.details["retry_after_seconds"] = math.ceil(delay)
                        raise error
                    self._validate(name, value)
                    if name not in CASE_TOOLS and name not in {
                        "list_analysis_contexts",
                        "get_case_analysis_result_manifest",
                        source_browse.TOOL,
                    }:
                        aid = value["analysis_id"]
                        root = API_PREFIX + "/analyses/" + aid
                        if (
                            value["links"]["self"] != root
                            or value["links"]["results"] != root + "/results"
                            or value["links"]["folklore"]
                            != "https://folklore.helena.bio/app/analysis/"
                            + value["case_id"]
                        ):
                            raise CaseError("source_contract_mismatch")
                        sequencing = (body or {}).get(
                            "profile"
                        ) == "singleton-sequencing-v1"
                        sequencing = sequencing or any(
                            key in value
                            for key in ("secondary_analysis", "cancellation_requested")
                        )
                        sequencing = sequencing or any(
                            key in value["links"] for key in ("review", "cancel")
                        )
                        if sequencing and (
                            not {
                                "secondary_analysis",
                                "cancellation_requested",
                            }.issubset(value)
                            or value["links"].get("review") != root + "/review"
                            or value["links"].get("cancel") != root + "/cancel"
                        ):
                            raise CaseError("source_contract_mismatch")
                    return value
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if method == "GET" and attempt < 2:
                    remaining = await self._wait(float(attempt + 1), waited)
                    if remaining is not None:
                        waited = remaining
                        continue
                raise CaseError("upstream_unavailable", retryable=True) from None
            except httpx.HTTPError:
                raise CaseError("upstream_unavailable", retryable=True) from None
        raise CaseError("upstream_unavailable", retryable=True)

    async def discovery(self, name, arguments):
        if name not in CASE_TOOLS:
            raise CaseError("invalid_input")
        args = dict(arguments)
        args["context_binding_id"] = identifier(args["context_binding_id"])
        path = API_PREFIX + "/cases"
        if name != "list_cases":
            args["case_id"] = identifier(args["case_id"])
            path += "/" + args["case_id"]
            if name == "list_case_analyses":
                path += "/analyses"
        params = {key: value for key, value in args.items() if key != "case_id"}
        value = await self.request("GET", path, params=params)
        validate_records(name, value, args)
        return value

    async def browse_source_objects(self, arguments):
        from .contracts import validate_input

        args = validate_input(source_browse.TOOL, arguments)
        args["context_binding_id"] = identifier(args["context_binding_id"])
        args["connection_id"] = identifier(args["connection_id"])
        args.setdefault("parent_handle", None)
        args.setdefault("cursor", None)
        args.setdefault("limit", 10)
        try:
            async with asyncio.timeout(source_browse.TOTAL_TIMEOUT):
                value = await self.request(
                    "POST", API_PREFIX + "/source-objects", body=args
                )
        except TimeoutError:
            raise CaseError("upstream_unavailable", retryable=True) from None
        return source_browse.validate_page(value, args)

    async def context(self):
        value = await self.request("GET", API_PREFIX + "/context")
        for item in value["contexts"]:
            if item["actor_kind"] != "machine" or item["user_id"] is not None:
                raise CaseError("credential_type_unverified")
            if any(
                item[field] is None
                for field in ("machine_principal_id", "credential_id", "contract_id")
            ) or (item["billing_arrangement_id"] is None) != (
                item["payer_organization_id"] is None
            ):
                raise CaseError("source_contract_mismatch")
        return value

    async def status(self, analysis_id):
        aid = identifier(analysis_id)
        value = await self.request("GET", API_PREFIX + "/analyses/" + aid)
        if value["analysis_id"] != aid:
            raise CaseError("source_contract_mismatch")
        return value

    async def manifest(self, analysis_id):
        aid = identifier(analysis_id)
        value = await self.request("GET", API_PREFIX + "/analyses/" + aid + "/results")
        try:
            if value["analysis_id"] != aid:
                raise ValueError
            expires = datetime.fromisoformat(value["expires_at"])
            if expires.tzinfo is None or expires <= datetime.now(UTC):
                raise CaseError("source_expired")
            body = {k: v for k, v in value.items() if k != "manifest_sha256"}
            if hashlib.sha256(json_bytes(body)).hexdigest() != value["manifest_sha256"]:
                raise ValueError
            seen = set()
            for item in value["artifacts"]:
                if item["artifact_id"] in seen or item["kind"] in seen:
                    raise ValueError
                seen.update((item["artifact_id"], item["kind"]))
                if (
                    item["download_url"]
                    != API_PREFIX
                    + "/analyses/"
                    + aid
                    + "/artifacts/"
                    + item["artifact_id"]
                    or item["content_type"]
                    != {"json": "application/json", "pdf": "application/pdf"}[
                        item["kind"]
                    ]
                ):
                    raise ValueError
        except CaseError:
            raise
        except (ValueError, KeyError, TypeError):
            raise CaseError("manifest_invalid") from None
        return value

    async def download(
        self, analysis_id, artifact_id, output_dir: Path, max_bytes=128 * 1024 * 1024
    ):
        try:
            async with asyncio.timeout(300):
                return await self._download(
                    analysis_id, artifact_id, output_dir, max_bytes
                )
        except TimeoutError:
            raise CaseError("upstream_unavailable", retryable=True) from None

    async def _download(self, analysis_id, artifact_id, output_dir: Path, max_bytes):
        aid, fid = identifier(analysis_id), identifier(artifact_id)
        manifest = await self.manifest(aid)
        item = next((x for x in manifest["artifacts"] if x["artifact_id"] == fid), None)
        if item is None:
            raise CaseError("artifact_not_found")
        if item["size_bytes"] > max_bytes:
            raise CaseError(
                "export_budget_exceeded",
                details={"limit_name": "download_bytes", "limit": max_bytes},
            )
        directory = private_directory(Path(output_dir))
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        temporary = "." + str(uuid4()) + ".partial"
        target = str(uuid4()) + (".json" if item["kind"] == "json" else ".pdf")
        handle = None
        published = False
        try:
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            handle = os.fdopen(fd, "wb")
            digest, size = hashlib.sha256(), 0
            async with asyncio.timeout(300):
                async with self._client.stream(
                    "GET",
                    API_ORIGIN + item["download_url"],
                    headers={
                        "Authorization": "Bearer " + self._key,
                        "Accept": item["content_type"],
                    },
                    follow_redirects=False,
                ) as response:
                    if response.status_code != 200:
                        try:
                            payload = parse_json(await self._body(response))
                        except CaseError:
                            payload = None
                        raise self._error(response, payload)
                    if (
                        response.headers.get("Content-Type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                        != item["content_type"]
                        or response.headers.get("Content-Encoding", "identity")
                        != "identity"
                    ):
                        raise CaseError("artifact_integrity_failed")
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > min(max_bytes, item["size_bytes"]):
                            raise CaseError("artifact_integrity_failed")
                        digest.update(chunk)
                        handle.write(chunk)
                if size != item["size_bytes"] or digest.hexdigest() != item["sha256"]:
                    raise CaseError("artifact_integrity_failed")
                current = await self.manifest(aid)
                if current != manifest:
                    raise CaseError("generation_conflict")
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
                handle = None
                os.link(
                    temporary,
                    target,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                try:
                    os.unlink(temporary, dir_fd=directory_fd)
                    os.fsync(directory_fd)
                except OSError:
                    os.unlink(target, dir_fd=directory_fd)
                    raise
                published = True
            return {
                "local_path": str(directory / target),
                "analysis_id": aid,
                "case_id": manifest["case_id"],
                "generation_id": manifest["generation_id"],
                "artifact_id": fid,
                "sha256": item["sha256"],
                "size_bytes": size,
                "media_type": item["content_type"],
                "expires_at": manifest["expires_at"],
            }
        except (TimeoutError, httpx.HTTPError):
            raise CaseError("upstream_unavailable", retryable=True) from None
        except OSError:
            raise CaseError("artifact_delivery_failed", retryable=True) from None
        finally:
            if handle is not None:
                handle.close()
            if not published:
                try:
                    os.unlink(temporary, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
            os.close(directory_fd)
