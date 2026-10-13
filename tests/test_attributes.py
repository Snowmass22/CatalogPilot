"""Tests for AttributeDef CRUD operations."""

from fastapi.testclient import TestClient


def test_create_attribute_def(client: TestClient) -> None:
    """Test creating attribute definition with allowed values."""
    payload = {
        "name": "Color",
        "type": "select",
        "allowed_values": ["Red", "Blue", "Green"],
    }
    response = client.post("/api/attributes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Color"
    assert data["type"] == "select"
    assert data["allowed_values"] == ["Red", "Blue", "Green"]
    assert "id" in data


def test_create_duplicate_attribute_name(client: TestClient) -> None:
    """Test that duplicate attribute name is rejected with 409."""
    client.post("/api/attributes", json={"name": "Size", "type": "text"})
    dup_resp = client.post("/api/attributes", json={"name": "Size", "type": "select"})
    assert dup_resp.status_code == 409


def test_get_attribute_def(client: TestClient) -> None:
    """Test getting attribute definition by ID."""
    created = client.post("/api/attributes", json={"name": "Material", "type": "text"}).json()
    response = client.get(f"/api/attributes/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Material"


def test_get_attribute_def_not_found(client: TestClient) -> None:
    """Test getting non-existent attribute returns 404."""
    response = client.get("/api/attributes/9999")
    assert response.status_code == 404


def test_list_attributes(client: TestClient) -> None:
    """Test listing all attribute definitions."""
    client.post("/api/attributes", json={"name": "Attr1", "type": "text"})
    client.post("/api/attributes", json={"name": "Attr2", "type": "text"})

    response = client.get("/api/attributes")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_update_attribute_def(client: TestClient) -> None:
    """Test updating attribute definition."""
    created = client.post(
        "/api/attributes",
        json={"name": "Season", "type": "select", "allowed_values": ["Summer"]},
    ).json()

    update_resp = client.put(
        f"/api/attributes/{created['id']}",
        json={"allowed_values": ["Summer", "Winter", "Spring", "Autumn"]},
    )
    assert update_resp.status_code == 200
    assert len(update_resp.json()["allowed_values"]) == 4


def test_delete_attribute_def(client: TestClient) -> None:
    """Test deleting attribute definition."""
    created = client.post("/api/attributes", json={"name": "Fit", "type": "text"}).json()
    del_resp = client.delete(f"/api/attributes/{created['id']}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True}

    get_resp = client.get(f"/api/attributes/{created['id']}")
    assert get_resp.status_code == 404
