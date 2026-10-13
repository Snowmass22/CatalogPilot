"""Thin FastAPI router for attribute definitions."""

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.db.session import get_session
from app.domain.schemas import (
    AttributeDefCreate,
    AttributeDefRead,
    AttributeDefUpdate,
)
from app.services.attribute_service import AttributeService

router = APIRouter(prefix="/attributes", tags=["Attributes"])


def _to_read_schema(attr: object) -> AttributeDefRead:
    """Helper to convert AttributeDef entity into AttributeDefRead schema."""
    from app.db.models import AttributeDef

    assert isinstance(attr, AttributeDef)
    return AttributeDefRead(
        id=attr.id or 0,
        name=attr.name,
        type=attr.type,
        allowed_values=AttributeService.parse_allowed_values(attr),
        woo_attribute_id=attr.woo_attribute_id,
    )


@router.get("", response_model=list[AttributeDefRead])
def list_attributes(session: Session = Depends(get_session)) -> list[AttributeDefRead]:
    """List all attribute definitions."""
    attrs = AttributeService.list_all(session)
    return [_to_read_schema(a) for a in attrs]


@router.post("", response_model=AttributeDefRead, status_code=status.HTTP_201_CREATED)
def create_attribute(
    payload: AttributeDefCreate,
    session: Session = Depends(get_session),
) -> AttributeDefRead:
    """Create a new attribute definition."""
    attr = AttributeService.create(session, payload)
    return _to_read_schema(attr)


@router.get("/{attribute_id}", response_model=AttributeDefRead)
def get_attribute(
    attribute_id: int,
    session: Session = Depends(get_session),
) -> AttributeDefRead:
    """Retrieve an attribute definition by ID."""
    attr = AttributeService.get(session, attribute_id)
    return _to_read_schema(attr)


@router.put("/{attribute_id}", response_model=AttributeDefRead)
def update_attribute(
    attribute_id: int,
    payload: AttributeDefUpdate,
    session: Session = Depends(get_session),
) -> AttributeDefRead:
    """Update an existing attribute definition."""
    attr = AttributeService.update(session, attribute_id, payload)
    return _to_read_schema(attr)


@router.delete("/{attribute_id}", status_code=status.HTTP_200_OK)
def delete_attribute(
    attribute_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete an attribute definition."""
    AttributeService.delete(session, attribute_id)
    return {"ok": True}
