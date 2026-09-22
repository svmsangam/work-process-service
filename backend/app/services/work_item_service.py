import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import WorkItem, WorkItemStatus
from app.schemas import WorkItemCreate, WorkItemStatusUpdate
from app.state_machine import validate_state_transition
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


class WorkItemService:

    @staticmethod
    def create_work_item(db: Session, payload: WorkItemCreate) -> WorkItem:
        """
        Ingests a new work item. Enforces database-level idempotency on external_id.
        """
        db_item = WorkItem(
            external_id=payload.external_id,
            title=payload.title,
            description=payload.description,
            status=WorkItemStatus.RECEIVED
        )
        try:
            db.add(db_item)
            db.commit()
            db.refresh(db_item)
            return db_item
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Work item with externalId '{payload.external_id}' already exists."
            )

    @staticmethod
    def get_all(db: Session, status_filter: Optional[WorkItemStatus] = None) -> List[WorkItem]:
        query = db.query(WorkItem)
        if status_filter:
            query = query.filter(WorkItem.status == status_filter)
        return query.order_by(WorkItem.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, item_id: int) -> WorkItem:
        item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work item with ID {item_id} not found."
            )
        return item

    @staticmethod
    def update_status(db: Session, item_id: int, payload: WorkItemStatusUpdate) -> WorkItem:
        """
        Updates item status while enforcing state machine transition rules.
        """
        item = WorkItemService.get_by_id(db, item_id)
        validate_state_transition(item.status, payload.status)

        item.status = payload.status
        item.version += 1
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    async def process_ai_analysis(db: Session, item_id: int):
        """
        Background worker logic for AI analysis execution.
        Safely captures failures and transitions item state to FAILED on error.
        """
        item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
        if not item:
            return

        # Transition status to ANALYSING
        try:
            validate_state_transition(item.status, WorkItemStatus.ANALYSING)
            item.status = WorkItemStatus.ANALYSING
            db.commit()
        except Exception as e:
            logger.error(f"Cannot process analysis for item {item_id}: {str(e)}")
            return

        # Execute AI Provider Adapter
        ai_service = get_ai_service()
        try:
            result = await ai_service.analyze_work_item(item.title, item.description)
            
            # On success: Update AI payload & transition to READY_FOR_REVIEW
            item.ai_analysis = result.model_dump()
            item.ai_error = None
            item.status = WorkItemStatus.READY_FOR_REVIEW
            item.version += 1
            db.commit()
            
        except Exception as err:
            logger.error(f"AI analysis failed for item {item_id}: {str(err)}")
            db.rollback()
            # Refetch instance in clean session state
            item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
            item.ai_error = str(err)
            item.status = WorkItemStatus.FAILED
            item.version += 1
            db.commit()