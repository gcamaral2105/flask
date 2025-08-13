from __future__ import annotations
from enum import Enum
from typing import Optional, List
from datetime import datetime, date
from sqlalchemy import (
    Integer, String, ForeignKey, Numeric, Text, DateTime, CheckConstraint, UniqueConstraint, Index,
    Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.lib import BaseModel

class ShuttleMaintenanceWindow(BaseModel):
    """
    Shuttle Maintenance Record Model.

    Tracks maintenance activities for shuttle vessels.
    """

    __tablename__ = 'shuttle_maintenance_windows'
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Foreign Key
    # ---------------------------------------------------------------------
    shuttle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shuttles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ---------------------------------------------------------------------
    # Maintenance Details
    # ---------------------------------------------------------------------
    maintenance_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Type of maintenance (e.g., 'Dry Dock', 'Engine Overhaul')"
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed maintenance description"
    )

    # ---------------------------------------------------------------------
    # Scheduling
    # ---------------------------------------------------------------------
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Scheduled maintenance start date"
    )

    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Scheduled maintenance end date"
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    shuttle: Mapped["Shuttle"] = relationship(
        "Shuttle",
        back_populates="maintenance_windows",
        lazy="selectin"
    )

    # ---------------------------------------------------------------------
    # Indexes and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint("start_at < end_at", name="check_shuttle_maint_range"),
        Index("idx_shuttle_maint_time", "shuttle_id", "start_at"),
    )