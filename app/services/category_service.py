"""Service layer for category operations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from app.db.models import Category
from app.domain.exceptions import CategoryNotFoundError, ParentCategoryCycleError
from app.domain.schemas import CategoryCreate, CategoryUpdate


class CategoryService:
    """Handles business logic for product categories."""

    @staticmethod
    def create(session: Session, data: CategoryCreate) -> Category:
        """Create a new category, validating parent if specified."""
        if data.parent_id is not None:
            parent = session.get(Category, data.parent_id)
            if not parent:
                raise CategoryNotFoundError(f"Parent category {data.parent_id} does not exist.")

        category = Category(
            name=data.name,
            parent_id=data.parent_id,
            woo_id=data.woo_id,
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        return category

    @staticmethod
    def get(session: Session, category_id: int) -> Category:
        """Retrieve a category by ID."""
        category = session.get(Category, category_id)
        if not category:
            raise CategoryNotFoundError(f"Category with ID {category_id} not found.")
        return category

    @staticmethod
    def list_all(session: Session, parent_id: int | None = None) -> Sequence[Category]:
        """List categories, optionally filtering by parent ID."""
        statement = select(Category)
        if parent_id is not None:
            statement = statement.where(Category.parent_id == parent_id)
        return session.exec(statement).all()

    @staticmethod
    def update(session: Session, category_id: int, data: CategoryUpdate) -> Category:
        """Update an existing category and prevent cyclical hierarchies."""
        category = CategoryService.get(session, category_id)

        update_dict = data.model_dump(exclude_unset=True)
        if "parent_id" in update_dict:
            new_parent_id = update_dict["parent_id"]
            if new_parent_id == category_id:
                raise ParentCategoryCycleError("A category cannot be its own parent.")

            if new_parent_id is not None:
                parent = session.get(Category, new_parent_id)
                if not parent:
                    raise CategoryNotFoundError(f"Parent category {new_parent_id} does not exist.")

                # Traverse parent chain upward to detect circular hierarchy
                curr = parent
                while curr.parent_id is not None:
                    if curr.parent_id == category_id:
                        raise ParentCategoryCycleError("Circular category hierarchy detected.")
                    curr = session.get(Category, curr.parent_id)  # type: ignore[assignment]
                    if not curr:
                        break

        for key, value in update_dict.items():
            setattr(category, key, value)

        session.add(category)
        session.commit()
        session.refresh(category)
        return category

    @staticmethod
    def delete(session: Session, category_id: int) -> bool:
        """Delete a category and detach child references."""
        category = CategoryService.get(session, category_id)

        # Unparent direct children before deletion
        children = session.exec(select(Category).where(Category.parent_id == category_id)).all()
        for child in children:
            child.parent_id = None
            session.add(child)

        session.delete(category)
        session.commit()
        return True


# Backward-compatible alias
CategoryService.list = CategoryService.list_all  # type: ignore[attr-defined]
