from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WorkItemStatus
from app.schemas import WorkItemCreate, WorkItemResponse, WorkItemStatusUpdate
from app.services.work_item_service import WorkItemService

router = APIRouter(prefix="/work-items", tags=["Work Items"])


@router.post("", response_model=WorkItemResponse, status_code=status.HTTP_201_CREATED)
def create_work_item(
    payload: WorkItemCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """1. Ingest work item (Deduplicated via unique externalId) and queue AI analysis."""
    item = WorkItemService.create_work_item(db, payload)
    background_tasks.add_task(WorkItemService.process_ai_analysis, db, item.id)
    return item


@router.get("", response_model=List[WorkItemResponse])
def list_work_items(
    status: Optional[WorkItemStatus] = Query(None, description="Filter items by status"),
    db: Session = Depends(get_db)
):
    """List work items with optional status filtering."""
    return WorkItemService.get_all(db, status_filter=status)


@router.get("/{item_id}", response_model=WorkItemResponse)
def get_work_item(item_id: int, db: Session = Depends(get_db)):
    """Fetch single work item by ID."""
    return WorkItemService.get_by_id(db, item_id)


@router.post("/{item_id}/analyse", response_model=WorkItemResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_analysis(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """3. Trigger AI Analysis asynchronously in background."""
    item = WorkItemService.get_by_id(db, item_id)
    
    # Schedule background execution
    background_tasks.add_task(WorkItemService.process_ai_analysis, db, item_id)
    return item


@router.post("/{item_id}/retry", response_model=WorkItemResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_analysis(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """4. Retry AI analysis (Only eligible for items currently in FAILED state)."""
    item = WorkItemService.get_by_id(db, item_id)
    
    if item.status != WorkItemStatus.FAILED:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only items in FAILED state are eligible for retry. Current status: {item.status.value}"
        )

    # Schedule background execution
    background_tasks.add_task(WorkItemService.process_ai_analysis, db, item_id)
    return item


@router.patch("/{item_id}/status", response_model=WorkItemResponse)
def update_item_status(
    item_id: int,
    payload: WorkItemStatusUpdate,
    db: Session = Depends(get_db)
):
    """Manual status updates (e.g. READY_FOR_REVIEW -> COMPLETED)."""
    return WorkItemService.update_status(db, item_id, payload)