from __future__ import annotations
from enum import Enum
from datetime import datetime
from sqlalchemy import (
    Integer, String, Text, DateTime, ForeignKey,
    CheckConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib import BaseModel

class MaintenanceType(str, Enum):
    PLANNED = "planned"
    UNPLANNED = "unplanned"

class MaintenanceStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class MaintenanceWindow(BaseModel):
    __tablename__ = 'lineup_maintenance_windows'
    __mapper_args__ = {'eager_defaults': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    berth_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("berths.id", ondelete="RESTRICT"),
        index=True,
        nullable=False
    )

    berth: Mapped["Berth"] = relationship(
        "Berth",
        back_populates="maintenance_windows",
        lazy="selectin"
    )

    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    mtype: Mapped[MaintenanceType] = mapped_column(
        default=MaintenanceType.PLANNED
    )

    status: Mapped[MaintenanceStatus] = mapped_column(
        default=MaintenanceStatus.SCHEDULED
    )

    # ---------------------------------------------------------------------
    # Maintenance Period
    # ---------------------------------------------------------------------
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint("end_at > start_at", name="check_maint_end_gt_start"),
        Index("idx_maint_berth_window", "berth_id", "start_at", "end_at")
    )