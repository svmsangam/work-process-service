from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from enum import Enum
from datetime import datetime
from app.models import WorkItemStatus

class AICategoryEnum(str, Enum):
    DOCUMENT_REQUEST = "DOCUMENT_REQUEST"
    TECHNICAL_ISSUE = "TECHNICAL_ISSUE"
    ACCOUNT_INQUIRY = "ACCOUNT_INQUIRY"
    BILLING_DISPUTE = "BILLING_DISPUTE"
    GENERAL = "GENERAL"

class AIPriorityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AIAnalysisResult(BaseModel):
    category: AICategoryEnum
    priority: AIPriorityEnum
    summary: str
    recommended_action: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

# Requests
class WorkItemCreate(BaseModel):
    external_id: str
    title: str
    description: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )

class WorkItemStatusUpdate(BaseModel):
    status: WorkItemStatus

# Responses
class WorkItemResponse(BaseModel):
    id: int
    external_id: str
    title: str
    description: str
    status: WorkItemStatus
    ai_analysis: Optional[AIAnalysisResult] = None
    ai_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )