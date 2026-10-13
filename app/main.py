"""Main FastAPI application entrypoint for CatalogPilot."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.ui import ui_router
from app.db.session import init_db
from app.domain.exceptions import (
    DuplicateAttributeNameError,
    DuplicateSKUError,
    EntityNotFoundError,
    InvalidAttributeValueError,
    ParentCategoryCycleError,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler initializing database schema on startup."""
    init_db()
    yield


app = FastAPI(
    title="CatalogPilot",
    description="Agentic PIM that cleans, enriches and safely syncs product data to WooCommerce",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Domain Exception Handlers
@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
    """Handle entity not found domain errors with HTTP 404."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.message},
    )


@app.exception_handler(DuplicateSKUError)
async def duplicate_sku_handler(request: Request, exc: DuplicateSKUError) -> JSONResponse:
    """Handle duplicate SKU conflicts with HTTP 409."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message},
    )


@app.exception_handler(DuplicateAttributeNameError)
async def duplicate_attribute_handler(
    request: Request, exc: DuplicateAttributeNameError
) -> JSONResponse:
    """Handle duplicate attribute definition name conflicts with HTTP 409."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message},
    )


@app.exception_handler(InvalidAttributeValueError)
async def invalid_attribute_value_handler(
    request: Request, exc: InvalidAttributeValueError
) -> JSONResponse:
    """Handle invalid attribute value errors with HTTP 422."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.message},
    )


@app.exception_handler(ParentCategoryCycleError)
async def parent_category_cycle_handler(
    request: Request, exc: ParentCategoryCycleError
) -> JSONResponse:
    """Handle circular category hierarchy errors with HTTP 422."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.message},
    )


# Include Routers
app.include_router(ui_router)
app.include_router(api_router)
