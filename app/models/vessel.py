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
    CAPE = "capesize"

class Vessel(BaseModel):
    """Vessels owned or nominated by Alcoa"""

    __tablename__ = 'vessels'
    __mapper_args__ = {"eager_defaults": True}

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

    vtype: Mapped[VesselType] = mapped_column(
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
    # Foreign Keys
    # ---------------------------------------------------------------------
    owner_partner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    owner_partner: Mapped[Optional["Partner"]] = relationship(
        "Partner",
        back_populates="vessels",
        lazy="selectin"
    )
    
    shuttle: Mapped["Shuttle"] = relationship(
        "Shuttle",
        back_populates="vessel",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    lineups: Mapped[List["Lineup"]] = relationship(
        "Lineup",
        back_populates="vessel",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Vessel {self.name!r}>"

    def to_dict(self, include_audit: bool = False) -> Dict [str, Any]:
        d = super().to_dict(include_audit=include_audit)
        d.update({
            "name": self.name,
            "imo": self.imo,
            "vtype": self.vtype.value if self.vtype else None,
            "status": self.status.value if self.status else None,
            "dwt": self.dwt,
            "loa": self.loa,
            "beam": self.beam,
        })
        return d


