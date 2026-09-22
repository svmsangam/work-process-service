from fastapi import HTTPException, status
from app.models import WorkItemStatus

# Define valid state transitions
ALLOWED_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.RECEIVED: {WorkItemStatus.ANALYSING},
    WorkItemStatus.ANALYSING: {WorkItemStatus.READY_FOR_REVIEW, WorkItemStatus.FAILED},
    WorkItemStatus.READY_FOR_REVIEW: {WorkItemStatus.COMPLETED, WorkItemStatus.ANALYSING},
    WorkItemStatus.FAILED: {WorkItemStatus.ANALYSING},  # Retry path
    WorkItemStatus.COMPLETED: set(),  # Terminal state: no moves allowed
}

def validate_state_transition(current_status: WorkItemStatus, new_status: WorkItemStatus):
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition from {current_status.value} to {new_status.value}."
        )