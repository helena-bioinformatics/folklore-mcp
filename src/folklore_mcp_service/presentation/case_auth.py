"""Request-local machine API credential for the hosted Folklore boundary."""

from contextvars import ContextVar

from folklore_mcp_service.case_tools.api_client import KEY_PATTERN
from folklore_mcp_service.case_tools.common import CaseError

current_api_key: ContextVar[str | None] = ContextVar(
    "folklore_case_api_key", default=None
)


def machine_bearer(headers) -> str | None:
    values = [value for key, value in headers if key.lower() == b"authorization"]
    if not values:
        return None
    if len(values) != 1:
        raise CaseError("authentication_required")
    try:
        value = values[0].decode("ascii")
    except UnicodeDecodeError:
        raise CaseError("authentication_required") from None
    if not value.startswith("Bearer "):
        raise CaseError("authentication_required")
    credential = value[7:]
    if KEY_PATTERN.fullmatch(credential) is None:
        raise CaseError("authentication_required")
    return credential
