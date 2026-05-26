import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("focusspark.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                request.client.host if request.client else "-",
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            request.client.host if request.client else "-",
        )

        response.headers["X-Request-ID"] = request_id
        return response
