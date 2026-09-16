"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.routers.dashboard import router as dashboard_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.patients import router as patients_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.exceptions import AppError
from app.schemas.envelope import err
from app.services.patient_service import pydantic_errors
from app.voice.webhook import router as vapi_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Patient Registration Voice Agent",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=err(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = pydantic_errors(exc)  # type: ignore[arg-type]
        return JSONResponse(
            status_code=422,
            content=err("validation_error", "Request validation failed", details),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=err("validation_error", "Request validation failed", pydantic_errors(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def wrapped_http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(status_code=exc.status_code, content=err(code, str(message)))

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, _exc: Exception) -> JSONResponse:
        import structlog

        structlog.get_logger("app").exception("unhandled_error")
        return JSONResponse(
            status_code=500,
            content=err("internal_error", "An unexpected error occurred"),
        )

    app.include_router(health_router)
    app.include_router(patients_router)
    app.include_router(patients_router, prefix="/api/v1")
    app.include_router(dashboard_router)
    app.include_router(vapi_router)

    return app


app = create_app()
