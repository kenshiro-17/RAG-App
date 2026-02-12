from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s",
    )


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()
        logger = logging.getLogger("api.request")

        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s status=%s latency_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                latency_ms,
                extra={"request_id": request_id},
            )
            response.headers["x-request-id"] = request_id
            return response
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s status=500 latency_ms=%.2f",
                request.method,
                request.url.path,
                latency_ms,
                extra={"request_id": request_id},
            )
            raise
