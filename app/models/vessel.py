from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from decimal import Decimal
from sqlalchemy import (
    Index, CheckConstraint, UniqueConstraint, ForeignKey,
    Integer, Numeric, String, DateTime, Enum as SQLEnum, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib import BaseModel

class VesselStatus(str, Enum):
    """Vessel operational status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"

class VesselType(str, Enum):
    """Vessel Type Enum"""
    SHUTTLE = "shuttle"
    PANAMAX = "panamax"
    OGV = "OGV"

class Vessel(BaseModel):
    """Vessels owned or nominated by Alcoa"""

    __tablename__ = 'vessels'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        comment="Vessel Name"
    )

    imo: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        comment="IMO (if it is known)"
    )

    # ---------------------------------------------------------------------
    # Vessel Classification
    # ---------------------------------------------------------------------

    type: Mapped[VesselType] = mapped_column(
        SQLEnum(VesselType, name="vessel_type"),
        nullable=False
    )

    status: Mapped[VesselStatus] = mapped_column(
        SQLEnum(VesselStatus, name="vessel_status"),
        nullable=False,
        default=VesselStatus.ACTIVE
    )

    # ---------------------------------------------------------------------
    # Specifications
    # ---------------------------------------------------------------------
    dwt: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Deadweight"
    )

    loa: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Length Overall in meters"
    )

    beam: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Length Overall in meters"
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    partner: Mapped["Partner"] = relationship(
        "Partner"
    )

    lineups: Mapped["Lineup"] = relationship(
        "Lineup",
        back_populates="vessel"
    )