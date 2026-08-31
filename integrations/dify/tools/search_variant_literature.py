import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.mcp_client import call_tool


class SearchVariantLiteratureTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        args = {"assembly": "GRCh38", "query": str(tool_parameters.get("query", "")).strip(), "limit": int(tool_parameters.get("limit", 10))}
        yield self.create_text_message(json.dumps(call_tool("search_variant_literature", args), ensure_ascii=False))
