"""Thin FastAPI router for product catalog management."""

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.db.session import get_session
from app.domain.schemas import (
    ProductCreate,
    ProductDetailRead,
    ProductListResponse,
    ProductUpdate,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    query: str | None = Query(default=None, description="Search term for SKU or name"),
    category_id: int | None = Query(default=None, description="Filter by category ID"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
    min_health_score: int | None = Query(
        default=None, ge=0, le=100, description="Minimum health score"
    ),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=50, ge=1, le=100, description="Limit for pagination"),
    session: Session = Depends(get_session),
) -> ProductListResponse:
    """List products with optional search, filtering, and pagination."""
    items, total = ProductService.list_all(
        session=session,
        query=query,
        category_id=category_id,
        status=status_filter,
        min_health_score=min_health_score,
        offset=offset,
        limit=limit,
    )
    detail_items = [ProductService.to_detail_read(session, item) for item in items]
    return ProductListResponse(
        items=detail_items,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=ProductDetailRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_session),
) -> ProductDetailRead:
    """Create a new product with optional initial attributes."""
    product = ProductService.create(session, payload)
    return ProductService.to_detail_read(session, product)


@router.get("/{product_id}", response_model=ProductDetailRead)
def get_product(
    product_id: int,
    session: Session = Depends(get_session),
) -> ProductDetailRead:
    """Retrieve detailed product information by ID."""
    product = ProductService.get(session, product_id)
    return ProductService.to_detail_read(session, product)


@router.put("/{product_id}", response_model=ProductDetailRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    session: Session = Depends(get_session),
) -> ProductDetailRead:
    """Update product details and attributes."""
    product = ProductService.update(session, product_id, payload)
    return ProductService.to_detail_read(session, product)


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a product by ID."""
    ProductService.delete(session, product_id)
    return {"ok": True}
