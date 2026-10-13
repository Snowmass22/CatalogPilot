"""Web UI router serving Jinja2 templates and HTMX partials for CatalogPilot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.config import settings
from app.db.models import Product, SyncPlan
from app.db.session import get_session
from app.domain.schemas import ImportCommitRequest
from app.services.category_service import CategoryService
from app.services.health_service import HealthService
from app.services.import_service import ImportService
from app.services.product_service import ProductService
from app.services.sync_service import SyncService

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ui_router = APIRouter(tags=["UI"])


@ui_router.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    """Serve single-page application shell with HTMX tabs and Tailwind CDN."""
    accept = request.headers.get("accept", "")
    if "text/html" not in accept and "application/json" in accept:
        return JSONResponse(
            {
                "name": "CatalogPilot",
                "description": "Agentic PIM for WooCommerce",
                "version": "0.1.0",
                "docs": "/docs",
                "health": "/api/health",
                "env": settings.ENV,
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "store_mode": settings.STORE_MODE,
        },
    )


# ---------------------------------------------------------------------------
# Dashboard Partial
# ---------------------------------------------------------------------------


@ui_router.get("/ui/partials/dashboard", response_class=HTMLResponse)
def get_dashboard_partial(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Render Dashboard tab with average health score, distribution, and top issues."""
    summary = HealthService.get_catalog_health(session)
    return templates.TemplateResponse(
        request=request,
        name="partials/dashboard.html",
        context={
            "summary": summary,
        },
    )


