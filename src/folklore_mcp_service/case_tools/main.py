"""Local stdio executable for API-key case processing (CR024)."""

from __future__ import annotations

import asyncio
import math
import os
import sys
from pathlib import Path

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import discovery, source_browse
from .api_client import ApiClient
from .commands import Commands
from .common import (
    MAX_RESPONSE_BYTES,
    SOFTWARE_VERSION,
    VERSION,
    CaseError,
    json_bytes,
    private_directory,
    wire_numbers,
)
from .contracts import (
    DESCRIPTIONS,
    EXPORT_TOOLS,
    INPUT_SCHEMAS,
    OUTPUT_SCHEMAS,
    TOOLS,
    WRITE_TOOLS,
    validate_input,
    validate_output,
)
from .journal import Journal
from .private_logging import protect_transport_logs
from .store import ExportStore


class CaseService:
    def __init__(self, api_key: str, state_dir: Path, output_dir: Path, *, api=None):
        self.api = api or ApiClient(api_key)
        self.state_dir = private_directory(Path(state_dir))
        self.output_dir = private_directory(Path(output_dir))
        self.journal = Journal(self.state_dir, api_key)
        try:
            self.commands = Commands(self.api, self.journal)
            self.exports = ExportStore(self.api, self.journal, self.state_dir)
        except BaseException:
            self.journal.close()
            raise
        self.lock = asyncio.Lock()
        self._release_transport_logs = protect_transport_logs()

    @staticmethod
    def _error(error: CaseError):
        allowed = {
            "field",
            "collection",
            "limit_name",
            "limit",
            "expected_generation_id",
            "actual_generation_id",
        }
        details = {key: value for key, value in error.details.items() if key in allowed}
        message = error.code.replace("_", " ").capitalize()
        wait = error.details.get("retry_after_seconds")
        if (
            isinstance(wait, (int, float))
            and math.isfinite(wait)
            and 0 <= wait <= 9007199254740991
        ):
            message += ". Retry after " + str(math.ceil(wait)) + " seconds"
        return {
            "ok": False,
            "error": {
                "code": error.code[:128],
                "message": message[:500],
                "retryable": error.retryable,
                "request_id": error.request_id,
                "details": details,
            },
        }

    @staticmethod
    def _result(name, envelope):
        label = name if name in TOOLS else "tool"
        outcome = "completed" if envelope["ok"] else envelope["error"]["code"]
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text=label + ": " + outcome)],
            structuredContent=envelope,
            isError=not envelope["ok"],
        )
        if (
            len(
                json_bytes(
                    result.model_dump(mode="json", by_alias=True, exclude_none=True)
                )
            )
            > MAX_RESPONSE_BYTES
        ):
            raise CaseError(
                "response_budget_exceeded",
                details={"limit_name": "response_bytes", "limit": MAX_RESPONSE_BYTES},
            )
        return result

    async def call(self, name: str, arguments: dict):
        try:
            args = validate_input(name, arguments)
            async with self.lock:
                if name in EXPORT_TOOLS:
                    envelope = {"ok": True, "data": await self.exports.call(name, args)}
                else:
                    if name in WRITE_TOOLS:
                        source = await self.commands.call(name, args)
                    elif name == source_browse.TOOL:
                        source = await self.api.browse_source_objects(args)
                    elif name in discovery.TOOLS:
                        source = await discovery.call(self.api, name, args)
                    elif name == "list_analysis_contexts":
                        source = await self.api.context()
                    elif name == "get_case_analysis_status":
                        source = await self.api.status(args["analysis_id"])
                    elif name == "get_case_analysis_result_manifest":
                        source = await self.api.manifest(args["analysis_id"])
                    elif name == "download_analysis_result_file":
                        source = await self.api.download(
                            args["analysis_id"], args["artifact_id"], self.output_dir
                        )
                    else:
                        raise CaseError("unknown_tool")
                    member = (
                        "file" if name == "download_analysis_result_file" else "result"
                    )
                    envelope = {
                        "ok": True,
                        "data": {
                            "contract_version": VERSION,
                            "source_operation": name,
                            member: wire_numbers(source),
                        },
                    }
                validate_output(name, envelope)
                return self._result(name, envelope)
        except CaseError as error:
            return self._result(name, self._error(error))
        except Exception:
            return self._result(name, self._error(CaseError("internal_error")))

    async def close(self):
        try:
            self.exports.close()
            try:
                await self.api.close()
            finally:
                self.journal.close()
        finally:
            self._release_transport_logs()


def create_server(service: CaseService) -> Server:
    async def list_tools(context, params):
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=name,
                    description=DESCRIPTIONS[name],
                    inputSchema=INPUT_SCHEMAS[name],
                    outputSchema=OUTPUT_SCHEMAS[name],
                    annotations=types.ToolAnnotations(
                        readOnlyHint=name not in WRITE_TOOLS
                        and name != "download_analysis_result_file",
                        destructiveHint=name
                        == "request_sequencing_analysis_cancellation",
                        idempotentHint=True,
                        openWorldHint=True,
                    ),
                )
                for name in TOOLS
            ]
        )

    async def call_tool(context, params):
        return await service.call(params.name, params.arguments or {})

    return Server(
        "folklore-case-mcp",
        version=SOFTWARE_VERSION,
        title="Folklore Case Analysis MCP",
        instructions="Use list_analysis_contexts before selecting a submission context and profile. "
        "Supply an explicit cost ceiling and original idempotency key. "
        "Use browse_source_objects to select an admitted S3 file and immutable version. "
        "Read status until publication, then use the frozen export views.",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve():
    import logging

    for name in ("httpx", "httpcore"):
        logging.getLogger(name).disabled = True
    os.umask(0o077)
    state_home = Path(
        os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    )
    state_dir = Path(
        os.environ.get("FOLKLORE_CASE_STATE_DIR", str(state_home / "folklore-case-mcp"))
    )
    output_dir = Path(
        os.environ.get("FOLKLORE_CASE_OUTPUT_DIR", str(state_dir / "downloads"))
    )
    key = os.environ.get("FOLKLORE_API_KEY", "")
    service = CaseService(key, state_dir, output_dir)
    try:
        server = create_server(service)
        async with stdio_server() as streams:
            await server.run(*streams, server.create_initialization_options())
    finally:
        await service.close()


def main():
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    except Exception:
        print("Folklore Case Analysis MCP could not start", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
