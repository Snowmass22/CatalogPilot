"""Pydantic schemas for API requests, responses, and domain validation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Category Schemas ---
class CategoryBase(BaseModel):
    """Base schema for category attributes."""

    name: str = Field(..., min_length=1, max_length=255, description="Category name")
    parent_id: int | None = Field(default=None, description="Optional parent category ID")
    woo_id: int | None = Field(default=None, description="WooCommerce category ID")


class CategoryCreate(CategoryBase):
    """Schema for creating a new category."""


class CategoryUpdate(BaseModel):
    """Schema for updating an existing category."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: int | None = Field(default=None)
    woo_id: int | None = Field(default=None)


class CategoryRead(CategoryBase):
    """Schema for category serialization."""

    id: int

    model_config = ConfigDict(from_attributes=True)


# --- Attribute Definition Schemas ---
class AttributeDefBase(BaseModel):
    """Base schema for attribute definitions."""

    name: str = Field(..., min_length=1, max_length=100, description="Attribute name")
    type: Literal["text", "select", "number"] = Field(
        default="text",
        description="Attribute type: text, select, or number",
    )
    allowed_values: list[str] | None = Field(
        default=None,
        description="List of allowed values for select type",
    )
    woo_attribute_id: int | None = Field(
        default=None,
        description="WooCommerce attribute ID",
    )


class AttributeDefCreate(AttributeDefBase):
    """Schema for creating an attribute definition."""


class AttributeDefUpdate(BaseModel):
    """Schema for updating an attribute definition."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: Literal["text", "select", "number"] | None = Field(default=None)
    allowed_values: list[str] | None = Field(default=None)
    woo_attribute_id: int | None = Field(default=None)


class AttributeDefRead(BaseModel):
    """Schema for attribute definition serialization."""

    id: int
    name: str
    type: str
    allowed_values: list[str] | None = None
    woo_attribute_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Product Attribute Schemas ---
class ProductAttributeInput(BaseModel):
    """Schema for assigning an attribute to a product."""

    attribute_id: int = Field(..., description="AttributeDef ID")
    value: str = Field(..., description="Assigned attribute value")


class ProductAttributeValue(BaseModel):
    """Schema for reading product attribute value with metadata."""

    attribute_id: int
    attribute_name: str
    attribute_type: str
    value: str

    model_config = ConfigDict(from_attributes=True)


# --- Product Schemas ---
class ProductBase(BaseModel):
    """Base schema for product attributes."""

    sku: str = Field(..., min_length=1, max_length=100, description="Unique SKU")
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    description: str | None = Field(default=None, description="Detailed description")
    price: float = Field(default=0.0, ge=0.0, description="Product price")
    stock: int = Field(default=0, ge=0, description="Available stock quantity")
    category_id: int | None = Field(default=None, description="Category ID")
    status: str = Field(
        default="draft", max_length=50, description="Product status (draft/active/archived)"
    )
    woo_id: int | None = Field(default=None, description="WooCommerce product ID")
    health_score: int | None = Field(
        default=None, ge=0, le=100, description="Catalog health score (0-100)"
    )


class ProductCreate(ProductBase):
    """Schema for creating a new product."""

    attributes: list[ProductAttributeInput] = Field(
        default_factory=list,
        description="Initial attributes for product",
    )


class ProductUpdate(BaseModel):
    """Schema for updating an existing product."""

    sku: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    price: float | None = Field(default=None, ge=0.0)
    stock: int | None = Field(default=None, ge=0)
    category_id: int | None = Field(default=None)
    status: str | None = Field(default=None, max_length=50)
    woo_id: int | None = Field(default=None)
    health_score: int | None = Field(default=None, ge=0, le=100)
    attributes: list[ProductAttributeInput] | None = Field(
        default=None,
        description="If provided, replaces existing product attributes",
    )


class ProductRead(ProductBase):
    """Schema for reading a product."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductDetailRead(ProductRead):
    """Schema for reading a product with category and attributes included."""

    category: CategoryRead | None = None
    attributes: list[ProductAttributeValue] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    """Paginated product list response."""

    items: list[ProductDetailRead]
    total: int
    offset: int
    limit: int
