"""API router aggregation."""

from fastapi import APIRouter

from app.api.attributes import router as attributes_router
from app.api.categories import router as categories_router
from app.api.imports import router as imports_router
from app.api.products import router as products_router

api_router = APIRouter(prefix="/api")

api_router.include_router(products_router)
api_router.include_router(categories_router)
api_router.include_router(attributes_router)
api_router.include_router(imports_router)


@api_router.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "CatalogPilot API"}
