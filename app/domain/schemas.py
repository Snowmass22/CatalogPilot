"""Pydantic schemas for API requests, responses, and domain validation."""

from datetime import datetime
from typing import Any, Literal

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


# --- Import Schemas (Pillar A, Pillar B) ---
class ColumnMapping(BaseModel):
    """Mapping of CSV columns to PIM fields and attributes."""

    sku_column: str = Field(..., description="Column containing unique product SKU or ID")
    name_column: str = Field(..., description="Column containing product title or name")
    description_column: str | None = Field(
        default=None, description="Column containing description"
    )
    price_column: str = Field(..., description="Column containing product price")
    stock_column: str = Field(..., description="Column containing available stock quantity")
    category_column: str | None = Field(default=None, description="Column containing category name")
    attribute_columns: dict[str, str] = Field(
        default_factory=dict,
        description="Maps raw CSV column name -> PIM attribute name (e.g. {'Clr': 'Color'})",
    )


class ImportPreviewRow(BaseModel):
    """Normalized preview representation of a single CSV row."""

    row_index: int
    raw_data: dict[str, str]
    sku: str
    name: str
    description: str | None = None
    price: float = 0.0
    stock: int = 0
    category_name: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class ImportPreviewResponse(BaseModel):
    """Response returned by CSV import preview endpoint."""

    mapping: ColumnMapping
    attribute_normalizations: dict[str, dict[str, str]] = Field(default_factory=dict)
    total_rows: int
    preview_items: list[ImportPreviewRow]
    duplicate_skus_in_file: list[str] = Field(default_factory=list)
    existing_skus_in_db: list[str] = Field(default_factory=list)


class ImportCommitItem(BaseModel):
    """Item to be saved into catalog during import commit."""

    sku: str
    name: str
    description: str | None = None
    price: float = 0.0
    stock: int = 0
    category_name: str | None = None
    status: str = "active"
    attributes: dict[str, str] = Field(default_factory=dict)


class ImportCommitRequest(BaseModel):
    """Request payload to commit previewed import data."""

    items: list[ImportCommitItem]
    upsert: bool = Field(default=True, description="Update product if SKU already exists")


class ImportCommitResponse(BaseModel):
    """Summary of committed products."""

    imported: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# --- Catalog Health Schemas (PRD Pillar A, ADR-0007) ---
class ScoreDistribution(BaseModel):
    """Distribution of catalog products by health score range."""

    excellent_90_100: int = 0
    good_70_89: int = 0
    fair_50_69: int = 0
    poor_0_49: int = 0


class IssueCount(BaseModel):
    """Frequency count of an explainable catalog quality issue."""

    issue: str
    count: int


class CatalogHealthSummary(BaseModel):
    """Overall catalog health score summary returned by GET /api/health."""

    average_score: float
    total_products: int
    score_distribution: ScoreDistribution
    top_issues: list[IssueCount]
    advice_summary: str | None = None


# --- Sync & Time Machine Schemas (PRD Pillar C, ADR-0006) ---
class SyncItemRead(BaseModel):
    """Individual action item inside a sync plan."""

    id: int
    product_id: int
    action: str
    diff: dict[str, Any] = Field(default_factory=dict)
    status: str
    error: str | None = None


class SyncPlanRead(BaseModel):
    """Sync plan representation with field-level diffs."""

    id: int
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    status: str
    items: list[SyncItemRead] = Field(default_factory=list)


class SyncRunRead(BaseModel):
    """Sync execution run record."""

    id: int
    plan_id: int
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    snapshots_count: int = 0


class RollbackResponse(BaseModel):
    """Rollback execution response."""

    run_id: int
    status: str
    restored_items: int
    details: str
