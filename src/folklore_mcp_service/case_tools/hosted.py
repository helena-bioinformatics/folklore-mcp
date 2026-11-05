"""Hosted case composition. One process owns a private durable namespace root."""

from __future__ import annotations

import asyncio
import copy
import fcntl
import hashlib
import hmac
import os
import re
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import types

from .api_client import KEY_PATTERN, ApiClient, identifier
from .common import API_ORIGIN, API_PREFIX, CaseError, json_bytes, private_directory
from .contracts import (
    DESCRIPTIONS,
    INPUT_SCHEMAS,
    OUTPUT_SCHEMAS,
    TOOLS,
    WRITE_TOOLS,
    validate_input,
)
from .main import CaseService
from .private_logging import protect_transport_logs

MAX_SERVICES = 8
MAX_NAMESPACES = 1024
MAX_DISK_BYTES = 8 * 1024**3
IDLE_SECONDS = 300
AUTHORIZATION_TIMEOUT_SECONDS = 30
# One call can append journal payloads, stage/cache a 32MiB export and download
# a 128MiB original. This conservative reservation is held until cleanup ends.
CALL_DISK_RESERVE = 384 * 1024**2
DOWNLOAD = "download_analysis_result_file"

HOSTED_OUTPUT_SCHEMAS = copy.deepcopy(OUTPUT_SCHEMAS)
_file = HOSTED_OUTPUT_SCHEMAS[DOWNLOAD]["oneOf"][0]["properties"]["data"]["properties"][
    "file"
]
del _file["properties"]["local_path"]
_file["properties"]["download_url"] = {
    "type": "string",
    "pattern": r"^https://api\.helena\.bio/folklore/v1/analyses/[0-9a-f-]{36}/artifacts/[0-9a-f-]{36}$",
}
_file["required"] = [
    "download_url" if x == "local_path" else x for x in _file["required"]
]
_validators = {
    name: Draft202012Validator(schema) for name, schema in HOSTED_OUTPUT_SCHEMAS.items()
}


def hosted_tools():
    """Public metadata contains schemas only, never caller state or credentials."""
    return [
        types.Tool(
            name=name,
            description=(
                "Verify an original result file and return its protected API download URL. Fetch it with the same Bearer API key."
                if name == DOWNLOAD
                else DESCRIPTIONS[name]
            ),
            input_schema=copy.deepcopy(INPUT_SCHEMAS[name]),
            output_schema=copy.deepcopy(HOSTED_OUTPUT_SCHEMAS[name]),
            annotations=types.ToolAnnotations(
                read_only_hint=name not in WRITE_TOOLS,
                destructive_hint=name == "request_sequencing_analysis_cancellation",
                idempotent_hint=True,
                open_world_hint=True,
            ),
        )
        for name in TOOLS
    ]


