"""Deterministic Catalog Health Score engine (PRD Pillar A, ADR-0007)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthBreakdown(BaseModel):
    """Breakdown of points awarded per category."""

    required_attributes: int = Field(default=0, ge=0, le=30)
    description: int = Field(default=0, ge=0, le=20)
    images: int = Field(default=0, ge=0, le=20)
    pricing_sanity: int = Field(default=0, ge=0, le=15)
    naming: int = Field(default=0, ge=0, le=10)
    duplicates: int = Field(default=0, ge=0, le=5)


class HealthEvaluation(BaseModel):
    """Result of health score calculation with explainable issues."""

    score: int = Field(..., ge=0, le=100, description="Total health score (0-100)")
    issues: list[str] = Field(default_factory=list, description="Explainable data quality issues")
    breakdown: HealthBreakdown = Field(default_factory=HealthBreakdown)


# Category-specific required attributes (PRD B4)
CATEGORY_REQUIRED_ATTRIBUTES: dict[str, list[str]] = {
    "apparel": ["Color", "Size"],
    "hoodies": ["Color", "Size"],
    "t-shirts": ["Color", "Size"],
    "accessories": ["Material"],
}


class HealthScoreCalculator:
    """Calculates deterministic health scores using fixed weights (ADR-0007)."""

    WEIGHT_REQUIRED_ATTRIBUTES = 30
    WEIGHT_DESCRIPTION = 20
    WEIGHT_IMAGES = 20
    WEIGHT_PRICING_SANITY = 15
    WEIGHT_NAMING = 10
    WEIGHT_DUPLICATES = 5

    @classmethod
    def evaluate(
        cls,
        product_data: dict[str, Any],
        category_name: str | None = None,
        is_duplicate: bool = False,
    ) -> HealthEvaluation:
        """Evaluate a product against 6 weighted quality rules."""
        issues: list[str] = []
        breakdown = HealthBreakdown()

        # 1. Required Attributes (30 points)
        breakdown.required_attributes = cls._evaluate_attributes(
            product_data.get("attributes", {}),
            category_name,
            issues,
        )

        # 2. Description (20 points)
        breakdown.description = cls._evaluate_description(
            product_data.get("description"),
            issues,
        )

        # 3. Images (20 points)
        breakdown.images = cls._evaluate_images(
            product_data,
            issues,
        )

        # 4. Pricing sanity (15 points)
        breakdown.pricing_sanity = cls._evaluate_pricing(
            product_data.get("price"),
            issues,
        )

        # 5. Naming (10 points)
        breakdown.naming = cls._evaluate_naming(
            product_data.get("name"),
            issues,
        )

        # 6. Duplicates (5 points)
        breakdown.duplicates = cls._evaluate_duplicates(
            is_duplicate,
            issues,
        )

        total_score = (
            breakdown.required_attributes
            + breakdown.description
            + breakdown.images
            + breakdown.pricing_sanity
            + breakdown.naming
            + breakdown.duplicates
        )

        return HealthEvaluation(
            score=max(0, min(100, total_score)),
            issues=issues,
            breakdown=breakdown,
        )

    @classmethod
    def _evaluate_attributes(
        cls,
        attributes: dict[str, str] | list[Any],
        category_name: str | None,
        issues: list[str],
    ) -> int:
        """Check presence of required attributes per category."""
        attr_dict: dict[str, str] = {}
        if isinstance(attributes, list):
            for a in attributes:
                if isinstance(a, dict):
                    name = a.get("attribute_name") or a.get("name")
                    val = a.get("value")
                    if name and val:
                        attr_dict[str(name).lower()] = str(val)
                elif hasattr(a, "attribute_name") and hasattr(a, "value"):
                    attr_dict[str(a.attribute_name).lower()] = str(a.value)
        elif isinstance(attributes, dict):
            attr_dict = {str(k).lower(): str(v) for k, v in attributes.items() if v}

        cat_key = (category_name or "").strip().lower()
        required = CATEGORY_REQUIRED_ATTRIBUTES.get(cat_key, [])

        if required:
            missing = [req for req in required if req.lower() not in attr_dict]
            if not missing:
                return cls.WEIGHT_REQUIRED_ATTRIBUTES
            missing_str = ", ".join(missing)
            issues.append(f"Missing required attribute(s): {missing_str}")
            # Partial credit if some required are present
            present_count = len(required) - len(missing)
            return int(cls.WEIGHT_REQUIRED_ATTRIBUTES * (present_count / len(required)))

        # Default rule: at least 1 attribute present gives full credit
        if attr_dict:
            return cls.WEIGHT_REQUIRED_ATTRIBUTES
        issues.append("No product attributes specified")
        return 0

    @classmethod
    def _evaluate_description(
        cls,
        description: str | None,
        issues: list[str],
    ) -> int:
        """Check description presence and length."""
        if not description or not str(description).strip():
            issues.append("Missing product description")
            return 0

        desc_len = len(str(description).strip())
        if desc_len >= 50:
            return cls.WEIGHT_DESCRIPTION
        issues.append("Short description (< 50 characters)")
        return 10  # Partial credit

    @classmethod
    def _evaluate_images(
        cls,
        product_data: dict[str, Any],
        issues: list[str],
    ) -> int:
        """Check if product has at least one valid image."""
        # Check explicit images field, URL in attributes, or image link in description
        has_image = bool(product_data.get("images") or product_data.get("image_url"))

        attrs = product_data.get("attributes", {})
        if isinstance(attrs, dict) and any("image" in k.lower() for k in attrs):
            has_image = True
        elif isinstance(attrs, list):
            for a in attrs:
                name = (
                    a.get("attribute_name", "")
                    if isinstance(a, dict)
                    else getattr(a, "attribute_name", "")
                )
                if "image" in str(name).lower():
                    has_image = True
                    break

        if has_image:
            return cls.WEIGHT_IMAGES
        issues.append("Missing product image")
        return 0

    @classmethod
    def _evaluate_pricing(
        cls,
        price: float | int | None,
        issues: list[str],
    ) -> int:
        """Check pricing sanity (> 0 and <= $1,000)."""
        if price is None or price <= 0:
            issues.append("Price must be greater than $0.00")
            return 0
        if price > 1000:
            issues.append("High price check needed (> $1,000)")
            return 5  # Partial credit
        return cls.WEIGHT_PRICING_SANITY

    @classmethod
    def _evaluate_naming(
        cls,
        name: str | None,
        issues: list[str],
    ) -> int:
        """Check product name length and formatting."""
        if not name or len(str(name).strip()) < 5:
            issues.append("Product name is too short (< 5 characters)")
            return 0
        return cls.WEIGHT_NAMING

    @classmethod
    def _evaluate_duplicates(
        cls,
        is_duplicate: bool,
        issues: list[str],
    ) -> int:
        """Check for duplicate SKU or title."""
        if is_duplicate:
            issues.append("Duplicate SKU or product name detected")
            return 0
        return cls.WEIGHT_DUPLICATES
