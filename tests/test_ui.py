"""Tests for server-rendered UI endpoints, HTMX partials, and tab interactions (PRD Pillar A-C, ADR-0008)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.adapters.store_port import _mock_store_instance


def test_ui_index_html(client: TestClient) -> None:
    """Test that GET / returns the main single-page UI HTML with all 4 tabs."""
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    html = response.text
    assert "CatalogPilot" in html
    assert "Agentic PIM" in html
    assert "Dashboard" in html
    assert "Catalog" in html
    assert "AI Import" in html
    assert "Sync & Rollback" in html
    assert "tailwindcss" in html
    assert "htmx.org" in html


def test_ui_index_json_fallback(client: TestClient) -> None:
    """Test backwards-compatibility JSON fallback for API clients on GET /."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CatalogPilot"
    assert "docs" in data


def test_ui_dashboard_partial(client: TestClient) -> None:
    """Test Dashboard HTMX partial rendering health score, distribution, and issues."""
    response = client.get("/ui/partials/dashboard")
    assert response.status_code == 200
    html = response.text
    assert "Catalog Health Score" in html
    assert "Score Distribution" in html
    assert "Detected Issue Chips" in html


def test_ui_dashboard_recompute(client: TestClient) -> None:
    """Test recomputing health scores via Dashboard partial button."""
    response = client.post("/ui/partials/dashboard/recompute")
    assert response.status_code == 200
    html = response.text
    assert "Catalog Health Score" in html


def test_ui_catalog_partial_and_search(client: TestClient) -> None:
    """Test Catalog HTMX partial table and live search filtering."""
    # Create product to ensure non-empty catalog
    client.post(
        "/api/products",
        json={"sku": "UI-CAT-001", "name": "UI Test Fleece", "price": 45.0, "stock": 12},
    )

    # 1. Unfiltered catalog partial
    resp1 = client.get("/ui/partials/catalog")
    assert resp1.status_code == 200
    assert "UI-CAT-001" in resp1.text
    assert "UI Test Fleece" in resp1.text

    # 2. Filtered search
    resp2 = client.get("/ui/partials/catalog?query=Fleece")
    assert resp2.status_code == 200
    assert "UI-CAT-001" in resp2.text

    # 3. Filter with no match
    resp3 = client.get("/ui/partials/catalog?query=NonExistentProductQuery123")
    assert resp3.status_code == 200
    assert "No products found matching your search" in resp3.text


def test_ui_import_preview_with_sample_and_commit(client: TestClient) -> None:
    """Test Import preview loading sample dirty CSV and committing."""
    # 1. Preview using sample dirty CSV
    preview_resp = client.post("/ui/partials/import/preview?use_sample=true")
    assert preview_resp.status_code == 200
    html = preview_resp.text
    assert (
        "AI Ingestion &amp; Attribute Normalization" in html
        or "AI Ingestion & Attribute Normalization" in html
    )
    assert "Inferred Column Mappings" in html
    assert "Before / After Normalizations" in html
    assert "Confirm &amp; Commit" in html or "Confirm & Commit" in html

    # 2. Commit a payload
    payload = {
        "items": [
            {
                "sku": "UI-IMP-001",
                "name": "Imported Product via UI",
                "price": 39.99,
                "stock": 15,
            }
        ],
        "upsert": True,
    }
    commit_resp = client.post(
        "/ui/partials/import/commit",
        data={"payload_json": json.dumps(payload)},
    )
    assert commit_resp.status_code == 200
    assert "Import Committed Successfully" in commit_resp.text
    assert "HX-Trigger" in commit_resp.headers
    assert "refreshCatalog" in commit_resp.headers["HX-Trigger"]


def test_ui_sync_plan_execute_and_rollback(client: TestClient) -> None:
    """Test Sync tab lifecycle: generate plan, approve/execute, and time machine rollback."""
    _mock_store_instance.clear()

    # 1. Ensure product exists
    client.post(
        "/api/products",
        json={"sku": "UI-SYNC-001", "name": "Sync UI Test", "price": 60.0, "stock": 5},
    )

    # 2. Plan Sync
    plan_resp = client.post("/ui/partials/sync/plan")
    assert plan_resp.status_code == 200
    plan_html = plan_resp.text
    assert "Sync Plan #" in plan_html
    assert (
        "Approve &amp; Execute Sync Plan" in plan_html or "Approve & Execute Sync Plan" in plan_html
    )

    # Extract plan ID from plan_resp or DB
    runs_resp = client.get("/ui/partials/sync/runs")
    assert runs_resp.status_code == 200

    # 3. Create plan via API to get exact ID for execution test
    api_plan = client.post("/api/sync/plan").json()
    exec_resp = client.post(f"/ui/partials/sync/{api_plan['id']}/execute")
    assert exec_resp.status_code == 200
    assert "Plan Executed Successfully" in exec_resp.text
    assert "HX-Trigger" in exec_resp.headers
    assert "refreshRuns" in exec_resp.headers["HX-Trigger"]

    # 4. Check runs history shows new run
    runs_resp2 = client.get("/ui/partials/sync/runs")
    assert runs_resp2.status_code == 200
    assert "Rollback Run" in runs_resp2.text

    # 5. Rollback the run
    runs = client.get("/api/sync/runs").json()
    run_id = runs[0]["id"]
    rollback_resp = client.post(f"/ui/partials/sync/runs/{run_id}/rollback")
    assert rollback_resp.status_code == 200
    assert "Rolled back" in rollback_resp.text