@dataclass
class _Entry:
    service: CaseService
    used: float
    active: int = 0
    download_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class HostedCaseManager:
    """Keys stay in request/client memory, never in paths, payloads or telemetry.

    Rotation creates a different namespace and does not inherit local recovery.
    Backend stable-principal visibility remains authoritative. Persistent journal
    directories are never deleted by registry eviction or shutdown.
    """

    def __init__(
        self,
        state_dir: Path,
        namespace_secret: bytes,
        *,
        max_services: int = MAX_SERVICES,
        max_namespaces: int = MAX_NAMESPACES,
        max_disk_bytes: int = MAX_DISK_BYTES,
        idle_seconds: float = IDLE_SECONDS,
        service_factory=CaseService,
        api_factory=ApiClient,
        clock=time.monotonic,
    ):
        if not isinstance(namespace_secret, bytes) or len(namespace_secret) != 32:
            raise CaseError("hosted_configuration_invalid")
        if (
            any(
                type(x) is not int or x < 1
                for x in (max_services, max_namespaces, max_disk_bytes)
            )
            or not 1 <= max_services <= max_namespaces <= 8192
            or max_disk_bytes < CALL_DISK_RESERVE
            or not isinstance(idle_seconds, (int, float))
            or isinstance(idle_seconds, bool)
            or not 0 < idle_seconds <= 86400
        ):
            raise CaseError("hosted_configuration_invalid")
        self.root = private_directory(Path(state_dir))
        self._secret = namespace_secret
        self._max_services = max_services
        self._max_namespaces = max_namespaces
        self._max_disk_bytes = max_disk_bytes
        self._idle_seconds = idle_seconds
        self._service_factory = service_factory
        self._api_factory = api_factory
        self._clock = clock
        self._entries: dict[str, _Entry] = {}
        self._condition = asyncio.Condition()
        self._reserved = 0
        self._authorizing = 0
        self._drained = asyncio.Event()
        self._drained.set()
        self._closed = False
        self._close_task = None
        self._lock_fd = os.open(
            self.root / ".hosted.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        try:
            s = os.fstat(self._lock_fd)
            if (
                not stat.S_ISREG(s.st_mode)
                or s.st_uid != os.geteuid()
                or stat.S_IMODE(s.st_mode) != 0o600
                or s.st_nlink != 1
            ):
                raise CaseError("invalid_state_directory")
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise CaseError("hosted_state_in_use") from None
            self._check_secret()
            self._inventory()
        except BaseException:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise
        self._release_transport_logs = protect_transport_logs()

    def _check_secret(self):
        path = self.root / ".namespace-key-check"
        expected = hmac.new(
            self._secret, b"folklore-hosted-namespace-v1", hashlib.sha256
        ).digest()
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            if any(x.is_dir() for x in self.root.iterdir()):
                raise CaseError("hosted_state_unreadable") from None
            fd = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(fd, "wb") as out:
                out.write(expected)
                out.flush()
                os.fsync(out.fileno())
            self._sync(self.root)
            return
        with os.fdopen(fd, "rb") as source:
            s = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(s.st_mode)
                or s.st_uid != os.geteuid()
                or stat.S_IMODE(s.st_mode) != 0o600
                or s.st_nlink != 1
                or source.read(33) != expected
            ):
                raise CaseError("hosted_state_unreadable")

    @staticmethod
    def _sync(path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _inventory(self):
        namespaces = set()
        size = 0
        count = 0
        stack = [self.root]
        while stack:
            directory = stack.pop()
            for path in directory.iterdir():
                count += 1
                if count > 100000:
                    raise CaseError("hosted_capacity_exceeded")
                try:
                    s = path.lstat()
                except FileNotFoundError:
                    continue  # An active call finished removing its own staging file.
                if s.st_uid != os.geteuid() or stat.S_ISLNK(s.st_mode):
                    raise CaseError("hosted_state_unreadable")
                if stat.S_ISDIR(s.st_mode):
                    if stat.S_IMODE(s.st_mode) != 0o700:
                        raise CaseError("hosted_state_unreadable")
                    if directory == self.root:
                        if not re.fullmatch(r"[a-f0-9]{64}", path.name):
                            raise CaseError("hosted_state_unreadable")
                        namespaces.add(path.name)
                    stack.append(path)
                elif stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode) == 0o600:
                    size += max(s.st_size, s.st_blocks * 512)
                else:
                    raise CaseError("hosted_state_unreadable")
        return namespaces, size

    def _namespace(self, key):
        return hmac.new(
            self._secret, b"credential:" + key.encode("ascii"), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or KEY_PATTERN.fullmatch(key) is None:
            raise CaseError("authentication_required")

    async def authorize(self, api_key: str):
        """Current API admission, with no state creation, including catalog requests."""
        return await self._authorize(api_key)

    async def _authorize(self, api_key, *, accepted_call=False):
        self._key(api_key)
        if self._closed and not accepted_call:
            raise CaseError("hosted_service_unavailable", retryable=True)
        if self._authorizing >= self._max_services:
            raise CaseError("hosted_capacity_exceeded", retryable=True)
        self._authorizing += 1
        self._drained.clear()
        api = None
        try:
            api = self._api_factory(api_key)
            try:
                async with asyncio.timeout(AUTHORIZATION_TIMEOUT_SECONDS):
                    return await api.context()
            except TimeoutError:
                raise CaseError("upstream_unavailable", retryable=True) from None
        finally:
            try:
                if api is not None:
                    await self._finish_owned(api.close())
            finally:
                self._authorizing -= 1
                self._mark_drained()

    def _mark_drained(self):
        if self._reserved == 0 and self._authorizing == 0:
            self._drained.set()

    @staticmethod
    async def _finish_owned(awaitable):
        """Finish owned cleanup despite repeat cancellation, then propagate it."""
        task = asyncio.ensure_future(awaitable)
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        result = task.result()
        if cancelled:
            raise asyncio.CancelledError
        return result

    @staticmethod
    def _clear_downloads(directory):
        for temporary in directory.iterdir():
            s = temporary.lstat()
            if (
                stat.S_ISREG(s.st_mode)
                and s.st_uid == os.geteuid()
                and stat.S_IMODE(s.st_mode) == 0o600
                and re.fullmatch(
                    r"(?:[0-9a-f-]{36}\.(?:json|pdf)|\.[0-9a-f-]{36}\.partial)",
                    temporary.name,
                )
            ):
                temporary.unlink(missing_ok=True)
        HostedCaseManager._sync(directory)

    async def _evict(self, namespace):
        entry = self._entries.pop(namespace)
        await self._finish_owned(entry.service.close())

    async def _acquire(self, key):
        namespace = self._namespace(key)
        async with self._condition:
            if self._closed:
                raise CaseError("hosted_service_unavailable", retryable=True)
            now = self._clock()
            for name, entry in list(self._entries.items()):
                if entry.active == 0 and now - entry.used >= self._idle_seconds:
                    await self._evict(name)
            namespaces, size = self._inventory()
            if (
                self._reserved // CALL_DISK_RESERVE >= self._max_services
                or size + self._reserved + CALL_DISK_RESERVE > self._max_disk_bytes
            ):
                raise CaseError("hosted_capacity_exceeded", retryable=True)
            entry = self._entries.get(namespace)
            if entry is None:
                if (
                    namespace not in namespaces
                    and len(namespaces) >= self._max_namespaces
                ):
                    raise CaseError("hosted_capacity_exceeded")
                if len(self._entries) >= self._max_services:
                    idle = [
                        (e.used, n) for n, e in self._entries.items() if e.active == 0
                    ]
                    if not idle:
                        raise CaseError("hosted_capacity_exceeded", retryable=True)
                    _, oldest = min(idle)
                    await self._evict(oldest)
                state = private_directory(self.root / namespace)
                output = private_directory(state / "downloads")
                service = self._service_factory(key, state, output)
                try:
                    # The real Journal lock now proves namespace ownership too.
                    self._clear_downloads(output)
                except BaseException:
                    await self._finish_owned(service.close())
                    raise
                entry = _Entry(service, now)
                self._entries[namespace] = entry
                self._sync(self.root)
            entry.active += 1
            self._reserved += CALL_DISK_RESERVE
            self._drained.clear()
            return namespace, entry

    async def _release(self, namespace, entry):
        async with self._condition:
            entry.active -= 1
            entry.used = self._clock()
            self._reserved -= CALL_DISK_RESERVE
            self._mark_drained()
            self._condition.notify_all()

    async def _download(self, service, args):
        # Separate serialization covers original download, authorization and unlink.
        # CaseService itself owns its scientific/command lock.
        try:
            result = await service.call(DOWNLOAD, args)
            envelope = copy.deepcopy(result.structured_content)
            if not envelope.get("ok"):
                return result
            file = envelope["data"]["file"]
            path = Path(file.pop("local_path"))
            if (
                path.parent != service.output_dir
                or path.is_symlink()
                or not path.is_file()
            ):
                raise CaseError("artifact_integrity_failed")
            manifest = await service.api.manifest(identifier(args["analysis_id"]))
            item = next(
                (
                    x
                    for x in manifest["artifacts"]
                    if x["artifact_id"] == args["artifact_id"]
                ),
                None,
            )
            relative = (
                API_PREFIX
                + "/analyses/"
                + identifier(args["analysis_id"])
                + "/artifacts/"
                + identifier(args["artifact_id"])
            )
            if (
                item is None
                or item["download_url"] != relative
                or any(
                    file[k] != str(manifest[k])
                    for k in ("analysis_id", "case_id", "generation_id", "expires_at")
                )
                or file["artifact_id"] != item["artifact_id"]
                or file["sha256"] != item["sha256"]
                or file["size_bytes"] != str(item["size_bytes"])
                or file["media_type"] != item["content_type"]
            ):
                raise CaseError("generation_conflict")
            file["download_url"] = API_ORIGIN + relative
            _validators[DOWNLOAD].validate(envelope)
            result = CaseService._result(DOWNLOAD, envelope)
            link = types.ResourceLink(
                uri=file["download_url"],
                name=file["artifact_id"],
                mime_type=file["media_type"],
            )
            result.content.append(link)
            # _result checked the original envelope; check again after the link.
            from .common import MAX_RESPONSE_BYTES

            if (
                len(
                    json_bytes(
                        result.model_dump(mode="json", by_alias=True, exclude_none=True)
                    )
                )
                > MAX_RESPONSE_BYTES
            ):
                raise CaseError("response_budget_exceeded")
            return result
        finally:
            # This hosted-only output directory contains temporary verified files,
            # including a file published immediately before cancellation. Never
            # follow or remove an unexpected path returned by a failing service.
            self._clear_downloads(service.output_dir)

    async def call(self, api_key: str, name: str, arguments: dict):
        leased = None
        try:
            args = validate_input(name, arguments)
            await self.authorize(api_key)
            leased = await self._acquire(api_key)
            _, entry = leased
            if name == DOWNLOAD:
                async with entry.download_lock:
                    result = await self._download(entry.service, args)
            else:
                result = await entry.service.call(name, args)
            # Admission may change while queued behind the service lock or while
            # a command replay reconciles. Never disclose a stale successful DTO.
            await self._authorize(api_key, accepted_call=True)
            _validators[name].validate(result.structured_content)
            return result
        except CaseError as error:
            return CaseService._result(name, CaseService._error(error))
        except Exception:
            return CaseService._result(
                name, CaseService._error(CaseError("internal_error"))
            )
        finally:
            if leased is not None:
                await self._finish_owned(self._release(*leased))

    async def close(self):
        self._closed = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown())
        await self._finish_owned(self._close_task)

    async def _shutdown(self):
        await self._drained.wait()
        async with self._condition:
            try:
                failure = None
                for namespace in list(self._entries):
                    try:
                        await self._evict(namespace)
                    except Exception as error:
                        failure = error
                if failure is not None:
                    raise failure
            finally:
                if self._lock_fd is not None:
                    os.close(self._lock_fd)
                    self._lock_fd = None
                self._release_transport_logs()
