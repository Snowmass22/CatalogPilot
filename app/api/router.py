"""API router aggregation."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.attributes import router as attributes_router
from app.api.categories import router as categories_router
from app.api.imports import router as imports_router
from app.api.products import router as products_router
from app.db.session import get_session
from app.domain.schemas import CatalogHealthSummary
from app.services.health_service import HealthService

api_router = APIRouter(prefix="/api")

api_router.include_router(products_router)
api_router.include_router(categories_router)
api_router.include_router(attributes_router)
api_router.include_router(imports_router)


@api_router.get("/health", response_model=CatalogHealthSummary, tags=["Health"])
def get_catalog_health(
    session: Session = Depends(get_session),
) -> CatalogHealthSummary:
    """Catalog Health Score summary endpoint (PRD 1.7). Returns average score, distribution, and top issues."""
    return HealthService.get_catalog_health(session)


@api_router.post("/health/recompute", tags=["Health"])
def recompute_catalog_health(
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Recompute health scores for all products in the catalog."""
    return HealthService.recompute_all(session)
