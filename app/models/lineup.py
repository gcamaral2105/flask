from __future__ import annotations
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Index, CheckConstraint, UniqueConstraint, ForeignKey,
    Integer, String, DateTime, Enum as SQLEnum, text, inspect
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
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

    vessel_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("vessels.id", ondelete="SET NULL"),
        nullable=True
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

    vessel: Mapped[Optional["Vessel"]] = relationship(
        "Vessel",
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
        CheckConstraint("ata <= atb", name="check_ata_atb"),
        CheckConstraint("atb <= loading_start", name="check_atb_loading_start"),
        CheckConstraint("loading_start <= loading_completion", name="check_loading_start_loading_completion"),
        CheckConstraint("loading_completion <= ats", name="check_loading_completion_ats"),
        Index("idx_lineup_status", "status"),
        Index("idx_lineup_partner_eta", "partner_id", "eta"),
        Index("idx_lineup_vld_dates", "vld_id", "etb", "loading_start"),
        Index("idx_lineup_berth_window", "berth_id", "etb", "atb")
    )

    @validates("vessel_id")
    def _sync_vessel_name(self, key, value):
        if value and self.vessel:
            self.vessel_name = self.vessel_name
        return value

    def __repr__(self) -> str:
        return f"<Lineup {self.vessel_name} - {self.partner} - {self.vld}>"
    
    def to_dict(self, *, include_audit: bool = False, expand: Optional[List[str]] = None, with_metrics: bool = True,) -> Dict [str, Any]:
        """
        Serializes Lineup with optional expansions and derived metrics.
        expand: e.g. ["partner", "product", "berth", "vld"]
        with_metrics: include derived KPIs (waiting time/loading/port_stay/progress)
        """

        expand = set(expand or [])
        result = super().to_dict(include_audit=include_audit)

        def _dt(d):
            return d.isoformat() if d else None
        
        def _hours(a, b):
            if a and b:
                secs = (b - a).total_seconds()
                return round(secs / 3600, 2) if secs >= 0 else None
            return None
        
        result.update({
            "vessel_name": self.vessel_name,
            "status": self.status.value if self.status else None,
            "eta": _dt(self.eta),
            "ata": _dt(self.ata),
            "nor_time": _dt(self.nor_time),
            "etb": _dt(self.etb),
            "atb": _dt(self.atb),
            "loading_start": _dt(self.loading_start),
            "loading_completion": _dt(self.loading_completion),
            "ets": _dt(self.ets),
            "ats": _dt(self.ats),
            "planned_tonnage": int(self.planned_tonnage) if self.planned_tonnage is not None else None,
            "actual_tonnage": int(self.actual_tonnage) if self.actual_tonnage is not None else None,
            "vld_id": self.vld_id,
            "partner_id": self.partner_id,
            "product_id": self.product_id,
            "berth_id": self.berth_id,
        })

        # Derived metrics
        if with_metrics:
            status_order = [
                "scheduled", "eta_received", "arrived", "nor_tendered",
                "berthed", "loading", "completed", "departed"
            ]
            try:
                idx = status_order.index(self.status.value) if self.status else 0
                progress_pct = round(100 * idx/(len(status_order) - 1), 1)
            except ValueError:
                progress_pct = None

            result['metrics'] = {
                "waiting_time_hours": _hours(self.ata, self.atb), # real arrival -> real berthing
                "loading_hours": _hours(self.loading_start, self.loading_completion),
                "port_stay_hours": _hours(self.ata, self.ats or self.loading_completion or self.atb),
                "progress_pct": progress_pct,
                "is_completed": self.status.value in {"completed", "departed"} if self.status else False,
            }

            # Timeline
            result["timeline"] = [
                {"event": "eta", "at": _dt(self.eta)},
                {"event": "ata", "at": _dt(self.ata)},
                {"event": "nor_tendered", "at": _dt(self.nor_time)},
                {"event": "etb", "at": _dt(self.etb)},
                {"event": "atb", "at": _dt(self.ata)},
                {"event": "loading_start", "at": _dt(self.loading_start)},
                {"event": "loadin_completion", "at": _dt(self.loading_completion)},
                {"event": "ets", "at": _dt(self.ets)},
                {"event": "ats", "at": _dt(self.ats)},
            ]

            # Secure expansions
            insp = inspect(self)

            def _expandable(name: str) -> bool:
                """Avoids non intentional lazy-loading"""
                return (name in expand) and (name not in getattr(insp, "unloaded", set()))
            
            # Partner
            if _expandable("partner") and self.partner:
                result["partner"] = {
                    "id": self.partner.id,
                    "name": self.partner.name,
                    "code": self.partner.code,
                    "entity_id": self.partner.entity_id,
                }

            # Product
            if _expandable("product") and self.product:
                result["product"] = {
                    "id": self.product.id,
                    "name": self.product.name,
                    "code": self.product.code,
                    "mine_id": self.product.mine_id
                }

            # Berth (+mine via berth)
            if _expandable("berth") and self.berth:
                result["berth"] = {
                    "id": self.berth.id,
                    "name": self.berth.name,
                    "priority": self.berth.priority,
                    "mine_id": self.berth.mine_id,
                    "mine_name": getattr(getattr(self.berth, "mine", None), "name", None)
                }

            # VLD
            if _expandable("vld") and self.vld:
                result["vld"] = {
                    "id": self.vld.id,
                    "vld_date": _dt(getattr(self.vld, "vld_date", None)),
                    "status": getattr(getattr(self.vld, "status", None), "value", None),
                    "planned_tonnage": getattr(self.vld, "planned_tonnage", None),
                }

            # Business Consistency Flags
            consistency = []
            try:
                if self.product and self.berth and self.product.mine_id != self.berth.mine_id:
                    consistency["mine_mismatch"] = True
            except Exception:
                pass
            if consistency:
                result["consistency_flags"] = consistency

            return result
