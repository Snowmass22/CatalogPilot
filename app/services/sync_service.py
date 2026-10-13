"""Service handling SyncPlan generation, dry-run diffs, approval, execution, and rollback (PRD Pillar C, ADR-0003, ADR-0006)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.adapters.store_port import StorePort, get_store_adapter
from app.agents.mapper import clean_price_string, clean_stock_string
from app.db.models import Product, Snapshot, SyncItem, SyncPlan, SyncRun
from app.domain.schemas import (
    RollbackResponse,
    SyncItemRead,
    SyncPlanRead,
    SyncRunRead,
)


class SyncService:
    """Orchestrates safe, idempotent product synchronization with dry-run diffs and snapshots."""

    @staticmethod
    def build_plan(
        session: Session,
        store: StorePort | None = None,
    ) -> SyncPlan:
        """Inspect catalog and external store to generate an immutable dry-run SyncPlan with field-level diffs."""
        store_adapter = store or get_store_adapter()
        products = list(session.exec(select(Product)).all())

        plan = SyncPlan(
            status="draft",
            created_at=datetime.now(UTC),
            summary="{}",
        )
        session.add(plan)
        session.flush()

        create_count = 0
        update_count = 0
        no_change_count = 0

        for product in products:
            # Lookup in external store by SKU
            store_prod = store_adapter.get_product_by_sku(product.sku)

            diff: dict[str, Any] = {}
            if not store_prod:
                action = "create"
                create_count += 1
                diff = {
                    "sku": {"before": None, "after": product.sku},
                    "name": {"before": None, "after": product.name},
                    "price": {"before": None, "after": product.price},
                    "stock": {"before": None, "after": product.stock},
                }
            else:
                # Compare fields for field-level diff
                store_price = clean_price_string(
                    store_prod.get("regular_price") or store_prod.get("price")
                )
                store_stock = clean_stock_string(
                    store_prod.get("stock_quantity") or store_prod.get("stock")
                )
                store_name = str(store_prod.get("name", "")).strip()

                field_diffs: dict[str, Any] = {}
                if store_name != product.name.strip():
                    field_diffs["name"] = {"before": store_name, "after": product.name.strip()}
                if abs(store_price - product.price) > 0.001:
                    field_diffs["price"] = {"before": store_price, "after": product.price}
                if store_stock != product.stock:
                    field_diffs["stock"] = {"before": store_stock, "after": product.stock}

                if field_diffs:
                    action = "update"
                    update_count += 1
                    diff = field_diffs
                else:
                    action = "no_change"
                    no_change_count += 1

            sync_item = SyncItem(
                plan_id=plan.id or 0,
                product_id=product.id or 0,
                action=action,
                diff=json.dumps(diff),
                status="pending",
            )
            session.add(sync_item)

        summary_dict = {
            "create": create_count,
            "update": update_count,
            "no_change": no_change_count,
            "total": len(products),
        }
        plan.summary = json.dumps(summary_dict)
        session.commit()
        session.refresh(plan)
        return plan

    @staticmethod
    def approve_plan(session: Session, plan_id: int) -> SyncPlan:
        """Human approval gate for sync plan execution (PRD C3, ADR-0004)."""
        plan = session.get(SyncPlan, plan_id)
        if not plan:
            raise ValueError(f"SyncPlan ID {plan_id} not found.")
        plan.status = "approved"
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return plan

    @staticmethod
    def execute_plan(
        session: Session,
        plan_id: int,
        store: StorePort | None = None,
        auto_approve: bool = True,
    ) -> SyncRun:
        """Execute approved plan in batches, capturing snapshots of prior states before writes."""
        store_adapter = store or get_store_adapter()
        plan = session.get(SyncPlan, plan_id)
        if not plan:
            raise ValueError(f"SyncPlan ID {plan_id} not found.")

        if plan.status == "draft":
            if auto_approve:
                plan.status = "approved"
            else:
                raise ValueError("Cannot execute unapproved SyncPlan. Approve the plan first.")
        elif plan.status == "executed":
            raise ValueError("This SyncPlan has already been executed.")

        run = SyncRun(
            plan_id=plan.id or 0,
            started_at=datetime.now(UTC),
            status="pending",
        )
        session.add(run)
        session.flush()

        items = session.exec(select(SyncItem).where(SyncItem.plan_id == plan.id)).all()

        create_payloads: list[dict[str, Any]] = []
        update_payloads: list[dict[str, Any]] = []

        for item in items:
            product = session.get(Product, item.product_id)
            if not product:
                continue

            if item.action == "create":
                # Save snapshot with before_state=None so rollback deletes newly created item
                snapshot = Snapshot(
                    run_id=run.id or 0,
                    product_id=product.id or 0,
                    before_state=None,
                )
                session.add(snapshot)

                create_payloads.append(
                    {
                        "sku": product.sku,
                        "name": product.name,
                        "regular_price": str(product.price),
                        "stock_quantity": product.stock,
                        "description": product.description or "",
                    }
                )
                item.status = "success"

            elif item.action == "update":
                store_item = store_adapter.get_product_by_sku(product.sku)
                # Capture snapshot of prior state
                snapshot = Snapshot(
                    run_id=run.id or 0,
                    product_id=product.id or 0,
                    before_state=json.dumps(store_item) if store_item else None,
                )
                session.add(snapshot)

                woo_id = product.woo_id or (store_item.get("id") if store_item else None)
                update_payloads.append(
                    {
                        "id": woo_id,
                        "sku": product.sku,
                        "name": product.name,
                        "regular_price": str(product.price),
                        "stock_quantity": product.stock,
                        "description": product.description or "",
                    }
                )
                item.status = "success"

            else:  # no_change
                item.status = "skipped"

            session.add(item)

        # Batch execution conforming to WooCommerce batch API
        result = store_adapter.batch_sync(
            create=create_payloads,
            update=update_payloads,
        )

        # Update product.woo_id from batch create results
        for created_prod in result.get("create", []):
            sku = created_prod.get("sku")
            if sku:
                prod_in_db = session.exec(select(Product).where(Product.sku == sku)).first()
                if prod_in_db:
                    prod_in_db.woo_id = created_prod.get("id")
                    session.add(prod_in_db)

        plan.status = "executed"
        run.status = "success"
        run.finished_at = datetime.now(UTC)

        session.add(plan)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    @staticmethod
    def rollback_run(
        session: Session,
        run_id: int,
        store: StorePort | None = None,
    ) -> RollbackResponse:
        """Rollback touched products to their exact prior snapshots (Time Machine feature)."""
        store_adapter = store or get_store_adapter()
        run = session.get(SyncRun, run_id)
        if not run:
            raise ValueError(f"SyncRun ID {run_id} not found.")

        if run.status == "rolled_back":
            raise ValueError("This SyncRun has already been rolled back.")

        snapshots = session.exec(select(Snapshot).where(Snapshot.run_id == run.id)).all()
        restored_count = 0

        for snap in snapshots:
            product = session.get(Product, snap.product_id)
            if not product:
                continue

            if snap.before_state is None:
                # Newly created product during run -> delete from store
                if product.woo_id:
                    store_adapter.delete_product(product.woo_id)
                    product.woo_id = None
                    session.add(product)
                restored_count += 1
            else:
                # Modified product -> restore prior state
                prior_data = json.loads(snap.before_state)
                woo_id = product.woo_id or prior_data.get("id")
                if woo_id:
                    store_adapter.restore_product(woo_id, prior_data)
                restored_count += 1

        run.status = "rolled_back"
        if run.plan:
            run.plan.status = "rolled_back"
            session.add(run.plan)

        session.add(run)
        session.commit()

        return RollbackResponse(
            run_id=run.id or 0,
            status="rolled_back",
            restored_items=restored_count,
            details=f"Successfully restored {restored_count} product(s) to previous snapshot states.",
        )

    @staticmethod
    def list_runs(session: Session) -> list[SyncRunRead]:
        """List all sync execution runs with snapshot metrics."""
        runs = list(session.exec(select(SyncRun).order_by(SyncRun.id.desc())).all())  # type: ignore[union-attr]
        read_items: list[SyncRunRead] = []
        for r in runs:
            snaps_count = len(session.exec(select(Snapshot).where(Snapshot.run_id == r.id)).all())
            read_items.append(
                SyncRunRead(
                    id=r.id or 0,
                    plan_id=r.plan_id,
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    status=r.status,
                    snapshots_count=snaps_count,
                )
            )
        return read_items

    @staticmethod
    def to_plan_read(session: Session, plan: SyncPlan) -> SyncPlanRead:
        """Serialize SyncPlan model into rich SyncPlanRead schema."""
        items = session.exec(select(SyncItem).where(SyncItem.plan_id == plan.id)).all()
        summary_dict = json.loads(plan.summary) if plan.summary else {}

        item_reads = [
            SyncItemRead(
                id=i.id or 0,
                product_id=i.product_id,
                action=i.action,
                diff=json.loads(i.diff) if i.diff else {},
                status=i.status,
                error=i.error,
            )
            for i in items
        ]

        return SyncPlanRead(
            id=plan.id or 0,
            created_at=plan.created_at,
            summary=summary_dict,
            status=plan.status,
            items=item_reads,
        )
