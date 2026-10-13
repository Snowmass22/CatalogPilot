"""Service managing catalog health scores and quality analytics (PRD Pillar A, ADR-0007)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlmodel import Session, select

from app.agents.quality import QualityAgent
from app.db.models import Category, Product, ProductAttribute
from app.domain.health import HealthEvaluation, HealthScoreCalculator
from app.domain.schemas import (
    CatalogHealthSummary,
    IssueCount,
    ScoreDistribution,
)


class HealthService:
    """Computes, updates, and aggregates catalog health quality metrics."""

    @staticmethod
    def evaluate_product(session: Session, product: Product) -> HealthEvaluation:
        """Calculate health score and explainable issues for a single product."""
        cat_name: str | None = None
        if product.category_id:
            cat = session.get(Category, product.category_id)
            if cat:
                cat_name = cat.name

        # Fetch product attributes
        prod_attrs = session.exec(
            select(ProductAttribute).where(ProductAttribute.product_id == product.id)
        ).all()
        attr_dict = {str(pa.attribute_id): pa.value for pa in prod_attrs}

        # Check duplicate SKU count
        dup_count = session.exec(select(Product).where(Product.sku == product.sku)).all()
        is_dup = len(dup_count) > 1

        product_dict: dict[str, Any] = {
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "stock": product.stock,
            "attributes": attr_dict,
        }

        return HealthScoreCalculator.evaluate(
            product_data=product_dict,
            category_name=cat_name,
            is_duplicate=is_dup,
        )

    @staticmethod
    def recompute_product(session: Session, product_id: int) -> HealthEvaluation:
        """Recompute health score for a specific product and update the database."""
        product = session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        evaluation = HealthService.evaluate_product(session, product)
        product.health_score = evaluation.score
        session.add(product)
        session.commit()
        session.refresh(product)
        return evaluation

    @staticmethod
    def recompute_all(session: Session) -> dict[str, Any]:
        """Recompute health scores for all products in the database."""
        products = session.exec(select(Product)).all()
        total = len(products)
        total_score = 0

        for p in products:
            evaluation = HealthService.evaluate_product(session, p)
            p.health_score = evaluation.score
            total_score += evaluation.score
            session.add(p)

        session.commit()

        avg_score = round(total_score / total, 1) if total > 0 else 0.0
        return {
            "total_products": total,
            "average_score": avg_score,
            "updated_count": total,
        }

    @staticmethod
    def get_catalog_health(
        session: Session,
        quality_agent: QualityAgent | None = None,
    ) -> CatalogHealthSummary:
        """Aggregate catalog-wide average health score, score distribution, and top issues."""
        products = session.exec(select(Product)).all()
        total = len(products)

        if total == 0:
            return CatalogHealthSummary(
                average_score=0.0,
                total_products=0,
                score_distribution=ScoreDistribution(),
                top_issues=[],
                advice_summary="Catalog is empty. Import products to see health score analytics.",
            )

        dist = ScoreDistribution()
        total_score = 0
        all_issues: list[str] = []

        for p in products:
            # Evaluate product quality
            evaluation = HealthService.evaluate_product(session, p)
            score = evaluation.score
            total_score += score
            all_issues.extend(evaluation.issues)

            # Update score if changed in DB
            if p.health_score != score:
                p.health_score = score
                session.add(p)

            # Distribution bucket
            if score >= 90:
                dist.excellent_90_100 += 1
            elif score >= 70:
                dist.good_70_89 += 1
            elif score >= 50:
                dist.fair_50_69 += 1
            else:
                dist.poor_0_49 += 1

        session.commit()

        avg_score = round(total_score / total, 1)

        # Count and rank top issues
        issue_counter = Counter(all_issues)
        top_issues = [
            IssueCount(issue=issue, count=count) for issue, count in issue_counter.most_common(10)
        ]

        # Quality agent advice
        advice_summary: str | None = None
        if top_issues:
            agent = quality_agent or QualityAgent()
            advice = agent.analyze(
                product_name="Catalog Overview",
                score=int(avg_score),
                issues=[f"{i.issue} ({i.count} items)" for i in top_issues[:3]],
            )
            advice_summary = advice.summary

        return CatalogHealthSummary(
            average_score=avg_score,
            total_products=total,
            score_distribution=dist,
            top_issues=top_issues,
            advice_summary=advice_summary,
        )
