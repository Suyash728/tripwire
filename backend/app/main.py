"""Tripwire FastAPI app. Every response, including errors, uses {success, data, error}."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")
load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from app.api.routes import envelope, router  # noqa: E402


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS") or os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000"
    )
    # Include both UI dev port (3000) and Playwright e2e port (3100)
    origins = [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
    for fallback in ("http://localhost:3000", "http://localhost:3100"):
        if fallback not in origins:
            origins.append(fallback)
    return origins


app = FastAPI(title="Tripwire Gateway API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization", "x-admin-token"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_req: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=envelope(
            None,
            success=False,
            error={"code": "validation_error", "message": str(exc.errors())},
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope(
            None,
            success=False,
            error={"code": f"http_{exc.status_code}", "message": str(exc.detail)},
        ),
    )


@app.get("/health")
async def health() -> dict:
    return envelope({"status": "ok"})


app.include_router(router)
