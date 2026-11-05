"""Credential-free spawned process for bounded export views (CR024)."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from contextlib import suppress
from pathlib import Path

from .common import CaseError, json_bytes, parse_json


def _send(message: dict) -> None:
    sys.stdout.buffer.write(json_bytes(message) + b"\n")
    sys.stdout.buffer.flush()


def _child() -> None:
    """Read one private request; the launcher provides a closed environment."""
    try:
        import resource

        from . import export_engine

        raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise CaseError("query_budget_exceeded")
        request = parse_json(raw)
        packet = request["packet"]
        memory = packet["limits"]["worker_memory_bytes"]
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))

        def query_start():
            _send({"phase": "query"})

            def expired(_signal, _frame):
                raise CaseError(
                    "query_budget_exceeded",
                    details={
                        "limit_name": "query_cpu_seconds",
                        "limit": packet["limits"]["query_cpu_seconds"],
                    },
                )

            signal.signal(signal.SIGPROF, expired)
            signal.setitimer(
                signal.ITIMER_PROF, float(packet["limits"]["query_cpu_seconds"])
            )

        export_engine.start_query_budget = query_start
        result = export_engine.execute_view(
            request["tool"],
            request["args"],
            request["identity"],
            request["path"],
            packet,
            request.get("cursor_state"),
        )
        signal.setitimer(signal.ITIMER_PROF, 0)
        encoded = json_bytes({"ok": True, "data": result})
        if len(encoded) > packet["limits"]["response_bytes"] + 16384:
            raise CaseError("response_budget_exceeded")
        _send({"ok": True, "data": result})
    except CaseError as exc:
        with suppress(Exception):
            _send({"ok": False, "error": exc.as_dict()})
    except (MemoryError, OSError):
        with suppress(Exception):
            _send({"ok": False, "error": CaseError("query_budget_exceeded").as_dict()})
    except BaseException:
        with suppress(Exception):
            _send(
                {"ok": False, "error": CaseError("unsupported_export_shape").as_dict()}
            )


async def _rss(pid: int) -> int:
    if sys.platform.startswith("linux"):
        try:
            fields = Path(f"/proc/{pid}/statm").read_text().split()
            return int(fields[1]) * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            return 0
    process = await asyncio.create_subprocess_exec(
        "/bin/ps",
        "-o",
        "rss=",
        "-p",
        str(pid),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={"PATH": os.defpath, "LANG": "C"},
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 0.5)
        return int(stdout.strip()) * 1024 if stdout.strip() else 0
    except (ValueError, TimeoutError):
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise CaseError("query_budget_exceeded") from None


async def run_view(
    tool: str,
    args: dict,
    identity: dict,
    path: str,
    packet: dict,
    cursor_state: dict | None = None,
) -> dict:
    """Enforce process RSS, parse wall and query CPU without inheriting keys."""
    if not (sys.platform.startswith("linux") or sys.platform == "darwin"):
        raise CaseError("query_budget_exceeded")
    env = {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
    }
    maximum = packet["limits"]["response_bytes"] + 16384
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        __name__,
        "child",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        limit=maximum,
    )
    reader = None
    deadline = time.monotonic() + packet["limits"]["parse_index_seconds"]
    limit_name = "parse_index_seconds"
    try:
        request = json_bytes(
            {
                "tool": tool,
                "args": args,
                "identity": identity,
                "path": path,
                "packet": packet,
                "cursor_state": cursor_state,
            }
        )
        if len(request) > 2 * 1024 * 1024:
            raise CaseError("query_budget_exceeded")
        process.stdin.write(request)
        await asyncio.wait_for(
            process.stdin.drain(), max(0.000001, deadline - time.monotonic())
        )
        process.stdin.close()
        reader = asyncio.create_task(process.stdout.readline())
        while True:
            ready, _ = await asyncio.wait([reader], timeout=0.02)
            if time.monotonic() > deadline:
                raise CaseError(
                    "query_budget_exceeded",
                    details={
                        "limit_name": limit_name,
                        "limit": packet["limits"][limit_name],
                    },
                )
            if await _rss(process.pid) > packet["limits"]["worker_memory_bytes"]:
                raise CaseError(
                    "query_budget_exceeded",
                    details={
                        "limit_name": "worker_memory_bytes",
                        "limit": packet["limits"]["worker_memory_bytes"],
                    },
                )
            if ready:
                try:
                    raw = reader.result()
                except (ValueError, asyncio.LimitOverrunError):
                    raise CaseError("response_budget_exceeded") from None
                if not raw or len(raw) > maximum:
                    raise CaseError("query_budget_exceeded")
                message = parse_json(raw)
                if message.get("phase") == "query":
                    deadline = time.monotonic() + max(
                        3, packet["limits"]["query_cpu_seconds"] * 3
                    )
                    limit_name = "query_cpu_seconds"
                    reader = asyncio.create_task(process.stdout.readline())
                    continue
                if message.get("ok") is False:
                    error = message["error"]
                    raise CaseError(
                        error["code"],
                        error["message"],
                        retryable=error["retryable"],
                        request_id=error["request_id"],
                        details=error["details"],
                    )
                if message.get("ok") is True and isinstance(message.get("data"), dict):
                    return message["data"]
                raise CaseError("unsupported_export_shape")
    except (BrokenPipeError, ConnectionResetError, TimeoutError):
        raise CaseError("query_budget_exceeded") from None
    finally:
        if reader is not None:
            reader.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await reader
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
        await process.wait()


if __name__ == "__main__" and sys.argv[1:] == ["child"]:
    _child()
