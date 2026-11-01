"""Per-request correlation ID, shared with the audit trail and error responses."""
import contextvars
import re
import uuid
from typing import Optional

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_request_id(incoming: Optional[str] = None) -> str:
    """Accept a well-formed caller-supplied ID, otherwise generate one."""
    if incoming and _VALID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def set_request_id(value: Optional[str]) -> None:
    _request_id.set(value)


def get_request_id() -> Optional[str]:
    return _request_id.get()
