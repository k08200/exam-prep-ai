import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger("app.requests")


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach request IDs, log request outcomes, and cap request setup time."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()

    try:
        response = await asyncio.wait_for(
            call_next(request),
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(
            "request_timeout",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": elapsed_ms,
            },
        )
        response = JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "Request timed out"},
        )
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.exception(
            "request_error",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": elapsed_ms,
            },
        )
        raise

    response.headers["X-Request-ID"] = request_id
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
        },
    )
    return response
