"""Service handling CSV import preview with AI mapping and commit operations."""

from __future__ import annotations

import csv
import io
from collections import Counter

from sqlmodel import Session, select

from app.agents.mapper import (
    MapperAgent,
    clean_price_string,
    clean_stock_string,
)
from app.db.models import AttributeDef, Category, Product
from app.domain.schemas import (
    AttributeDefCreate,
    CategoryCreate,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ProductAttributeInput,
    ProductCreate,
    ProductUpdate,
)
from app.services.attribute_service import AttributeService
from app.services.category_service import CategoryService
from app.services.product_service import ProductService


class ImportService:
    """Service orchestrating CSV parsing, mapping inference, validation, and batch commitment."""

    @staticmethod
    def parse_csv(csv_content: str) -> tuple[list[str], list[dict[str, str]]]:
        """Parse raw CSV text into headers and row dictionaries."""
        stream = io.StringIO(csv_content.strip())
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        rows = list(reader)
        return list(headers), rows

    @staticmethod
    def preview(
        session: Session,
        csv_content: str,
        mapper_agent: MapperAgent | None = None,
    ) -> ImportPreviewResponse:
        """Analyze CSV, infer mapping and normalizations, and return structured preview."""
        headers, rows = ImportService.parse_csv(csv_content)
        if not headers or not rows:
            raise ValueError("CSV is empty or missing headers.")

        agent = mapper_agent or MapperAgent()

        # Gather target schema from database
        db_categories = CategoryService.list_all(session)
        known_categories = [c.name for c in db_categories]

        db_attributes = AttributeService.list_all(session)
        attr_defs_info = [
            {
                "name": a.name,
                "type": a.type,
                "allowed_values": AttributeService.parse_allowed_values(a),
            }
            for a in db_attributes
        ]

        # Infer mapping using agent
        mapper_result = agent.infer_mapping(
            headers=headers,
            sample_rows=rows[:5],
            attribute_defs=attr_defs_info,
            known_categories=known_categories,
        )

        mapping = mapper_result.mapping
        normalizations = mapper_result.attribute_normalizations

        # Identify duplicate SKUs within the file
        raw_skus = [
            r.get(mapping.sku_column, "").strip() for r in rows if r.get(mapping.sku_column)
        ]
        sku_counts = Counter(raw_skus)
        duplicate_skus_in_file = [sku for sku, count in sku_counts.items() if count > 1]

        # Check existing SKUs in DB
        existing_db_skus = set(
            session.exec(select(Product.sku).where(Product.sku.in_(raw_skus))).all()  # type: ignore[attr-defined]
        )

        preview_rows: list[ImportPreviewRow] = []

        for idx, row in enumerate(rows, start=1):
            sku_val = row.get(mapping.sku_column, "").strip()
            name_val = row.get(mapping.name_column, "").strip()
            desc_val = (
                row.get(mapping.description_column, "").strip()
                if mapping.description_column
                else None
            )
            raw_price = row.get(mapping.price_column, "")
            raw_stock = row.get(mapping.stock_column, "")
            cat_val = (
                row.get(mapping.category_column, "").strip() if mapping.category_column else None
            )

            price_val = clean_price_string(raw_price)
            stock_val = clean_stock_string(raw_stock)

            # Process attributes and apply normalizations
            row_attrs: dict[str, str] = {}
            for col_name, attr_name in mapping.attribute_columns.items():
                raw_val = row.get(col_name, "").strip()
                if not raw_val:
                    continue

                # Check normalization mapping
                norm_for_attr = normalizations.get(attr_name, {})
                normalized_val = (
                    norm_for_attr.get(raw_val) or norm_for_attr.get(raw_val.lower()) or raw_val
                )
                row_attrs[attr_name] = normalized_val

            # Issue detection
            issues: list[str] = []
            if not sku_val:
                issues.append("Missing SKU")
            elif sku_counts[sku_val] > 1:
                issues.append("Duplicate SKU in file")

            if sku_val in existing_db_skus:
                issues.append("SKU exists in catalog (will update)")

            if not name_val:
                issues.append("Missing product title")
            if not desc_val:
                issues.append("Missing description")
            if price_val <= 0:
                issues.append("Price is 0 or invalid")
            elif price_val > 1000:
                issues.append("High price check needed (> $1,000)")

            preview_rows.append(
                ImportPreviewRow(
                    row_index=idx,
                    raw_data=row,
                    sku=sku_val,
                    name=name_val,
                    description=desc_val or None,
                    price=price_val,
                    stock=stock_val,
                    category_name=cat_val or None,
                    attributes=row_attrs,
                    issues=issues,
                )
            )

        return ImportPreviewResponse(
            mapping=mapping,
            attribute_normalizations=normalizations,
            total_rows=len(rows),
            preview_items=preview_rows,
            duplicate_skus_in_file=duplicate_skus_in_file,
            existing_skus_in_db=list(existing_db_skus),
        )

    @staticmethod
    def commit(session: Session, request: ImportCommitRequest) -> ImportCommitResponse:
        """Commit validated preview items into database, resolving categories and attributes."""
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors: list[str] = []

        # Cache existing categories and attribute defs
        category_cache: dict[str, Category] = {
            c.name.lower(): c for c in CategoryService.list_all(session)
        }
        attr_cache: dict[str, AttributeDef] = {
            a.name.lower(): a for a in AttributeService.list_all(session)
        }

        for item in request.items:
            try:
                # 1. Resolve category
                cat_id: int | None = None
                if item.category_name:
                    norm_cat = item.category_name.strip().lower()
                    if norm_cat in category_cache:
                        cat_id = category_cache[norm_cat].id
                    else:
                        new_cat = CategoryService.create(
                            session, CategoryCreate(name=item.category_name.strip())
                        )
                        category_cache[norm_cat] = new_cat
                        cat_id = new_cat.id

                # 2. Resolve attributes
                attr_inputs: list[ProductAttributeInput] = []
                for attr_name, attr_val in item.attributes.items():
                    norm_attr = attr_name.strip().lower()
                    if norm_attr in attr_cache:
                        attr_def = attr_cache[norm_attr]
                    else:
                        # Auto-create attribute def as text if missing
                        new_attr = AttributeService.create(
                            session,
                            AttributeDefCreate(name=attr_name.strip(), type="text"),
                        )
                        attr_cache[norm_attr] = new_attr
                        attr_def = new_attr

                    if attr_def.id is not None and attr_val:
                        attr_inputs.append(
                            ProductAttributeInput(
                                attribute_id=attr_def.id,
                                value=attr_val.strip(),
                            )
                        )

                # 3. Insert or update product
                existing = ProductService.get_by_sku(session, item.sku)

                if existing:
                    if request.upsert:
                        update_payload = ProductUpdate(
                            name=item.name,
                            description=item.description,
                            price=item.price,
                            stock=item.stock,
                            category_id=cat_id,
                            status=item.status,
                            attributes=attr_inputs,
                        )
                        ProductService.update(session, existing.id or 0, update_payload)
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    create_payload = ProductCreate(
                        sku=item.sku,
                        name=item.name,
                        description=item.description,
                        price=item.price,
                        stock=item.stock,
                        category_id=cat_id,
                        status=item.status,
                        attributes=attr_inputs,
                    )
                    ProductService.create(session, create_payload)
                    imported_count += 1

            except Exception as e:
                errors.append(f"Failed to process SKU '{item.sku}': {e}")

        return ImportCommitResponse(
            imported=imported_count,
            updated=updated_count,
            skipped=skipped_count,
            errors=errors,
        )
