"""Mapper Agent: infers CSV column mapping and normalizes attributes (PRD Pillar A, B)."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.adapters.llm_port import LLMError, LLMPort, get_llm_adapter
from app.domain.schemas import ColumnMapping

logger = logging.getLogger(__name__)


class MapperResult(BaseModel):
    """Output from the Mapper Agent."""

    mapping: ColumnMapping
    attribute_normalizations: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Maps PIM attribute name -> (raw value -> canonical value)",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str = Field(default="Mapping inferred successfully.")


class MapperAgent:
    """Agent that analyzes CSV headers, sample rows, and PIM schema to map and normalize."""

    def __init__(self, llm_adapter: LLMPort | None = None) -> None:
        self.llm = llm_adapter or get_llm_adapter()

    def infer_mapping(
        self,
        headers: list[str],
        sample_rows: list[dict[str, str]],
        attribute_defs: list[dict[str, Any]],
        known_categories: list[str] | None = None,
    ) -> MapperResult:
        """Infer column mapping and value normalizations via LLM, falling back to rule-based."""
        prompt = self._build_prompt(headers, sample_rows, attribute_defs, known_categories or [])

        system_instruction = (
            "You are CatalogPilot's Mapper Agent. Your task is to inspect CSV headers and sample rows "
            "from supplier spreadsheets and map them to the PIM catalog schema. "
            "Normalize raw attribute values like 'x-large' -> 'XL', 'blk' -> 'Black'. "
            "NEVER fabricate or generate numeric price, SKU, or stock numbers. "
            "Only produce the column names that correspond to those fields."
        )

        try:
            result = self.llm.generate(
                prompt=prompt,
                schema=MapperResult,
                system_instruction=system_instruction,
            )
            # Ensure valid mapped columns actually exist in headers
            if self._validate_columns_exist(result.mapping, headers):
                return result
            logger.warning(
                "LLM proposed column mapping with missing headers; using rule-based fallback."
            )
        except LLMError as e:
            logger.warning("LLM mapper failed (%s); using deterministic rule-based fallback.", e)

        # Fallback to deterministic rules
        return self._rule_based_fallback(headers, sample_rows, attribute_defs)

    @staticmethod
    def _validate_columns_exist(mapping: ColumnMapping, headers: list[str]) -> bool:
        """Verify that mapped columns exist in provided CSV headers."""
        header_set = set(headers)
        if mapping.sku_column not in header_set or mapping.name_column not in header_set:
            return False
        if mapping.price_column not in header_set or mapping.stock_column not in header_set:
            return False
        if mapping.category_column and mapping.category_column not in header_set:
            return False
        for col_name in mapping.attribute_columns:
            if col_name not in header_set:
                return False
        return True

    @staticmethod
    def _build_prompt(
        headers: list[str],
        sample_rows: list[dict[str, str]],
        attribute_defs: list[dict[str, Any]],
        known_categories: list[str],
    ) -> str:
        """Construct prompt for the LLM."""
        return f"""Inspect this supplier data and produce a ColumnMapping:

CSV Headers:
{headers}

Sample Rows (up to 5):
{sample_rows[:5]}

Target PIM Schema:
- Core Fields: sku (required), name (required), description (optional), price (required), stock (required), category (optional)
- Known Categories: {known_categories}
- Target Attribute Definitions:
{attribute_defs}

Return a JSON matching MapperResult schema with:
1. mapping: exactly which CSV column maps to sku, name, description, price, stock, category, and which columns map to attributes.
2. attribute_normalizations: mapping from raw values found in sample rows to canonical target values.
"""

    @staticmethod
    def _rule_based_fallback(
        headers: list[str],
        sample_rows: list[dict[str, str]],
        attribute_defs: list[dict[str, Any]],
    ) -> MapperResult:
        """Deterministic rule-based mapping engine that never fails."""
        header_map: dict[str, str] = {
            h.lower().strip().replace(" ", "_").replace("#", "num"): h for h in headers
        }

        def find_col(candidates: list[str]) -> str | None:
            for c in candidates:
                for norm_h, orig_h in header_map.items():
                    if c in norm_h:
                        return orig_h
            return None

        sku_col = (
            find_col(["item_ref", "sku", "item_num", "product_id", "item", "code", "id"])
            or headers[0]
        )
        name_col = (
            find_col(["prod_title", "title", "product_name", "item_name", "name"]) or headers[1]
        )
        desc_col = find_col(["details", "description", "desc", "about"])
        price_col = find_col(["mrp", "msrp", "price", "retail", "cost"]) or (
            headers[3] if len(headers) > 3 else headers[0]
        )
        stock_col = find_col(["qty_avail", "qty", "stock", "quantity", "avail", "count"]) or (
            headers[4] if len(headers) > 4 else headers[0]
        )
        cat_col = find_col(["cat_name", "category", "cat"])

        # Attributes detection
        attr_cols: dict[str, str] = {}
        target_attr_names = {a.get("name", "").lower(): a.get("name", "") for a in attribute_defs}

        for norm_h, orig_h in header_map.items():
            if norm_h in ["clr", "color", "colour"]:
                target_name = target_attr_names.get("color", "Color")
                attr_cols[orig_h] = target_name
            elif norm_h in ["sz", "size"]:
                target_name = target_attr_names.get("size", "Size")
                attr_cols[orig_h] = target_name
            elif "material" in norm_h:
                target_name = target_attr_names.get("material", "Material")
                attr_cols[orig_h] = target_name

        # Normalization dictionary
        normalizations: dict[str, dict[str, str]] = {
            "Color": {
                "blk": "Black",
                "black": "Black",
                "wht": "White",
                "white": "White",
                "nav": "Navy",
                "navy": "Navy",
                "navy blue": "Navy",
                "heather grey": "Heather Grey",
                "olive drab": "Olive",
                "olive": "Olive",
                "burgundy": "Burgundy",
            },
            "Size": {
                "x-large": "XL",
                "xl": "XL",
                "sml": "S",
                "small": "S",
                "s": "S",
                "med": "M",
                "medium": "M",
                "m": "M",
                "l": "L",
                "large": "L",
                "2xl": "XXL",
                "xx-large": "XXL",
                "xxl": "XXL",
                "one size": "One Size",
            },
        }

        mapping = ColumnMapping(
            sku_column=sku_col,
            name_column=name_col,
            description_column=desc_col,
            price_column=price_col,
            stock_column=stock_col,
            category_column=cat_col,
            attribute_columns=attr_cols,
        )

        return MapperResult(
            mapping=mapping,
            attribute_normalizations=normalizations,
            confidence=0.92,
            notes="Inferred via deterministic heuristic mapping engine.",
        )


def clean_price_string(price_str: str | float | int | None) -> float:
    """Safely parse price values like '$1,299.00', ' 64.99 ', etc. (LLM never parses numbers)."""
    if price_str is None:
        return 0.0
    if isinstance(price_str, (int, float)):
        return float(price_str)

    cleaned = str(price_str).strip()
    # Remove currency symbols and formatting commas
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def clean_stock_string(stock_str: str | int | float | None) -> int:
    """Safely parse integer stock values."""
    if stock_str is None:
        return 0
    if isinstance(stock_str, int):
        return stock_str
    if isinstance(stock_str, float):
        return int(stock_str)

    cleaned = str(stock_str).strip()
    cleaned = re.sub(r"[^\d]", "", cleaned)
    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0
