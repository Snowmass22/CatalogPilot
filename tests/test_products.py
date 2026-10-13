"""Tests for Product CRUD operations."""

from fastapi.testclient import TestClient


def test_create_product_basic(client: TestClient) -> None:
    """Test creating a minimal product without attributes."""
    payload = {
        "sku": "TEE-BASIC-001",
        "name": "Basic Tee",
        "description": "A simple everyday t-shirt.",
        "price": 19.99,
        "stock": 50,
        "status": "draft",
    }
    response = client.post("/api/products", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "TEE-BASIC-001"
    assert data["name"] == "Basic Tee"
    assert data["price"] == 19.99
    assert data["stock"] == 50
    assert data["status"] == "draft"
    assert "id" in data


def test_create_product_with_category_and_attributes(client: TestClient) -> None:
    """Test creating product with associated category and validated attributes."""
    # 1. Setup category
    cat = client.post("/api/categories", json={"name": "Hoodies"}).json()

    # 2. Setup attributes
    color_attr = client.post(
        "/api/attributes",
        json={"name": "Color", "type": "select", "allowed_values": ["Black", "Grey"]},
    ).json()
    material_attr = client.post(
        "/api/attributes",
        json={"name": "Material", "type": "text"},
    ).json()

    # 3. Create product
    payload = {
        "sku": "HOODIE-PRO-01",
        "name": "Pro Fleece Hoodie",
        "description": "Fleece hoodie with kangaroo pocket.",
        "price": 79.0,
        "stock": 20,
        "category_id": cat["id"],
        "status": "active",
        "health_score": 90,
        "attributes": [
            {"attribute_id": color_attr["id"], "value": "Black"},
            {"attribute_id": material_attr["id"], "value": "Cotton Fleece"},
        ],
    }
    response = client.post("/api/products", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["category"]["name"] == "Hoodies"
    assert len(data["attributes"]) == 2
    attr_names = {a["attribute_name"]: a["value"] for a in data["attributes"]}
    assert attr_names["Color"] == "Black"
    assert attr_names["Material"] == "Cotton Fleece"


def test_create_product_duplicate_sku(client: TestClient) -> None:
    """Test that creating a product with duplicate SKU fails with 409."""
    client.post("/api/products", json={"sku": "DUPLICATE-SKU", "name": "First"})
    dup_resp = client.post("/api/products", json={"sku": "DUPLICATE-SKU", "name": "Second"})
    assert dup_resp.status_code == 409


def test_create_product_invalid_category(client: TestClient) -> None:
    """Test that providing a non-existent category_id returns 404."""
    response = client.post(
        "/api/products",
        json={"sku": "CAT-FAIL-01", "name": "Fail", "category_id": 99999},
    )
    assert response.status_code == 404


def test_create_product_invalid_attribute_def(client: TestClient) -> None:
    """Test that non-existent attribute_id returns 404."""
    response = client.post(
        "/api/products",
        json={
            "sku": "ATTR-FAIL-01",
            "name": "Fail",
            "attributes": [{"attribute_id": 99999, "value": "Val"}],
        },
    )
    assert response.status_code == 404


def test_create_product_invalid_select_value(client: TestClient) -> None:
    """Test that invalid value for select attribute returns 422."""
    color_attr = client.post(
        "/api/attributes",
        json={"name": "Color", "type": "select", "allowed_values": ["Red", "Blue"]},
    ).json()

    response = client.post(
        "/api/products",
        json={
            "sku": "SELECT-FAIL-01",
            "name": "Fail",
            "attributes": [{"attribute_id": color_attr["id"], "value": "Neon Yellow"}],
        },
    )
    assert response.status_code == 422


def test_get_product_detail(client: TestClient) -> None:
    """Test retrieving product details by ID."""
    created = client.post("/api/products", json={"sku": "GET-01", "name": "Product 1"}).json()
    response = client.get(f"/api/products/{created['id']}")
    assert response.status_code == 200
    assert response.json()["sku"] == "GET-01"


def test_get_product_not_found(client: TestClient) -> None:
    """Test retrieving non-existent product returns 404."""
    response = client.get("/api/products/9999")
    assert response.status_code == 404


def test_list_products_search_and_filters(client: TestClient) -> None:
    """Test listing products with text search and filtering."""
    cat1 = client.post("/api/categories", json={"name": "T-Shirts"}).json()
    cat2 = client.post("/api/categories", json={"name": "Hats"}).json()

    client.post(
        "/api/products",
        json={
            "sku": "TEE-ALPHA",
            "name": "Alpha Tee",
            "category_id": cat1["id"],
            "status": "active",
            "health_score": 90,
        },
    )
    client.post(
        "/api/products",
        json={
            "sku": "TEE-BETA",
            "name": "Beta Tee",
            "category_id": cat1["id"],
            "status": "draft",
            "health_score": 50,
        },
    )
    client.post(
        "/api/products",
        json={
            "sku": "HAT-GAMMA",
            "name": "Gamma Hat",
            "category_id": cat2["id"],
            "status": "active",
            "health_score": 80,
        },
    )

    # 1. Total count
    resp = client.get("/api/products")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    # 2. Search query by name
    search_resp = client.get("/api/products?query=Alpha")
    assert search_resp.json()["total"] == 1
    assert search_resp.json()["items"][0]["sku"] == "TEE-ALPHA"

    # 3. Filter by category
    cat_resp = client.get(f"/api/products?category_id={cat1['id']}")
    assert cat_resp.json()["total"] == 2

    # 4. Filter by status
    status_resp = client.get("/api/products?status=active")
    assert status_resp.json()["total"] == 2

    # 5. Filter by min health score
    health_resp = client.get("/api/products?min_health_score=85")
    assert health_resp.json()["total"] == 1
    assert health_resp.json()["items"][0]["sku"] == "TEE-ALPHA"


def test_update_product(client: TestClient) -> None:
    """Test updating product fields and replacing attributes."""
    color_attr = client.post(
        "/api/attributes",
        json={"name": "Color", "type": "select", "allowed_values": ["Black", "White"]},
    ).json()

    product = client.post(
        "/api/products",
        json={"sku": "UPD-01", "name": "Original", "price": 10.0},
    ).json()

    update_payload = {
        "name": "Updated Name",
        "price": 25.0,
        "attributes": [{"attribute_id": color_attr["id"], "value": "White"}],
    }
    response = client.put(f"/api/products/{product['id']}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["price"] == 25.0
    assert len(data["attributes"]) == 1
    assert data["attributes"][0]["value"] == "White"


def test_delete_product(client: TestClient) -> None:
    """Test deleting product."""
    product = client.post("/api/products", json={"sku": "DEL-01", "name": "To Delete"}).json()
    del_resp = client.delete(f"/api/products/{product['id']}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True}

    get_resp = client.get(f"/api/products/{product['id']}")
    assert get_resp.status_code == 404
