"""Tests for Import preview and commit endpoints (PRD 1.7)."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def test_preview_messy_supplier_csv(client: TestClient) -> None:
    """Test POST /api/imports/preview with messy_supplier.csv."""
    csv_path = Path("sample_data/messy_supplier.csv")
    assert csv_path.exists(), "messy_supplier.csv must exist"

    with open(csv_path, "rb") as f:
        response = client.post(
            "/api/imports/preview",
            files={"file": ("messy_supplier.csv", f, "text/csv")},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["total_rows"] == 30
    mapping = data["mapping"]
    assert mapping["sku_column"] == "Item_Ref"
    assert mapping["name_column"] == "Prod_Title"
    assert mapping["price_column"] == "MSRP"
    assert mapping["stock_column"] == "Qty_Avail"
    assert mapping["attribute_columns"]["Clr"] == "Color"
    assert mapping["attribute_columns"]["Sz"] == "Size"

    # Duplicates in file
    assert "SUP-HOOD-001" in data["duplicate_skus_in_file"]
    assert "SUP-TEE-003" in data["duplicate_skus_in_file"]

    # Check preview items
    first_item = data["preview_items"][0]
    assert first_item["sku"] == "SUP-HOOD-001"
    assert first_item["price"] == 65.0
    assert first_item["stock"] == 40
    # Normalized attributes
    assert first_item["attributes"]["Color"] == "Black"  # "blk" normalized to "Black"
    assert first_item["attributes"]["Size"] == "XL"  # "x-large" normalized to "XL"

    # Row with $1,299.00 price should be parsed to 1299.0 with issue chip
    expensive_item = next(item for item in data["preview_items"] if item["sku"] == "SUP-HOOD-004")
    assert expensive_item["price"] == 1299.0
    assert any("High price" in issue for issue in expensive_item["issues"])


def test_preview_empty_csv_bad_request(client: TestClient) -> None:
    """Test POST /api/imports/preview with empty content returns 400."""
    response = client.post(
        "/api/imports/preview",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


def test_commit_import_items(client: TestClient) -> None:
    """Test POST /api/imports/commit persists items into the catalog."""
    payload: dict[str, Any] = {
        "items": [
            {
                "sku": "IMP-001",
                "name": "Imported Hoodie",
                "description": "Imported via AI mapper",
                "price": 49.99,
                "stock": 100,
                "category_name": "New Category",
                "attributes": {"Color": "Black", "Size": "XL"},
            },
            {
                "sku": "IMP-002",
                "name": "Imported Tee",
                "price": 25.0,
                "stock": 50,
                "category_name": "T-Shirts",
                "attributes": {"Color": "White"},
            },
        ],
        "upsert": True,
    }

    response = client.post("/api/imports/commit", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["imported"] == 2
    assert res_data["updated"] == 0
    assert res_data["errors"] == []

    # Verify created product in catalog
    prod_resp = client.get("/api/products?query=IMP-001")
    assert prod_resp.status_code == 200
    assert prod_resp.json()["total"] == 1
    prod = prod_resp.json()["items"][0]
    assert prod["sku"] == "IMP-001"
    assert prod["category"]["name"] == "New Category"
    assert len(prod["attributes"]) == 2

    # Second commit with updated stock (upsert)
    payload["items"][0]["stock"] = 150
    recommit_resp = client.post("/api/imports/commit", json=payload)
    assert recommit_resp.status_code == 200
    recommit_data = recommit_resp.json()
    assert recommit_data["imported"] == 0
    assert recommit_data["updated"] == 2

    # Check updated stock
    updated_prod = client.get(f"/api/products/{prod['id']}").json()
    assert updated_prod["stock"] == 150
