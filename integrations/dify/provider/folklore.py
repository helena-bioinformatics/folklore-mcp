from dify_plugin import ToolProvider


class FolkloreProvider(ToolProvider):
    def validate_credentials(self, credentials: dict) -> None:
        return None
