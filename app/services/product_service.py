"""Service layer for product catalog management."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, func, select

from app.db.models import AttributeDef, Category, Product, ProductAttribute
from app.domain.exceptions import (
    AttributeDefNotFoundError,
    CategoryNotFoundError,
    DuplicateSKUError,
    InvalidAttributeValueError,
    ProductNotFoundError,
)
from app.domain.schemas import (
    CategoryRead,
    ProductAttributeValue,
    ProductCreate,
    ProductDetailRead,
    ProductUpdate,
)
from app.services.attribute_service import AttributeService


class ProductService:
    """Handles business logic for products and product attributes."""

    @staticmethod
    def create(session: Session, data: ProductCreate) -> Product:
        """Create a new product with validated SKU, category, and attributes."""
        # 1. Check SKU uniqueness
        existing_sku = session.exec(select(Product).where(Product.sku == data.sku)).first()
        if existing_sku:
            raise DuplicateSKUError(f"Product with SKU '{data.sku}' already exists.")

        # 2. Check category existence if provided
        if data.category_id is not None:
            category = session.get(Category, data.category_id)
            if not category:
                raise CategoryNotFoundError(f"Category ID {data.category_id} not found.")

        # 3. Create product record
        product = Product(
            sku=data.sku,
            name=data.name,
            description=data.description,
            price=data.price,
            stock=data.stock,
            category_id=data.category_id,
            status=data.status,
            woo_id=data.woo_id,
            health_score=data.health_score,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(product)
        session.flush()  # Populate product.id for attributes

        # 4. Attach and validate attributes
        if data.attributes and product.id is not None:
            ProductService._apply_attributes(session, product.id, data.attributes)

        session.commit()
        session.refresh(product)
        return product

    @staticmethod
    def get(session: Session, product_id: int) -> Product:
        """Retrieve a product by its ID."""
        product = session.get(Product, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} not found.")
        return product

    @staticmethod
    def get_by_sku(session: Session, sku: str) -> Product | None:
        """Retrieve a product by its unique SKU."""
        return session.exec(select(Product).where(Product.sku == sku)).first()

    @staticmethod
    def list_all(
        session: Session,
        query: str | None = None,
        category_id: int | None = None,
        status: str | None = None,
        min_health_score: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Product], int]:
        """List products with search, filtering, and pagination support."""
        statement = select(Product)
        count_statement = select(func.count(col(Product.id)))

        if query:
            search_filter = col(Product.name).contains(query) | col(Product.sku).contains(query)
            statement = statement.where(search_filter)
            count_statement = count_statement.where(search_filter)

        if category_id is not None:
            statement = statement.where(Product.category_id == category_id)
            count_statement = count_statement.where(Product.category_id == category_id)

        if status:
            statement = statement.where(Product.status == status)
            count_statement = count_statement.where(Product.status == status)

        if min_health_score is not None:
            statement = statement.where(col(Product.health_score) >= min_health_score)
            count_statement = count_statement.where(col(Product.health_score) >= min_health_score)

        total_count = session.exec(count_statement).one() or 0
        items = session.exec(
            statement.order_by(col(Product.id)).offset(offset).limit(limit)
        ).all()

        return items, int(total_count)

    @staticmethod
    def update(session: Session, product_id: int, data: ProductUpdate) -> Product:
        """Update an existing product and its attributes."""
        product = ProductService.get(session, product_id)

        update_dict = data.model_dump(exclude_unset=True)

        # SKU uniqueness check if changed
        if "sku" in update_dict and update_dict["sku"] != product.sku:
            existing_sku = session.exec(
                select(Product).where(Product.sku == update_dict["sku"])
            ).first()
            if existing_sku:
                raise DuplicateSKUError(f"Product with SKU '{update_dict['sku']}' already exists.")

        # Category check if changed
        if "category_id" in update_dict and update_dict["category_id"] is not None:
            category = session.get(Category, update_dict["category_id"])
            if not category:
                raise CategoryNotFoundError(f"Category ID {update_dict['category_id']} not found.")

        # Update attributes if explicitly provided
        if "attributes" in update_dict:
            new_attrs = update_dict.pop("attributes")
            if new_attrs is not None and product.id is not None:
                # Remove existing attributes
                existing_attrs = session.exec(
                    select(ProductAttribute).where(ProductAttribute.product_id == product.id)
                ).all()
                for attr in existing_attrs:
                    session.delete(attr)
                session.flush()

                ProductService._apply_attributes(session, product.id, new_attrs)

        for key, value in update_dict.items():
            setattr(product, key, value)

        product.updated_at = datetime.now(UTC)
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    @staticmethod
    def delete(session: Session, product_id: int) -> bool:
        """Delete a product and its associated product attributes."""
        product = ProductService.get(session, product_id)
        session.delete(product)
        session.commit()
        return True

    @staticmethod
    def _apply_attributes(
        session: Session,
        product_id: int,
        attributes: Sequence[Any],
    ) -> None:
        """Validate and attach attributes to a product."""
        for attr_input in attributes:
            if isinstance(attr_input, dict):
                attr_id = int(attr_input["attribute_id"])
                val = str(attr_input["value"])
            else:
                attr_id = attr_input.attribute_id
                val = attr_input.value

            attr_def = session.get(AttributeDef, attr_id)
            if not attr_def:
                raise AttributeDefNotFoundError(f"Attribute definition ID {attr_id} not found.")

            # Validate select type allowed values
            if attr_def.type == "select":
                allowed = AttributeService.parse_allowed_values(attr_def)
                if allowed and val not in allowed:
                    raise InvalidAttributeValueError(
                        f"Value '{val}' is not allowed for attribute '{attr_def.name}'. "
                        f"Allowed values: {allowed}"
                    )

            prod_attr = ProductAttribute(
                product_id=product_id,
                attribute_id=attr_id,
                value=val,
            )
            session.add(prod_attr)

    @staticmethod
    def to_detail_read(session: Session, product: Product) -> ProductDetailRead:
        """Transform a Product model into a comprehensive ProductDetailRead schema."""
        category_read: CategoryRead | None = None
        if product.category_id:
            cat = session.get(Category, product.category_id)
            if cat:
                category_read = CategoryRead.model_validate(cat)

        # Fetch attributes with their definitions
        prod_attrs = session.exec(
            select(ProductAttribute).where(ProductAttribute.product_id == product.id)
        ).all()

        attr_values: list[ProductAttributeValue] = []
        for pa in prod_attrs:
            attr_def = session.get(AttributeDef, pa.attribute_id)
            if attr_def:
                attr_values.append(
                    ProductAttributeValue(
                        attribute_id=pa.attribute_id,
                        attribute_name=attr_def.name,
                        attribute_type=attr_def.type,
                        value=pa.value,
                    )
                )

        return ProductDetailRead(
            id=product.id or 0,
            sku=product.sku,
            name=product.name,
            description=product.description,
            price=product.price,
            stock=product.stock,
            category_id=product.category_id,
            status=product.status,
            woo_id=product.woo_id,
            health_score=product.health_score,
            created_at=product.created_at,
            updated_at=product.updated_at,
            category=category_read,
            attributes=attr_values,
        )


# Backward-compatible alias
ProductService.list = ProductService.list_all  # type: ignore[attr-defined]
