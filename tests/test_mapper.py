"""Tests for Mapper Agent, deterministic fallback, and price/stock cleaning (Rule 6, ADR-0004)."""

from unittest.mock import MagicMock

from app.adapters.llm_port import LLMError
from app.agents.mapper import (
    ColumnMapping,
    MapperAgent,
    clean_price_string,
    clean_stock_string,
)


def test_clean_price_string() -> None:
    """Test deterministic price parsing without LLM involvement."""
    assert clean_price_string("$1,299.00") == 1299.0
    assert clean_price_string(" $65.50 ") == 65.50
    assert clean_price_string("£24.99") == 24.99
    assert clean_price_string("120.00 USD") == 120.0
    assert clean_price_string(45.0) == 45.0
    assert clean_price_string(None) == 0.0
    assert clean_price_string("N/A") == 0.0


def test_clean_stock_string() -> None:
    """Test deterministic stock parsing."""
    assert clean_stock_string("40") == 40
    assert clean_stock_string(" 100 ") == 100
    assert clean_stock_string(25) == 25
    assert clean_stock_string("N/A") == 0
    assert clean_stock_string(None) == 0


def test_mapper_agent_rule_fallback_on_messy_headers() -> None:
    """Test that MapperAgent correctly maps messy supplier headers via deterministic fallback."""
    agent = MapperAgent()  # Uses FixtureLLMAdapter which will trigger rule-based fallback

    headers = [
        "Item_Ref",
        "Prod_Title",
        "Details",
        "MSRP",
        "Qty_Avail",
        "Clr",
        "Sz",
        "Material_Type",
        "Cat_Name",
    ]
    sample_rows = [
        {
            "Item_Ref": "SUP-HOOD-001",
            "Prod_Title": "Vintage Fleece",
            "Details": "Warm fleece",
            "MSRP": "$65.00",
            "Qty_Avail": "40",
            "Clr": "blk",
            "Sz": "x-large",
            "Material_Type": "Cotton",
            "Cat_Name": "Hoodies",
        }
    ]
    attr_defs = [
        {"name": "Color", "type": "select"},
        {"name": "Size", "type": "select"},
        {"name": "Material", "type": "text"},
    ]

    result = agent.infer_mapping(
        headers=headers,
        sample_rows=sample_rows,
        attribute_defs=attr_defs,
        known_categories=["Hoodies", "T-Shirts"],
    )

    mapping = result.mapping
    assert mapping.sku_column == "Item_Ref"
    assert mapping.name_column == "Prod_Title"
    assert mapping.description_column == "Details"
    assert mapping.price_column == "MSRP"
    assert mapping.stock_column == "Qty_Avail"
    assert mapping.category_column == "Cat_Name"

    # Verify attribute mapping
    assert mapping.attribute_columns["Clr"] == "Color"
    assert mapping.attribute_columns["Sz"] == "Size"
    assert mapping.attribute_columns["Material_Type"] == "Material"

    # Verify normalizations
    assert result.attribute_normalizations["Color"]["blk"] == "Black"
    assert result.attribute_normalizations["Size"]["x-large"] == "XL"


def test_mapper_agent_rejects_hallucinated_columns_and_falls_back() -> None:
    """Test that if LLM returns columns that do not exist in CSV, the agent falls back safely."""
    mock_llm = MagicMock()
    # LLM returns hallucinated column names
    hallucinated_mapping = ColumnMapping(
        sku_column="FAKE_SKU",
        name_column="FAKE_NAME",
        price_column="FAKE_PRICE",
        stock_column="FAKE_STOCK",
    )
    from app.agents.mapper import MapperResult

    mock_llm.generate.return_value = MapperResult(
        mapping=hallucinated_mapping,
        attribute_normalizations={},
        confidence=0.5,
    )

    agent = MapperAgent(llm_adapter=mock_llm)
    headers = ["Item_Ref", "Prod_Title", "MSRP", "Qty_Avail"]
    result = agent.infer_mapping(headers, [], [])

    # Must fall back to true headers
    assert result.mapping.sku_column == "Item_Ref"
    assert result.mapping.name_column == "Prod_Title"


def test_mapper_agent_falls_back_on_llm_exception() -> None:
    """Test that if LLM raises LLMError, deterministic rules take over immediately."""
    mock_llm = MagicMock()
    mock_llm.generate.side_effect = LLMError("API quota exhausted")

    agent = MapperAgent(llm_adapter=mock_llm)
    headers = ["sku", "title", "price", "stock"]
    result = agent.infer_mapping(headers, [], [])

    assert result.mapping.sku_column == "sku"
    assert result.mapping.name_column == "title"
    assert result.confidence > 0.0
