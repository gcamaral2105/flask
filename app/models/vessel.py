from __future__ import annotations
from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    Integer, String, ForeignKey, Numeric, DateTime, Boolean, CheckConstraint, UniqueConstraint, Index,
    Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.lib import BaseModel
from app.models.vessel import VesselType

class ShuttleStatus(str, Enum):
    ACTIVE = "active"
    MAINT = "maintenance"
    IDLE = "idle"

class Shuttle(BaseModel):
    """
    Model for specialized vessel type = SHUTTLE
    """

    __tablename__ = 'shuttles'
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Operational Parameters
    # ---------------------------------------------------------------------
    target_discharge_rate_tph: Mapped(Optional[int]) = mapped_column(
        Integer,
        nullable=True,
        comment="Targeted Offshore Transfer Rate"
    )

    target_loading_rate_tph: Mapped(Optional[int]) = mapped_column(
        Integer,
        nullable=True,
        comment="Targeted Offshore Transfer Rate"
    )

    status: Mapped[ShuttleStatus] = mapped_column(
        SQLEnum(ShuttleStatus, name='shuttle_status'),
        nullable=False,
        default=ShuttleStatus.ACTIVE
    )

    # ---------------------------------------------------------------------
    # Foreign Key
    # ---------------------------------------------------------------------
    vessel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vessels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    vessel: Mapped["Vessel"] = relationship(
        "Vessel",
        back_populates="shuttle",
        lazy="selectin"
    )

    maintenance_windows: Mapped[List["ShuttleMaintenanceWindow"]] = relationship(
        "ShuttleMaintenanceWindow",
        back_populates="shuttle",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin"
    )

    cycles: Mapped[List["ShuttleOperation"]] = relationship(
        "ShuttleOperation",
        back_populates="shuttle",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin"
    )

    # ---------------------------------------------------------------------
    # Indexes and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint("target_discharge_rate_tph IS NULL OR target_discharge_rate_tph > 0", name="check_shuttle_discharge_rate"),
        CheckConstraint("target_loading_rate_tph IS NULL OR target_loading_rate_tph > 0", name="check_shuttle_loading_rate"),
    )

    def __repr__(self) -> str:
        return f"<Shuttle {self.name!r} vessel={self.vessel_id}>"

    @validates("vessel")
    def _ensure_vessel_type(self, key, value):
        if value and getattr(value, "vtype", None) != VesselType.SHUTTLE:
            raise ValueError("Assigned vessel must be of type shuttle.")
        return value
    

class ShuttleOperationStatus(str, Enum):
    """Shuttle operation status"""
    PLANNED = 'planned'
    CBG_LOADING = 'cbg_loading'
    CBG_COMPLETED = 'cbg_completed'
    TRANSIT = 'transit'
    DISCHARGING = 'discharging'
    COMPLETED = 'completed'
    STOPPED = 'stopped'
    SUBLET = 'sublet'


class ShuttleOperation(BaseModel):
    """
    Shuttle Operation Model.
    """

    __tablename__ = 'shuttle_operations'
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    cape_vessel_name: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True
    )

    # ---------------------------------------------------------------------
    # Timestamps
    # ---------------------------------------------------------------------
    load_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    load_end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    sail_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    discharge_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    discharge_end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    return_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    # ---------------------------------------------------------------------
    # Volume
    # ---------------------------------------------------------------------
    volume: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Transfered tonnage"
    )

    # ---------------------------------------------------------------------
    # Subletting
    # ---------------------------------------------------------------------
    is_sublet: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    # ---------------------------------------------------------------------
    # Foreign Keys
    # ---------------------------------------------------------------------
    shuttle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shuttles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    loading_lineup_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("lineups.id", ondelete="SET NULL"), 
        nullable=True,
        index=True
    )

    cape_vessel_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("vessels.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    cape_operation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("capesize_vessels.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    loading_vld_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("vlds.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    sublet_partner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    sublet_vld_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("vlds.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    shuttle: Mapped["Shuttle"] = relationship(
        "Shuttle",
        back_populates="cycles",
        lazy="selectin"
    )

    loading_lineup: Mapped[Optional["Lineup"]] = relationship(
        "Lineup",
        lazy="selectin"
    )

    cape_vessel: Mapped[Optional["Vessel"]] = relationship(
        "Vessel",
        lazy="selectin"
    )

    cape_operation: Mapped[Optional["CapesizeVessel"]] = relationship(
        "CapesizeVessel",
        back_populates="cycles",
        lazy="selectin"
    )

    loading_vld: Mapped[Optional["VLD"]] = relationship(
        "VLD",
        foreign_keys=[loading_vld_id],
        lazy="selectin"
    )

    sublet_partner: Mapped[Optional["Partner"]] = relationship(
        "Partner",
        lazy="selectin"
    )

    sublet_vld: Mapped[Optional["VLD"]] = relationship(
        "VLD",
        foreign_keys=[sublet_vld_id],
        lazy="selectin"
    )

    # ---------------------------------------------------------------------
    # Indexes and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint("volume IS NOT NULL OR volume >= 0", name="check_cycle_volume_nonneg"),
        CheckConstraint("(load_start_at IS NOT NULL) OR (load_end_at IS NULL) OR (load_start_at <= load_end_at)", name="check_cycle_load_order"),
        CheckConstraint("(discharge_start_at IS NULL) OR (discharge_end_at IS NULL) OR (discharge_start_at <= discharge_end_at)", name="check_cycle_discharge_order"),
        Index("idx_cycle_shuttle_time", "shuttle_id", "load_start_at"),
    )

    @property
    def effective_partner_id(self) -> Optional[int]:
        if self.is_sublet and self.sublet_partner_id:
            return self.sublet_partner_id
        return getattr(self.loading_lineup, "partner_id", None)
    
    @property
    def effective_vld_id(self) -> Optional[int]:
        if self.is_sublet and self.sublet_vld_id:
            return self.sublet_vld_id
        return self.loading_vld_id or getattr(self.loading_lineup, "vld_id", None)
