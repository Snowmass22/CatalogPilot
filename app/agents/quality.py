"""Quality Agent: translates deterministic health issues into plain-language suggestions (PRD Pillar D, ADR-0007)."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.adapters.llm_port import LLMError, LLMPort, get_llm_adapter

logger = logging.getLogger(__name__)


class QualityAdvice(BaseModel):
    """Plain-language quality assessment and actionable recommendations."""

    summary: str = Field(..., description="High-level evaluation of product quality")
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable steps the merchant can take to raise the score",
    )


class QualityAgent:
    """Agent that produces human-friendly advice from deterministic rule issues."""

    def __init__(self, llm_adapter: LLMPort | None = None) -> None:
        self.llm = llm_adapter or get_llm_adapter()

    def analyze(
        self,
        product_name: str,
        score: int,
        issues: list[str],
        category: str | None = None,
    ) -> QualityAdvice:
        """Produce actionable advice from issues, falling back to deterministic advice."""
        if not issues:
            return QualityAdvice(
                summary=f"'{product_name}' meets high quality standards with a complete catalog profile.",
                suggestions=["Catalog data is complete and ready for WooCommerce sync."],
            )

        prompt = (
            f"Product: '{product_name}' (Category: {category or 'General'})\n"
            f"Health Score: {score}/100\n"
            f"Detected Issues:\n"
            + "\n".join(f"- {issue}" for issue in issues)
            + "\n\nRewrite these issues into a polite, clear 1-sentence summary and 2-4 actionable suggestions."
        )

        system_instruction = (
            "You are CatalogPilot's Quality Agent. Convert technical PIM catalog data issues "
            "into helpful, encouraging e-commerce advice for store managers."
        )

        try:
            return self.llm.generate(
                prompt=prompt,
                schema=QualityAdvice,
                system_instruction=system_instruction,
            )
        except LLMError as e:
            logger.info("Quality agent using deterministic advice generator: %s", e)

        # Fallback to deterministic plain-language translation
        return self._rule_based_advice(product_name, score, issues)

    @staticmethod
    def _rule_based_advice(
        product_name: str,
        score: int,
        issues: list[str],
    ) -> QualityAdvice:
        """Deterministic advice generator."""
        suggestions: list[str] = []
        for issue in issues:
            if "Missing product image" in issue:
                suggestions.append("Upload at least one high-resolution product image.")
            elif "Missing required attribute" in issue:
                suggestions.append(
                    f"Add the missing specifications: {issue.replace('Missing required attribute(s): ', '')}."
                )
            elif "description" in issue.lower():
                suggestions.append(
                    "Expand the description with fabric details, dimensions, and styling notes."
                )
            elif "Price" in issue:
                suggestions.append(
                    "Review product pricing to ensure accurate decimal formatting and positive values."
                )
            elif "Duplicate" in issue:
                suggestions.append(
                    "Assign a unique SKU to prevent stock collisions in WooCommerce."
                )
            else:
                suggestions.append(f"Address issue: {issue}.")

        summary = (
            f"'{product_name}' is scored at {score}/100 with {len(issues)} item(s) to optimize."
        )
        return QualityAdvice(summary=summary, suggestions=suggestions)
