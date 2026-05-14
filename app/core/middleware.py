from __future__ import annotations

import logging
import re
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import _StreamingResponse  # noqa: F401 (type hint only)
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# SECURITY FIX: Only accept X-Request-ID values that look like a UUID / short
# alphanumeric token.  Anything else (e.g. a newline-injected log payload) is
# silently replaced with a fresh UUID4.
_SAFE_REQUEST_ID_RE = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')


async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    """Attach a unique request-id to every request/response cycle.

    * Reads ``X-Request-ID`` from the incoming headers; generates a UUID4 when
      absent so every request is traceable end-to-end.
    * Forwards the id in the ``X-Request-ID`` response header.
    * Emits a single structured INFO log line with method, path, status, and id.
    """
    raw_id = request.headers.get("X-Request-ID", "")
    # SECURITY FIX: validate before trusting — prevents log-injection via header
    request_id: str = (
        raw_id
        if _SAFE_REQUEST_ID_RE.match(raw_id)
        else str(uuid.uuid4())
    )

    response: Response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
        },
    )

    return response
