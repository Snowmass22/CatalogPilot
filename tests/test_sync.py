"""Integration tests for Sync Plan, Idempotent Execution, and Rollback Time Machine (PRD Pillar C, ADR-0003, ADR-0006)."""

from fastapi.testclient import TestClient

from app.adapters.store_port import _mock_store_instance


def test_sync_idempotency_e2e(client: TestClient) -> None:
    """Integration Test: Import -> Plan -> Execute -> Re-plan shows zero changes (Idempotency proof)."""
    # 0. Reset mock store state
    _mock_store_instance.clear()

    # 1. Import sample products
    import_payload = {
        "items": [
            {
                "sku": "SYNC-TEST-001",
                "name": "Classic Vintage Hoodie",
                "description": "Premium fleece hoodie",
                "price": 65.0,
                "stock": 30,
                "category_name": "Hoodies",
            },
            {
                "sku": "SYNC-TEST-002",
                "name": "Everyday Crew Tee",
                "description": "100% cotton crewneck",
                "price": 28.0,
                "stock": 80,
                "category_name": "T-Shirts",
            },
        ],
        "upsert": True,
    }
    import_resp = client.post("/api/imports/commit", json=import_payload)
    assert import_resp.status_code == 200
    assert import_resp.json()["imported"] == 2

    # 2. Build initial Sync Plan
    plan_resp = client.post("/api/sync/plan")
    assert plan_resp.status_code == 201
    plan_data = plan_resp.json()
    plan_id = plan_data["id"]

    # Initial plan should propose 2 creates and 0 updates
    assert plan_data["summary"]["create"] == 2
    assert plan_data["summary"]["update"] == 0
    assert plan_data["summary"]["no_change"] == 0

    # 3. Approve and Execute the Sync Plan
    exec_resp = client.post(f"/api/sync/{plan_id}/execute")
    assert exec_resp.status_code == 200
    run_data = exec_resp.json()
    assert run_data["status"] == "success"
    assert run_data["snapshots_count"] == 2

    # Verify products in catalog now have woo_id assigned
    prods_resp = client.get("/api/products")
    for prod in prods_resp.json()["items"]:
        if prod["sku"] in ["SYNC-TEST-001", "SYNC-TEST-002"]:
            assert prod["woo_id"] is not None

    # 4. RE-PLAN: Must show ZERO changes!
    replan_resp = client.post("/api/sync/plan")
    assert replan_resp.status_code == 201
    replan_data = replan_resp.json()

    assert replan_data["summary"]["create"] == 0, "Idempotency violated: expected 0 creates"
    assert replan_data["summary"]["update"] == 0, "Idempotency violated: expected 0 updates"
    assert replan_data["summary"]["no_change"] == 2, "Expected all products to have no_change"


def test_sync_field_diff_and_update(client: TestClient) -> None:
    """Test field-level diff detection and selective update."""
    _mock_store_instance.clear()

    # Create product and execute initial sync
    prod = client.post(
        "/api/products",
        json={"sku": "DIFF-001", "name": "Original Name", "price": 40.0, "stock": 10},
    ).json()

    plan1 = client.post("/api/sync/plan").json()
    client.post(f"/api/sync/{plan1['id']}/execute")

    # Update product price in PIM
    client.put(f"/api/products/{prod['id']}", json={"price": 48.0, "stock": 15})

    # Plan again: should detect update with field-level diff
    plan2 = client.post("/api/sync/plan").json()
    assert plan2["summary"]["update"] == 1
    assert plan2["summary"]["create"] == 0

    item = plan2["items"][0]
    assert item["action"] == "update"
    assert item["diff"]["price"]["before"] == 40.0
    assert item["diff"]["price"]["after"] == 48.0


def test_sync_rollback_flow(client: TestClient) -> None:
    """Test Time Machine rollback restoring prior state."""
    _mock_store_instance.clear()

    # 1. Create and sync product
    create_resp = client.post(
        "/api/products",
        json={"sku": "ROLL-001", "name": "To Rollback", "price": 50.0, "stock": 20},
    )
    assert create_resp.status_code == 201

    plan = client.post("/api/sync/plan").json()
    exec_run = client.post(f"/api/sync/{plan['id']}/execute").json()
    run_id = exec_run["id"]

    # Verify product in mock store
    store_prod = _mock_store_instance.get_product_by_sku("ROLL-001")
    assert store_prod is not None

    # 2. Trigger Rollback
    rollback_resp = client.post(f"/api/sync/runs/{run_id}/rollback")
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["status"] == "rolled_back"
    assert rollback_resp.json()["restored_items"] == 1

    # Product should now be removed from store (newly created was deleted)
    assert _mock_store_instance.get_product_by_sku("ROLL-001") is None

    # Listing runs should show run marked as rolled_back
    runs_resp = client.get("/api/sync/runs")
    assert any(r["id"] == run_id and r["status"] == "rolled_back" for r in runs_resp.json())
