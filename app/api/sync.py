"""FastAPI router for Sync Plan, Execution, and Rollback (PRD Pillar C)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.domain.schemas import (
    RollbackResponse,
    SyncPlanRead,
    SyncRunRead,
)
from app.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("/plan", response_model=SyncPlanRead, status_code=status.HTTP_201_CREATED)
def create_sync_plan(
    session: Session = Depends(get_session),
) -> SyncPlanRead:
    """Generate dry-run SyncPlan with field-level diffs (PRD C2)."""
    plan = SyncService.build_plan(session)
    return SyncService.to_plan_read(session, plan)


@router.post("/{plan_id}/approve", response_model=SyncPlanRead)
def approve_sync_plan(
    plan_id: int,
    session: Session = Depends(get_session),
) -> SyncPlanRead:
    """Approve a dry-run sync plan before execution (PRD C3)."""
    try:
        plan = SyncService.approve_plan(session, plan_id)
        return SyncService.to_plan_read(session, plan)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{plan_id}/execute", response_model=SyncRunRead)
def execute_sync_plan(
    plan_id: int,
    session: Session = Depends(get_session),
) -> SyncRunRead:
    """Execute an approved SyncPlan, saving snapshots for rollback (PRD C4)."""
    try:
        run = SyncService.execute_plan(session, plan_id, auto_approve=True)
        return SyncRunRead(
            id=run.id or 0,
            plan_id=run.plan_id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            snapshots_count=len(run.snapshots),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/runs", response_model=list[SyncRunRead])
def list_sync_runs(
    session: Session = Depends(get_session),
) -> list[SyncRunRead]:
    """Retrieve history of all sync execution runs (PRD C5)."""
    return SyncService.list_runs(session)


@router.post("/runs/{run_id}/rollback", response_model=RollbackResponse)
def rollback_sync_run(
    run_id: int,
    session: Session = Depends(get_session),
) -> RollbackResponse:
    """Roll back a sync run to its pre-execution state using saved snapshots (PRD C6)."""
    try:
        return SyncService.rollback_run(session, run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
