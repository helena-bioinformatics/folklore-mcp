"""Authorized encrypted artifact cache and process-local opaque cursors."""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .common import API_ORIGIN, CaseError, json_bytes, private_directory
from .contracts import EXPORT_PACKET
from .export_worker import run_view

MAX_JSON = 32 * 1024 * 1024
MAX_CACHE = 128 * 1024 * 1024
CACHE_TTL = 300
MAX_CURSORS = 1024


def expiry(value: str) -> float:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.timestamp()
    except (ValueError, TypeError, AttributeError):
        raise CaseError("manifest_invalid") from None


class ExportStore:
    def __init__(self, api, journal, state_dir: Path):
        self.api = api
        self.fingerprint = journal.credential_fingerprint
        self.cipher = AESGCM(journal.state_key)
        self.cache_dir = private_directory(state_dir / "cache")
        self.staging_dir = private_directory(state_dir / "staging")
        self.entries = {}
        self.cursors = {}
        self.lock = asyncio.Lock()
        # Both directories belong exclusively to this executable.
        # A process lock in CaseService excludes another live writer.
        for directory in (self.cache_dir, self.staging_dir):
            for file in directory.iterdir():
                if file.is_file() and not file.is_symlink():
                    file.unlink()
                else:
                    raise CaseError("invalid_state_directory")

    def _remove(self, key):
        entry = self.entries.pop(key, None)
        if entry:
            entry["path"].unlink(missing_ok=True)

    def _sweep(self):
        now = time.time()
        idle = time.monotonic()
        for key, entry in list(self.entries.items()):
            if entry["expires"] <= now or idle - entry["used"] >= CACHE_TTL:
                self._remove(key)
        for key, cursor in list(self.cursors.items()):
            if cursor["expires"] <= now:
                self.cursors.pop(key, None)

    def _identity(self, manifest, artifact):
        return {
            "analysis_id": manifest["analysis_id"],
            "case_id": manifest["case_id"],
            "generation_id": manifest["generation_id"],
            "artifact_id": artifact["artifact_id"],
            "artifact_sha256": artifact["sha256"],
            "manifest_sha256": manifest["manifest_sha256"],
            "source_expires_at": manifest["expires_at"],
            "artifact_size_bytes": artifact["size_bytes"],
        }

    async def _manifest(self, args):
        manifest = await self.api.manifest(args["analysis_id"])
        if manifest["analysis_id"] != args["analysis_id"]:
            raise CaseError("manifest_invalid")
        if expiry(manifest["expires_at"]) <= time.time():
            raise CaseError("source_expired")
        expected = args.get("expected_generation_id")
        if expected is not None and expected != manifest["generation_id"]:
            raise CaseError("generation_conflict")
        artifacts = [item for item in manifest["artifacts"] if item["kind"] == "json"]
        if len(artifacts) != 1:
            raise CaseError("structured_export_unavailable")
        artifact = artifacts[0]
        if artifact["size_bytes"] > MAX_JSON:
            raise CaseError(
                "export_budget_exceeded",
                details={"limit_name": "artifact_bytes", "limit": MAX_JSON},
            )
        return manifest, artifact, self._identity(manifest, artifact)

    def _binding(self, identity):
        return json_bytes(
            {"origin": API_ORIGIN, "credential": self.fingerprint, **identity}
        )

    def _query(self, name, args):
        query = {key: value for key, value in args.items() if key != "cursor"}
        if name in (
            "query_analysis_export_records",
            "get_analysis_export_gene_records",
        ):
            query.setdefault("limit", 25)
            query.setdefault("sort", [])
            query.setdefault(
                "projection",
                EXPORT_PACKET["compact_default_projection"][args["collection"]],
            )
            if name == "query_analysis_export_records":
                query.setdefault("filters", [])
        return json_bytes({"tool": name, "arguments": query})

    def _cursor(self, name, args, binding):
        token = args.get("cursor")
        if token is None:
            return None
        cursor = self.cursors.get(token)
        if cursor is None:
            raise CaseError("invalid_cursor")
        if cursor["binding"] != binding:
            raise CaseError("stale_cursor")
        if cursor["query"] != self._query(name, args):
            raise CaseError("invalid_cursor")
        if cursor["expires"] <= time.time():
            raise CaseError("stale_cursor")
        return cursor["state"]

    def _temporary(self, raw):
        path = self.staging_dir / (uuid.uuid4().hex + ".json")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path

    async def _artifact(self, args, artifact, identity, binding):
        key = hashlib.sha256(binding).hexdigest()
        entry = self.entries.get(key)
        if entry:
            size = entry["path"].stat().st_size
            if size > MAX_JSON + 28:
                self._remove(key)
                raise CaseError("artifact_integrity_failed")
            try:
                encrypted = entry["path"].read_bytes()
                raw = self.cipher.decrypt(encrypted[:12], encrypted[12:], binding)
            except Exception:
                self._remove(key)
                raise CaseError("artifact_integrity_failed") from None
            entry["used"] = time.monotonic()
        else:
            result = await self.api.download(
                args["analysis_id"],
                artifact["artifact_id"],
                self.staging_dir,
                max_bytes=MAX_JSON,
            )
            path = Path(result["local_path"])
            if path.parent != self.staging_dir or path.is_symlink():
                raise CaseError("artifact_integrity_failed")
            try:
                with path.open("rb") as stream:
                    raw = stream.read(MAX_JSON + 1)
            finally:
                path.unlink(missing_ok=True)
            if len(raw) > MAX_JSON:
                raise CaseError(
                    "export_budget_exceeded",
                    details={"limit_name": "artifact_bytes", "limit": MAX_JSON},
                )
            if (
                len(raw) != artifact["size_bytes"]
                or hashlib.sha256(raw).hexdigest() != artifact["sha256"]
            ):
                raise CaseError("artifact_integrity_failed")
            nonce = secrets.token_bytes(12)
            encrypted = nonce + self.cipher.encrypt(nonce, raw, binding)
            while (
                self.entries
                and sum(item["path"].stat().st_size for item in self.entries.values())
                + len(encrypted)
                > MAX_CACHE
            ):
                oldest = min(self.entries, key=lambda item: self.entries[item]["used"])
                self._remove(oldest)
            target = self.cache_dir / (key + ".enc")
            fd = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(encrypted)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            self.entries[key] = {
                "path": target,
                "used": time.monotonic(),
                "expires": expiry(identity["source_expires_at"]),
            }
        if (
            len(raw) != artifact["size_bytes"]
            or hashlib.sha256(raw).hexdigest() != artifact["sha256"]
        ):
            self._remove(key)
            raise CaseError("artifact_integrity_failed")
        return self._temporary(raw)

    async def call(self, name, args):
        async with self.lock:
            self._sweep()
            path = None
            try:
                manifest, artifact, identity = await self._manifest(args)
                binding = self._binding(identity)
                cursor_state = self._cursor(name, args, binding)
                path = await self._artifact(args, artifact, identity, binding)
                result = await run_view(
                    name, args, identity, str(path), EXPORT_PACKET, cursor_state
                )
                # An artifact or key may have expired or been revoked while parsing.
                _, _, current = await self._manifest(args)
                if current != identity:
                    raise CaseError("generation_conflict")
                continuation = result.pop("__cursor_state", None)
                if continuation is not None:
                    if len(self.cursors) >= MAX_CURSORS:
                        oldest = min(
                            self.cursors,
                            key=lambda token: self.cursors[token]["expires"],
                        )
                        self.cursors.pop(oldest, None)
                    token = secrets.token_urlsafe(32)
                    self.cursors[token] = {
                        "binding": binding,
                        "query": self._query(name, args),
                        "state": continuation,
                        "expires": min(
                            time.time() + CACHE_TTL,
                            expiry(identity["source_expires_at"]),
                        ),
                    }
                    result["next_cursor"] = token
                    result["has_more"] = True
                return result
            except BaseException:
                # Fail closed even when admission failed before the artifact lookup.
                for key in list(self.entries):
                    self._remove(key)
                self.cursors.clear()
                raise
            finally:
                if path is not None:
                    path.unlink(missing_ok=True)

    def close(self):
        for key in list(self.entries):
            self._remove(key)
        self.cursors.clear()
        for file in self.staging_dir.iterdir():
            if file.is_file() and not file.is_symlink():
                file.unlink()
