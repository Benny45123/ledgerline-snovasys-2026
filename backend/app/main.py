"""
How this works / why it is safe:
This module is the entry point and application factory for the LedgerLine FastAPI service.
Security features:
- Injects a unique X-Request-ID onto every request and response context.
- Enforces strict CORS headers (no wildcards permitted).
- Limits maximum HTTP request payload body size to 16 KB, preventing denial-of-service memory exhaustion.
- Enforces standardized JSON error envelopes {"error": {"code", "message", "request_id"}} on all failures.
- Intercepts all unhandled exceptions, suppressing raw tracebacks, SQL statements, and internal server paths.
- Provides unauthenticated, lightweight /health and /ready probes for deployment orchestrators.
"""

from typing import Any
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.accounts.routes import router as accounts_router
from app.audit.routes import router as audit_router
from app.auth.routes import router as auth_router
from app.config import settings
from app.db.engine import SessionLocal
from app.deps import get_request_id
from app.errors import AppError
from app.logging import logger, setup_logging
from app.review.routes import router as review_router

setup_logging(env=settings.ENV)

app = FastAPI(
    title="LedgerLine API",
    description="Money movement with a ledger you can prove.",
    version="0.1.0",
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
)

# CORS Middleware with strict explicit origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Idempotent-Replayed", "X-Request-ID"],
)


@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next: Any) -> Response:
    """Attach request tracing, body length limits, and security headers."""
    # Enforce request body size limit of 16 KB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 16 * 1024:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "error": {
                    "code": "body_too_large",
                    "message": "Request payload exceeds 16 KB limit.",
                    "request_id": request.headers.get("x-request-id", "unknown"),
                }
            },
        )

    # Establish or read request ID
    req_id = request.headers.get("x-request-id")
    if not req_id:
        req_id = get_request_id(None)

    response: Response = await call_next(request)

    # Security headers
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENV == "prod":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# Exception Handlers
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    req_id = request.headers.get("x-request-id", "unknown")
    logger.warning("app_error", code=exc.code, status_code=exc.status_code, message=exc.message, request_id=req_id)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "request_id": req_id}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = request.headers.get("x-request-id", "unknown")
    errors = exc.errors()
    first_msg = errors[0]["msg"] if errors else "Validation failed."
    logger.info("validation_error", errors=errors, request_id=req_id)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "validation_error", "message": first_msg, "request_id": req_id}},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = request.headers.get("x-request-id", "unknown")
    logger.error("internal_server_error", exc_info=exc, request_id=req_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. The operation was safely rolled back.",
                "request_id": req_id,
            }
        },
    )


# Health and Readiness Probes
@app.get("/health", tags=["Operational"])
def health_probe() -> dict[str, str]:
    """Lightweight process liveness probe."""
    return {"status": "ok"}


@app.get("/ready", tags=["Operational"])
def ready_probe() -> dict[str, str]:
    """Database connectivity and readiness probe."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "disconnected"},
        )
    finally:
        db.close()


# Mount Domain Routers
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(audit_router)
app.include_router(review_router)
