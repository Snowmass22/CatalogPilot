"""Service layer for attribute definitions."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, select

from app.db.models import AttributeDef
from app.domain.exceptions import AttributeDefNotFoundError, DuplicateAttributeNameError
from app.domain.schemas import AttributeDefCreate, AttributeDefUpdate


class AttributeService:
    """Handles business logic for product attribute definitions."""

    @staticmethod
    def create(session: Session, data: AttributeDefCreate) -> AttributeDef:
        """Create a new attribute definition ensuring unique naming."""
        existing = session.exec(select(AttributeDef).where(AttributeDef.name == data.name)).first()
        if existing:
            raise DuplicateAttributeNameError(f"Attribute '{data.name}' already exists.")

        allowed_json = json.dumps(data.allowed_values) if data.allowed_values is not None else None

        attr = AttributeDef(
            name=data.name,
            type=data.type,
            allowed_values=allowed_json,
            woo_attribute_id=data.woo_attribute_id,
        )
        session.add(attr)
        session.commit()
        session.refresh(attr)
        return attr

    @staticmethod
    def get(session: Session, attr_id: int) -> AttributeDef:
        """Retrieve an attribute definition by ID."""
        attr = session.get(AttributeDef, attr_id)
        if not attr:
            raise AttributeDefNotFoundError(f"Attribute definition with ID {attr_id} not found.")
        return attr

    @staticmethod
    def get_by_name(session: Session, name: str) -> AttributeDef | None:
        """Retrieve an attribute definition by name."""
        return session.exec(select(AttributeDef).where(AttributeDef.name == name)).first()

    @staticmethod
    def list_all(session: Session) -> Sequence[AttributeDef]:
        """List all attribute definitions."""
        return session.exec(select(AttributeDef)).all()

    @staticmethod
    def update(session: Session, attr_id: int, data: AttributeDefUpdate) -> AttributeDef:
        """Update an existing attribute definition."""
        attr = AttributeService.get(session, attr_id)

        update_dict = data.model_dump(exclude_unset=True)
        if "name" in update_dict and update_dict["name"] != attr.name:
            existing = session.exec(
                select(AttributeDef).where(AttributeDef.name == update_dict["name"])
            ).first()
            if existing:
                raise DuplicateAttributeNameError(
                    f"Attribute '{update_dict['name']}' already exists."
                )

        if "allowed_values" in update_dict:
            val = update_dict.pop("allowed_values")
            attr.allowed_values = json.dumps(val) if val is not None else None

        for key, value in update_dict.items():
            setattr(attr, key, value)

        session.add(attr)
        session.commit()
        session.refresh(attr)
        return attr

    @staticmethod
    def delete(session: Session, attr_id: int) -> bool:
        """Delete an attribute definition."""
        attr = AttributeService.get(session, attr_id)
        session.delete(attr)
        session.commit()
        return True

    @staticmethod
    def parse_allowed_values(attr: AttributeDef) -> list[str] | None:
        """Helper to deserialize allowed_values JSON string into a list of strings."""
        if not attr.allowed_values:
            return None
        try:
            parsed: Any = json.loads(attr.allowed_values)
            return [str(v) for v in parsed] if isinstance(parsed, list) else None
        except (json.JSONDecodeError, TypeError):
            return None


# Backward-compatible alias
AttributeService.list = AttributeService.list_all  # type: ignore[attr-defined]
