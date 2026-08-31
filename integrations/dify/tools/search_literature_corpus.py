import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.mcp_client import call_tool


class SearchLiteratureCorpusTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        args = {
            "query": str(tool_parameters.get("query", "")).strip(),
            "limit": int(tool_parameters.get("limit", 10)),
            "sort": "relevance",
        }
        yield self.create_text_message(
            json.dumps(call_tool("search_literature_corpus", args), ensure_ascii=False)
        )
