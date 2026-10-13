"""Tests for Category CRUD operations."""

from fastapi.testclient import TestClient


def test_create_category(client: TestClient) -> None:
    """Test successful category creation."""
    response = client.post("/api/categories", json={"name": "Apparel", "parent_id": None})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Apparel"
    assert data["parent_id"] is None
    assert "id" in data


def test_create_child_category(client: TestClient) -> None:
    """Test creating child category with valid parent."""
    parent_resp = client.post("/api/categories", json={"name": "Apparel"})
    parent_id = parent_resp.json()["id"]

    child_resp = client.post("/api/categories", json={"name": "Hoodies", "parent_id": parent_id})
    assert child_resp.status_code == 201
    assert child_resp.json()["parent_id"] == parent_id


def test_create_category_invalid_parent(client: TestClient) -> None:
    """Test creating category with non-existent parent returns 404."""
    response = client.post("/api/categories", json={"name": "Ghost", "parent_id": 9999})
    assert response.status_code == 404


def test_get_category(client: TestClient) -> None:
    """Test retrieving category by ID."""
    created = client.post("/api/categories", json={"name": "Shoes"}).json()
    response = client.get(f"/api/categories/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Shoes"


def test_get_category_not_found(client: TestClient) -> None:
    """Test retrieving non-existent category returns 404."""
    response = client.get("/api/categories/9999")
    assert response.status_code == 404


def test_list_categories_and_filter(client: TestClient) -> None:
    """Test listing categories and filtering by parent_id."""
    parent = client.post("/api/categories", json={"name": "Electronics"}).json()
    client.post("/api/categories", json={"name": "Phones", "parent_id": parent["id"]})
    client.post("/api/categories", json={"name": "Laptops", "parent_id": parent["id"]})
    client.post("/api/categories", json={"name": "Books"})

    # List all
    all_resp = client.get("/api/categories")
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 4

    # Filter by parent
    filtered = client.get(f"/api/categories?parent_id={parent['id']}")
    assert filtered.status_code == 200
    assert len(filtered.json()) == 2
    assert {c["name"] for c in filtered.json()} == {"Phones", "Laptops"}


def test_update_category(client: TestClient) -> None:
    """Test updating category name."""
    cat = client.post("/api/categories", json={"name": "Old Name"}).json()
    update_resp = client.put(f"/api/categories/{cat['id']}", json={"name": "New Name"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "New Name"


def test_category_self_parent_cycle(client: TestClient) -> None:
    """Test that setting a category as its own parent is rejected."""
    cat = client.post("/api/categories", json={"name": "Cycle"}).json()
    resp = client.put(f"/api/categories/{cat['id']}", json={"parent_id": cat["id"]})
    assert resp.status_code == 422


def test_delete_category(client: TestClient) -> None:
    """Test deleting category."""
    cat = client.post("/api/categories", json={"name": "To Delete"}).json()
    del_resp = client.delete(f"/api/categories/{cat['id']}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True}

    # Verify deleted
    get_resp = client.get(f"/api/categories/{cat['id']}")
    assert get_resp.status_code == 404
