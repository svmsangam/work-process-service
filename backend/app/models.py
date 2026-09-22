import enum
from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base

class WorkItemStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    ANALYSING = "ANALYSING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Use native_enum=False so SQLite can store Enum values as plain Varchar strings
    status = Column(
        Enum(WorkItemStatus, native_enum=False, create_constraint=False),
        default=WorkItemStatus.RECEIVED,
        nullable=False,
        index=True
    )
    
    ai_analysis = Column(JSON, nullable=True)
    ai_error = Column(Text, nullable=True)

    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('external_id', name='uq_work_item_external_id'),
    )