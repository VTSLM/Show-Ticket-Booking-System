"""Turn unhandled errors into a clean JSON 500 that still carries CORS headers.

FastAPI's own `@app.exception_handler(Exception)` runs outside the CORS middleware,
so the browser gets a 500 without CORS headers and reports a "CORS error" instead of
the real failure. This middleware is added *before* CORSMiddleware in main.py, which
makes it the inner layer: CORS headers are added to the 500 it returns.
"""
import logging

from fastapi.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")


class CatchUnhandledErrors:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Full details go to the server log only; the client gets a generic message.
            logger.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if response_started:
                raise
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
            await response(scope, receive, send)