@ui_router.post("/ui/partials/dashboard/recompute", response_class=HTMLResponse)
def recompute_dashboard_partial(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Recompute all catalog health scores and return refreshed Dashboard partial."""
    HealthService.recompute_all(session)
    summary = HealthService.get_catalog_health(session)
    return templates.TemplateResponse(
        request=request,
        name="partials/dashboard.html",
        context={
            "summary": summary,
        },
    )


# ---------------------------------------------------------------------------
# Catalog Partial
# ---------------------------------------------------------------------------


@ui_router.get("/ui/partials/catalog", response_class=HTMLResponse)
def get_catalog_partial(
    request: Request,
    query: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """Render Catalog tab with search filtering and responsive product table."""
    products, total_count = ProductService.list_all(session, query=query, limit=100)
    categories = CategoryService.list_all(session)
    category_names = {c.id: c.name for c in categories if c.id is not None}

    return templates.TemplateResponse(
        request=request,
        name="partials/catalog.html",
        context={
            "products": products,
            "total_count": total_count,
            "category_names": category_names,
            "query": query,
        },
    )


# ---------------------------------------------------------------------------
# Import Partials
# ---------------------------------------------------------------------------


@ui_router.post("/ui/partials/import/preview", response_class=HTMLResponse)
async def import_preview_partial(
    request: Request,
    file: UploadFile | None = File(None),
    use_sample: bool = False,
    session: Session = Depends(get_session),
) -> Response:
    """Render CSV preview showing AI mapping, normalized attributes, and sample rows."""
    if use_sample:
        sample_path = Path("sample_data/messy_supplier.csv")
        if not sample_path.exists():
            return HTMLResponse(
                "<div class='p-4 text-xs text-rose-400 bg-rose-950/40 rounded-lg'>Sample messy_supplier.csv not found on disk.</div>"
            )
        csv_content = sample_path.read_text(encoding="utf-8")
    else:
        if file is None or not file.filename:
            return HTMLResponse(
                "<div class='p-4 text-xs text-amber-400 bg-amber-950/40 rounded-lg'>Please select a CSV file or click 'Load Sample Messy CSV'.</div>"
            )
        raw_bytes = await file.read()
        csv_content = raw_bytes.decode("utf-8-sig", errors="replace")

    preview = ImportService.preview(session, csv_content)

    commit_items: list[dict[str, Any]] = [
        {
            "sku": item.sku,
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "stock": item.stock,
            "category_name": item.category_name,
            "attributes": item.attributes,
        }
        for item in preview.preview_items
    ]
    commit_payload_json = json.dumps({"items": commit_items, "upsert": True})

    return templates.TemplateResponse(
        request=request,
        name="partials/import_preview.html",
        context={
            "preview": preview,
            "commit_payload_json": commit_payload_json,
        },
    )


@ui_router.post("/ui/partials/import/commit", response_class=HTMLResponse)
def import_commit_partial(
    request: Request,
    response: Response,
    payload_json: str = Form(...),
    session: Session = Depends(get_session),
) -> Response:
    """Commit imported products and dispatch reactive HTMX triggers."""
    commit_request = ImportCommitRequest.model_validate_json(payload_json)
    result = ImportService.commit(session, commit_request)

    resp = templates.TemplateResponse(
        request=request,
        name="partials/import_success.html",
        context={
            "result": result,
        },
    )
    # Trigger HTMX to update Catalog and Dashboard tabs
    resp.headers["HX-Trigger"] = "refreshCatalog, refreshDashboard"
    return resp


# ---------------------------------------------------------------------------
# Sync Partials
# ---------------------------------------------------------------------------


@ui_router.post("/ui/partials/sync/plan", response_class=HTMLResponse)
def sync_plan_partial(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Generate dry-run sync plan and render diff table with action buttons."""
    plan = SyncService.build_plan(session)
    summary_dict: dict[str, Any] = json.loads(plan.summary) if plan.summary else {}

    items_details: list[dict[str, Any]] = []
    for item in plan.items:
        prod = session.get(Product, item.product_id)
        diff_data = json.loads(item.diff) if item.diff else {}
        items_details.append(
            {
                "sku": prod.sku if prod else "—",
                "name": prod.name if prod else "—",
                "action": item.action,
                "diff": diff_data,
                "status": item.status,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/sync_plan.html",
        context={
            "plan": plan,
            "summary": summary_dict,
            "items_details": items_details,
        },
    )


@ui_router.post("/ui/partials/sync/{plan_id}/execute", response_class=HTMLResponse)
def sync_execute_partial(
    plan_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Approve and execute sync plan, saving snapshots and updating store."""
    SyncService.execute_plan(session, plan_id, auto_approve=True)
    plan = session.get(SyncPlan, plan_id)
    summary_dict: dict[str, Any] = {}

    items_details: list[dict[str, Any]] = []
    if plan:
        summary_dict = json.loads(plan.summary) if plan.summary else {}
        for item in plan.items:
            prod = session.get(Product, item.product_id)
            diff_data = json.loads(item.diff) if item.diff else {}
            items_details.append(
                {
                    "sku": prod.sku if prod else "—",
                    "name": prod.name if prod else "—",
                    "action": item.action,
                    "diff": diff_data,
                    "status": item.status,
                }
            )

    resp = templates.TemplateResponse(
        request=request,
        name="partials/sync_plan.html",
        context={
            "plan": plan,
            "summary": summary_dict,
            "items_details": items_details,
        },
    )
    # Trigger HTMX to update Runs list and Catalog WooCommerce status
    resp.headers["HX-Trigger"] = "refreshRuns, refreshCatalog"
    return resp


@ui_router.get("/ui/partials/sync/runs", response_class=HTMLResponse)
def sync_runs_partial(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """List historical sync runs with snapshot counts and rollback buttons."""
    runs = SyncService.list_runs(session)
    return templates.TemplateResponse(
        request=request,
        name="partials/sync_runs.html",
        context={
            "runs": runs,
        },
    )


@ui_router.post("/ui/partials/sync/runs/{run_id}/rollback", response_class=HTMLResponse)
def sync_rollback_partial(
    run_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Execute Time Machine rollback and return refreshed runs history."""
    SyncService.rollback_run(session, run_id)
    runs = SyncService.list_runs(session)

    resp = templates.TemplateResponse(
        request=request,
        name="partials/sync_runs.html",
        context={
            "runs": runs,
        },
    )
    # Trigger HTMX to update Catalog tab to show reverted states
    resp.headers["HX-Trigger"] = "refreshCatalog"
    return resp
