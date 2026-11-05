"""Encrypted durable command identity and replay state (CR024)."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import os
import sqlite3
import stat
import threading
import time
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .common import CaseError, json_bytes, parse_json, private_directory

DISK_CAP = 256 * 1024 * 1024
RECOVERY_RESERVE = 8 * 1024 * 1024
PAYLOAD_CAP = 1024 * 1024
COMMAND_RESERVE = PAYLOAD_CAP + 65536
TERMINAL_RETENTION = 30 * 86400


class Journal:
    """A single SQLite writer; ciphertext is bound to row identity and credential."""

    def __init__(self, state_dir: Path, credential: str):
        self.directory = private_directory(Path(state_dir))
        self._lock = threading.RLock()
        self._closed = False
        self._db_path = self.directory / "commands.sqlite3"
        lock_path = self.directory / "journal.lock"
        self._lock_fd = os.open(
            lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        try:
            info = os.fstat(self._lock_fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise CaseError("journal_unreadable")
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (CaseError, OSError):
            os.close(self._lock_fd)
            raise CaseError("journal_in_use") from None
        try:
            key_path = self.directory / "state.key"
            existing = self._db_path.exists() or self._db_path.is_symlink()
            if key_path.exists() or key_path.is_symlink():
                self.state_key = self._read_private(key_path)
                if len(self.state_key) != 32:
                    raise CaseError("journal_unreadable")
            else:
                if existing:
                    raise CaseError("journal_unreadable")
                key = os.urandom(32)
                fd = os.open(
                    key_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
                with os.fdopen(fd, "wb") as handle:
                    handle.write(key)
                    handle.flush()
                    os.fsync(handle.fileno())
                self.state_key = key
                self._sync_directory()
            self._cipher = AESGCM(self.state_key)
            self.credential_fingerprint = hmac.new(
                self.state_key, b"credential:" + credential.encode(), hashlib.sha256
            ).hexdigest()
            if existing:
                self._read_private(self._db_path, read=False)
            for name in ("commands.sqlite3-wal", "commands.sqlite3-shm"):
                sidecar = self.directory / name
                if sidecar.exists() or sidecar.is_symlink():
                    self._read_private(sidecar, read=False)
            if not existing:
                fd = os.open(
                    self._db_path,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
                os.close(fd)
        except Exception:
            os.close(self._lock_fd)
            raise CaseError("journal_unreadable") from None
        try:
            self._connection = sqlite3.connect(
                self._db_path, timeout=5, check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA secure_delete=ON")
            self._connection.execute("PRAGMA busy_timeout=5000")
            page_size = self._connection.execute("PRAGMA page_size").fetchone()[0]
            self._connection.execute(
                "PRAGMA max_page_count="
                + str((DISK_CAP - RECOVERY_RESERVE) // page_size)
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value BLOB NOT NULL)"
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, operation_hash TEXT UNIQUE NOT NULL, "
                "fingerprint TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL, "
                "created REAL NOT NULL, updated REAL NOT NULL, reservation INTEGER NOT NULL, payload BLOB NOT NULL)"
            )
            sentinel = self._connection.execute(
                "SELECT value FROM metadata WHERE name='key-check'"
            ).fetchone()
            if sentinel is None:
                if existing:
                    raise CaseError("journal_unreadable")
                self._connection.execute(
                    "INSERT INTO metadata VALUES ('key-check',?)",
                    (self._encrypt(b"folklore-case-journal-v1", b"key-check"),),
                )
            elif (
                self._decrypt(sentinel["value"], b"key-check")
                != b"folklore-case-journal-v1"
            ):
                raise CaseError("journal_unreadable")
            # Sending is never evidence that a remote request did not commit.
            self._connection.execute(
                "UPDATE commands SET state='uncertain',updated=? WHERE state='sending'",
                (time.time(),),
            )
            self._connection.commit()
            self._checkpoint()
            self._sync_directory()
        except Exception:
            if hasattr(self, "_connection"):
                self._connection.close()
            os.close(self._lock_fd)
            raise CaseError("journal_unreadable") from None

    @staticmethod
    def _read_private(path: Path, *, read: bool = True):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise CaseError("journal_unreadable")
            return handle.read() if read else b""

    def _sync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _encrypt(self, raw: bytes, aad: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._cipher.encrypt(nonce, raw, aad)

    def _decrypt(self, raw: bytes, aad: bytes) -> bytes:
        try:
            return self._cipher.decrypt(raw[:12], raw[12:], aad)
        except Exception:
            raise CaseError("journal_unreadable") from None

    def _aad(self, row):
        return (row["id"] + ":" + row["fingerprint"]).encode()

    def _record(self, row):
        if row is None:
            raise CaseError("operation_not_found")
        if row["fingerprint"] != self.credential_fingerprint:
            raise CaseError("recovery_credential_required")
        try:
            data = parse_json(self._decrypt(row["payload"], self._aad(row)))
        except CaseError:
            raise CaseError("journal_unreadable") from None
        return dict(
            data,
            id=row["id"],
            state=row["state"],
            created=row["created"],
            updated=row["updated"],
        )

    def _size(self):
        return sum(
            p.stat().st_size
            for p in (
                self._db_path,
                self.directory / "commands.sqlite3-wal",
                self.directory / "commands.sqlite3-shm",
            )
            if p.exists()
        )

    def _checkpoint(self):
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for name in ("commands.sqlite3-wal", "commands.sqlite3-shm"):
            path = self.directory / name
            if path.exists():
                self._read_private(path, read=False)

    def _collect(self):
        self._connection.execute(
            "DELETE FROM commands WHERE state IN ('accepted','definitive_failure') AND updated<?",
            (time.time() - TERMINAL_RETENTION,),
        )

    def prepare(self, kind: str, key: str, path: str, body: dict, analysis_id=None):
        data = {
            "kind": kind,
            "key": key,
            "path": path,
            "body": body,
            "analysis_id": analysis_id,
            "response": None,
            "error": None,
        }
        raw = json_bytes(data)
        if len(raw) > PAYLOAD_CAP:
            raise CaseError(
                "journal_full",
                details={"limit_name": "command_payload", "limit": PAYLOAD_CAP},
            )
        operation_hash = hmac.new(
            self.state_key, (kind + ":" + key).encode(), hashlib.sha256
        ).hexdigest()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                existing = self._connection.execute(
                    "SELECT * FROM commands WHERE operation_hash=?", (operation_hash,)
                ).fetchone()
                if existing is not None:
                    result = self._record(existing)
                    if result["path"] != path or json_bytes(
                        result["body"]
                    ) != json_bytes(body):
                        raise CaseError("operation_conflict")
                    self._connection.commit()
                    return result
                self._collect()
                outstanding = self._connection.execute(
                    "SELECT COALESCE(SUM(reservation),0) FROM commands "
                    "WHERE state IN ('prepared','sending','uncertain')"
                ).fetchone()[0]
                if (
                    self._size() + outstanding + COMMAND_RESERVE
                    > DISK_CAP - RECOVERY_RESERVE
                ):
                    raise CaseError("journal_full")
                record_id = str(uuid4())
                now = time.time()
                row = {"id": record_id, "fingerprint": self.credential_fingerprint}
                encrypted = self._encrypt(raw, self._aad(row))
                self._connection.execute(
                    "INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        operation_hash,
                        self.credential_fingerprint,
                        kind,
                        "prepared",
                        now,
                        now,
                        COMMAND_RESERVE,
                        encrypted,
                    ),
                )
                self._connection.commit()
                self._checkpoint()
                self._sync_directory()
                return self.get(record_id)
            except CaseError:
                self._connection.rollback()
                raise
            except (OSError, sqlite3.Error):
                self._connection.rollback()
                raise CaseError("journal_full") from None

    def get(self, record_id):
        with self._lock:
            return self._record(
                self._connection.execute(
                    "SELECT * FROM commands WHERE id=?", (record_id,)
                ).fetchone()
            )

    def _update(self, record_id, state, *, response=None, error=None):
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT * FROM commands WHERE id=?", (record_id,)
                ).fetchone()
                data = self._record(row)
                if state == "sending" and data["state"] == "sending":
                    raise CaseError("command_uncertain", retryable=True)
                if data["state"] == "definitive_failure" or (
                    data["state"] == "accepted" and state != "sending"
                ):
                    self._connection.commit()
                    return data
                data = {
                    k: v
                    for k, v in data.items()
                    if k not in {"id", "state", "created", "updated"}
                }
                if response is not None:
                    data["response"] = response
                if error is not None:
                    data["error"] = error
                raw = json_bytes(data)
                if len(raw) > PAYLOAD_CAP:
                    raise CaseError(
                        "journal_full",
                        details={"limit_name": "command_payload", "limit": PAYLOAD_CAP},
                    )
                if self._size() > DISK_CAP - 65536:
                    raise CaseError("journal_full")
                encrypted = self._encrypt(raw, self._aad(row))
                self._connection.execute(
                    "UPDATE commands SET state=?,updated=?,payload=? WHERE id=?",
                    (state, time.time(), encrypted, record_id),
                )
                self._connection.commit()
                self._checkpoint()
                return self.get(record_id)
            except CaseError:
                self._connection.rollback()
                raise
            except (OSError, sqlite3.Error):
                self._connection.rollback()
                raise CaseError("journal_full") from None

    def sending(self, record_id):
        return self._update(record_id, "sending")

    def uncertain(self, record_id):
        return self._update(record_id, "uncertain")

    def accepted(self, record_id, response):
        return self._update(record_id, "accepted", response=response)

    def definitive_failure(self, record_id, error):
        return self._update(record_id, "definitive_failure", error=error)

    def close(self):
        with self._lock:
            if not self._closed:
                self._connection.commit()
                self._checkpoint()
                self._connection.close()
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                self._closed = True
