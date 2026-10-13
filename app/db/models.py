"""SQLModel database tables for CatalogPilot."""

from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class Category(SQLModel, table=True):
    """Product Category supporting flat or nested hierarchies."""

    __tablename__ = "category"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=255)
    parent_id: int | None = Field(default=None, foreign_key="category.id")
    woo_id: int | None = Field(default=None, index=True)

    # Self-referencing relationships
    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Category.id"},
    )
    children: list["Category"] = Relationship(back_populates="parent")

    # Related products
    products: list["Product"] = Relationship(back_populates="category")


class AttributeDef(SQLModel, table=True):
    """Attribute definition specifying allowed values and type."""

    __tablename__ = "attributedef"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    type: str = Field(default="text", max_length=50)  # text, select, number
    allowed_values: str | None = Field(default=None)  # Stored as JSON string
    woo_attribute_id: int | None = Field(default=None, index=True)

    # Relationships
    product_attributes: list["ProductAttribute"] = Relationship(
        back_populates="attribute_def",
        cascade_delete=True,
    )


class ProductAttribute(SQLModel, table=True):
    """Link table between Product and AttributeDef storing attribute value."""

    __tablename__ = "productattribute"

    product_id: int = Field(foreign_key="product.id", primary_key=True)
    attribute_id: int = Field(foreign_key="attributedef.id", primary_key=True)
    value: str = Field(default="", max_length=500)

    # Relationships
    product: Optional["Product"] = Relationship(back_populates="attributes")
    attribute_def: AttributeDef | None = Relationship(back_populates="product_attributes")


class Product(SQLModel, table=True):
    """Product master entity in CatalogPilot."""

    __tablename__ = "product"

    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(unique=True, index=True, max_length=100)
    name: str = Field(index=True, max_length=255)
    description: str | None = Field(default=None)
    price: float = Field(default=0.0)
    stock: int = Field(default=0)
    category_id: int | None = Field(default=None, foreign_key="category.id")
    status: str = Field(default="draft", max_length=50)
    woo_id: int | None = Field(default=None, index=True)
    health_score: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Relationships
    category: Category | None = Relationship(back_populates="products")
    attributes: list[ProductAttribute] = Relationship(
        back_populates="product",
        cascade_delete=True,
    )
