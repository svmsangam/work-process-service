import pytest
from app.models import WorkItemStatus, WorkItem


# Scenario 1: Idempotency & Duplicate Prevention
def test_create_duplicate_external_id_rejected(client):
    """Verify duplicate externalId payloads return 409 Conflict and prevent duplicate rows."""
    payload = {
        "external_id": "CRM-12345",
        "title": "Missing income document",
        "description": "Applicant has not provided latest payslip."
    }

    # First attempt -> Success
    res1 = client.post("/work-items", json=payload)
    assert res1.status_code == 201
    assert res1.json()["external_id"] == "CRM-12345"
    assert res1.json()["status"] == WorkItemStatus.RECEIVED.value

    # Second attempt with same externalId -> 409 Conflict
    res2 = client.post("/work-items", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


# Scenario 2: Workflow State Machine Boundaries
def test_invalid_workflow_transition_rejected(client):
    """Verify direct jump from RECEIVED to COMPLETED is blocked by state machine rules."""
    # Create work item
    payload = {
        "external_id": "CRM-99999",
        "title": "Unprocessed claim",
        "description": "Requires manual review."
    }
    create_res = client.post("/work-items", json=payload)
    item_id = create_res.json()["id"]

    # Attempt illegal transition: RECEIVED -> COMPLETED
    status_update = {"status": WorkItemStatus.COMPLETED.value}
    update_res = client.patch(f"/work-items/{item_id}/status", json=status_update)

    assert update_res.status_code == 400
    assert "Invalid state transition" in update_res.json()["detail"]


def test_completed_state_is_terminal(client):
    """Verify COMPLETED state cannot transition backward or into analysis."""
    # Create item and advance sequentially to COMPLETED
    payload = {"external_id": "CRM-11111", "title": "Test", "description": "Test"}
    item_id = client.post("/work-items", json=payload).json()["id"]

    # Step-by-step valid transitions
    client.patch(f"/work-items/{item_id}/status", json={"status": WorkItemStatus.ANALYSING.value})
    client.patch(f"/work-items/{item_id}/status", json={"status": WorkItemStatus.READY_FOR_REVIEW.value})
    client.patch(f"/work-items/{item_id}/status", json={"status": WorkItemStatus.COMPLETED.value})

    # Try transitioning out of COMPLETED -> Should fail
    res = client.patch(f"/work-items/{item_id}/status", json={"status": WorkItemStatus.ANALYSING.value})
    assert res.status_code == 400


# Scenario 3: AI Failure Isolation & Retry Boundaries
def test_ai_failure_isolation_and_retry_eligibility(client, db_session):
    """
    Verify AI failure sets status to FAILED without corrupting item fields,
    and verify non-FAILED items cannot trigger retry.
    """
    # 1. Create item
    payload = {
        "external_id": "FAIL_LLM_TEST",
        "title": "FAIL_LLM Special Case",
        "description": "Triggers synthetic failure in Mock AI service."
    }
    create_res = client.post("/work-items", json=payload)
    item_id = create_res.json()["id"]

    # 2. Attempt retry while in RECEIVED state -> Should return 400 (Only FAILED items eligible)
    retry_invalid = client.post(f"/work-items/{item_id}/retry")
    assert retry_invalid.status_code == 400
    assert "Only items in FAILED state are eligible" in retry_invalid.json()["detail"]

    # 3. Simulate direct AI failure execution
    from app.services.work_item_service import WorkItemService
    import asyncio

    # Run AI processing synchronously for test evaluation
    asyncio.run(WorkItemService.process_ai_analysis(db_session, item_id))

    # Refetch item from DB
    failed_item = db_session.query(WorkItem).filter(WorkItem.id == item_id).first()

    # Assert record status updated to FAILED safely
    assert failed_item.status == WorkItemStatus.FAILED
    assert failed_item.ai_error is not None
    assert "Mock LLM Provider failure" in failed_item.ai_error

    # Assert original core metadata remains completely uncorrupted
    assert failed_item.external_id == "FAIL_LLM_TEST"
    assert failed_item.title == "FAIL_LLM Special Case"
    assert failed_item.description == "Triggers synthetic failure in Mock AI service."