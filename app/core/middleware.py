from __future__ import annotations

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import _StreamingResponse  # noqa: F401 (type hint only)
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    """Attach a unique request-id to every request/response cycle.

    * Reads ``X-Request-ID`` from the incoming headers; generates a UUID4 when
      absent so every request is traceable end-to-end.
    * Forwards the id in the ``X-Request-ID`` response header.
    * Emits a single structured INFO log line with method, path, status, and id.
    """
    request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())

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
