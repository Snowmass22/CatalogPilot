"""Thin FastAPI router for categories."""

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.db.session import get_session
from app.domain.schemas import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories(
    parent_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[CategoryRead]:
    """List categories, optionally filtering by parent category."""
    categories = CategoryService.list_all(session, parent_id=parent_id)
    return [CategoryRead.model_validate(c) for c in categories]


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    session: Session = Depends(get_session),
) -> CategoryRead:
    """Create a new category."""
    category = CategoryService.create(session, payload)
    return CategoryRead.model_validate(category)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> CategoryRead:
    """Retrieve a category by ID."""
    category = CategoryService.get(session, category_id)
    return CategoryRead.model_validate(category)


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
) -> CategoryRead:
    """Update an existing category."""
    category = CategoryService.update(session, category_id, payload)
    return CategoryRead.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a category by ID."""
    CategoryService.delete(session, category_id)
    return {"ok": True}
