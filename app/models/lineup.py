from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Index, CheckConstraint, UniqueConstraint, ForeignKey,
    Integer, String, DateTime, Enum as SQLEnum, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from app.lib import BaseModel

class LineupStatus(str, Enum):
    SCHEDULED = "scheduled"
    ETA_RECEIVED = "eta_received"
    ARRIVED = "arrived"
    NOR_TENDERED = "nor_tendered"
    BERTHED = "berthed"
    LOADING = "loading"
    COMPLETED = "completed"
    DEPARTED = "departed"

class Lineup(BaseModel):
    """
    CBG Line-up model
    """
    __tablename__ = 'lineups'
    __mapper_args__ = {'eager_defaults': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    vessel_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True
    )

    # ---------------------------------------------------------------------
    # Foreign Keys
    # ---------------------------------------------------------------------
    vld_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vlds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("partners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    berth_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("berths.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # ---------------------------------------------------------------------
    # Status
    # ---------------------------------------------------------------------
    status: Mapped[LineupStatus] = mapped_column(
        SQLEnum(LineupStatus, name="lineup_status", native_enum=True, create_constraint=True, validate_strings=True),
        nullable=False,
        default=LineupStatus.SCHEDULED,
        server_default=text("'scheduled'")
    )

    # ---------------------------------------------------------------------
    # Timestamps
    # ---------------------------------------------------------------------
    eta: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    ata: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    nor_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    etb: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    atb: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    loading_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    loading_completion: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    ets: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    ats: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # ---------------------------------------------------------------------
    # Tonnage
    # ---------------------------------------------------------------------
    planned_tonnage: Mapped[Optional[int]] = mapped_column(
        Integer
    )

    actual_tonnage: Mapped[Optional[int]] = mapped_column(
        Integer
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    vld: Mapped["VLD"] = relationship(
        "VLD",
        back_populates="lineups",
        lazy="selectin"
    )

    partner: Mapped["Partner"] = relationship(
        "Partner",
        back_populates="lineups",
        lazy="selectin"
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="lineups",
        lazy="selectin"
    )

    berth: Mapped["Berth"] = relationship(
        "Berth",
        back_populates="lineups",
        lazy="selectin"
    )

    # ---------------------------------------------------------------------
    # Association Proxy
    # ---------------------------------------------------------------------
    mine = association_proxy("berth", "mine")

    __table_args__ = (
        UniqueConstraint("vld_id", "berth_id", name="uq_lineup_vld_berth"),
        CheckConstraint(
            "(planned_tonnage IS NULL OR planned_tonnage >= 0)"
            "AND (actual_tonnage IS NULL OR actual_tonnage >= 0)",
            name="check_lineup_tonnage_nonneg"
        ),
        Index("idx_lineup_status", "status"),
        Index("idx_lineup_partner_eta", "partner_id", "eta"),
        Index("idx_lineup_vld_dates", "vld_id", "etb", "loading_start"),
        Index("idx_lineup_berth_window", "berth_id", "etb", "atb")
    )

    def __repr__(self) -> str:
        return f"<Lineup {self.vessel_name} - {self.partner} - {self.vld}>"
    
    def to_dict(self, include_lineups: bool = False, include_audit: bool = True) -> Dict [str, Any]:
        "Serialize the lineup to a dictionary"
        result = super().to_dict(include_audit=include_audit)

        result.update({
            "vessel_name": self.vessel_name,
            "status": self.status.value if self.status else None,
            "vld_id": self.vld_id,
            "partner_id": self.partner_id,
            "product_id": self.product_id,
            "berth_id": self.berth_id,
            "eta": self.eta.isoformat() if self.eta else None,
            "ata": self.ata.isoformat() if self.ata else None,
            "nor_time": self.nor_time.isoformat() if self.nor_time else None,
            "etb": self.etb.isoformat() if self.etb else None,
            "atb": self.atb.isoformat() if self.atb else None,
            "loading_start": self.loading_start.isoformat() if self.loading_start else None,
            "loading_completion": self.loading_completion.isoformat() if self.loading_completion else None,
            "ets": self.ets.isoformat() if self.ets else None,
            "ats": self.ats.isoformat() if self.ats else None,
            "planned_tonnage": self.planned_tonnage,
            "actual_tonnage": self.actual_tonnage,
        })

        if include_lineups:
            result["mine"] = {
                "id": self.mine.id,
                "name": self.mine.name
            } if self.mine else None

        return result
