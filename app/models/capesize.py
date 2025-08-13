from __future__ import annotations
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, date
from enum import Enum
from sqlalchemy import (
    Index, CheckConstraint, UniqueConstraint, ForeignKey,
    Integer, String, Date, DateTime, Enum as SQLEnum, text, inspect
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.lib import BaseModel

class CapesizeStatus(str, Enum):
    SCHEDULED = 'scheduled'
    ARRIVED = 'arrived'
    LOADING = 'loading'
    COMPLETED = 'completed'
    DEPARTED = 'departed'

class CapesizeVessel(BaseModel):
    """Capesize vessel model for transloader operations."""
    __tablename__ = 'capesize_vessels'
    __mapper_args__ = {'eager_defaults': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Operational Parameter
    # ---------------------------------------------------------------------
    target_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Capesize Stowage Plan"
    )

    current_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # ---------------------------------------------------------------------
    # Scheduling
    # ---------------------------------------------------------------------
    layday_start: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    layday_end: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    ata_anchorage: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    departure_anchorage: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Scheduling
    # ---------------------------------------------------------------------
    status: Mapped[CapesizeStatus] = mapped_column(
        SQLEnum(CapesizeStatus, name='capesize_status'),
        nullable=False,
        default=CapesizeStatus.SCHEDULED
    )

    # ---------------------------------------------------------------------
    # Foreign Key
    # ---------------------------------------------------------------------
    partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="RESTRICT"),
        index=True
    )

    cape_vessel_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("vessels.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        index=True
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    partner: Mapped["Partner"] = relationship(
        "Partner",
        lazy="selectin"
    )

    cape_vessel: Mapped[Optional["Vessel"]] = relationship(
        "Vessel",
        lazy="selectin"
    )

    product: Mapped["Product"] = relationship(
        "Product",
        lazy="selectin"
    )

    cycles: Mapped[List["ShuttleOperation"]] = relationship(
        "ShuttleOperation",
        back_populates="cape_operation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin"
    )
    
    # ---------------------------------------------------------------------
    # Index and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint("target_tonnage > 0", name="check_cape_target_pos"),
        Index("idx_cape_partner_product", "partner_id", "product_id")
    )
    
    def __repr__(self):
        return f'<CapesizeVessel {self.vessel_name} - {self.current_tonnage}/{self.target_tonnage}MT>'