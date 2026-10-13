"""Tests for HealthScoreCalculator, HealthService, and QualityAgent (ADR-0007)."""

from fastapi.testclient import TestClient

from app.agents.quality import QualityAgent
from app.domain.health import HealthScoreCalculator


def test_health_score_perfect_product() -> None:
    """Test a product satisfying all 6 quality rules receives 100 points."""
    product_data = {
        "name": "Classic Heavyweight Fleece Hoodie",
        "description": "Ultra-soft 450 GSM fleece hoodie with ribbed cuffs and large front kangaroo pocket for comfort.",
        "price": 64.99,
        "stock": 40,
        "image_url": "https://example.com/hoodie.jpg",
        "attributes": {"Color": "Black", "Size": "XL"},
    }

    eval_result = HealthScoreCalculator.evaluate(
        product_data=product_data,
        category_name="Hoodies",
        is_duplicate=False,
    )

    assert eval_result.score == 100
    assert len(eval_result.issues) == 0
    assert eval_result.breakdown.required_attributes == 30
    assert eval_result.breakdown.description == 20
    assert eval_result.breakdown.images == 20
    assert eval_result.breakdown.pricing_sanity == 15
    assert eval_result.breakdown.naming == 10
    assert eval_result.breakdown.duplicates == 5


def test_health_score_missing_attributes_and_images() -> None:
    """Test deduction for missing required category attributes and missing image."""
    product_data = {
        "name": "Generic Item",
        "description": "Short desc",  # < 50 chars -> 10 pts
        "price": 20.0,
        "stock": 10,
        "attributes": {},  # Missing Color and Size for Hoodies -> 0 pts
    }

    eval_result = HealthScoreCalculator.evaluate(
        product_data=product_data,
        category_name="Hoodies",
        is_duplicate=False,
    )

    # 0 (attr) + 10 (desc) + 0 (img) + 15 (price) + 10 (name) + 5 (dup) = 40
    assert eval_result.score == 40
    assert any("Missing required attribute" in i for i in eval_result.issues)
    assert any("Missing product image" in i for i in eval_result.issues)
    assert any("Short description" in i for i in eval_result.issues)


def test_health_score_pricing_anomalies() -> None:
    """Test price zero and price over $1,000 penalties."""
    # Zero price
    zero_eval = HealthScoreCalculator.evaluate(
        product_data={"name": "Free Item", "price": 0.0, "description": "A" * 60, "images": True},
        category_name="Accessories",
    )
    assert zero_eval.breakdown.pricing_sanity == 0
    assert any("greater than $0.00" in i for i in zero_eval.issues)

    # Extreme price
    extreme_eval = HealthScoreCalculator.evaluate(
        product_data={
            "name": "Luxury Item",
            "price": 2500.0,
            "description": "B" * 60,
            "images": True,
        },
        category_name="Accessories",
    )
    assert extreme_eval.breakdown.pricing_sanity == 5  # Partial credit
    assert any("High price check needed" in i for i in extreme_eval.issues)


def test_health_score_duplicate_penalty() -> None:
    """Test duplicate flag deduction."""
    eval_result = HealthScoreCalculator.evaluate(
        product_data={
            "name": "Duplicate Tee",
            "price": 25.0,
            "description": "C" * 60,
            "images": True,
        },
        category_name="Accessories",
        is_duplicate=True,
    )
    assert eval_result.breakdown.duplicates == 0
    assert any("Duplicate" in i for i in eval_result.issues)


def test_quality_agent_plain_language_advice() -> None:
    """Test QualityAgent converts technical issues to actionable suggestions."""
    agent = QualityAgent()
    issues = [
        "Missing product image",
        "Missing required attribute(s): Color, Size",
        "Short description (< 50 characters)",
    ]
    advice = agent.analyze("Vintage Hoodie", score=45, issues=issues, category="Hoodies")

    assert "Vintage Hoodie" in advice.summary
    assert len(advice.suggestions) >= 2
    assert any("image" in s.lower() for s in advice.suggestions)


def test_catalog_health_endpoint_empty(client: TestClient) -> None:
    """Test GET /api/health when catalog is empty."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] == 0
    assert data["average_score"] == 0.0


def test_catalog_health_endpoint_with_products(client: TestClient) -> None:
    """Test GET /api/health returns average score, distribution, and top issues."""
    # Create products with varying quality
    client.post(
        "/api/products",
        json={
            "sku": "PROD-PERFECT",
            "name": "Perfect High Quality Jacket",
            "description": "Full lengthy description detailing premium material and fit for every customer.",
            "price": 120.0,
            "stock": 10,
        },
    )
    client.post(
        "/api/products",
        json={
            "sku": "PROD-POOR",
            "name": "Bad",
            "price": 0.0,
            "stock": 0,
        },
    )

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] == 2
    assert data["average_score"] > 0
    assert "score_distribution" in data
    assert len(data["top_issues"]) > 0

    # Test recompute endpoint
    recompute_resp = client.post("/api/health/recompute")
    assert recompute_resp.status_code == 200
    assert recompute_resp.json()["total_products"] == 2
