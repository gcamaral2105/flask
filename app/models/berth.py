from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from app.lib import BaseModel

from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    UniqueConstraint,
    Index,
    Boolean,
    SmallInteger,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
    sql
)

from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from datetime import datetime, date
import json

class Berth(BaseModel):
    __tablename__ = 'berths'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    mine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('mines.id', ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Mine that owns this berth"
    )
    
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Berth name or identifier"
    )
    
    # ---------------------------------------------------------------------
    # Operational track
    # ---------------------------------------------------------------------
    priority: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        comment="Scheduling priority (lower = first)"
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    mine: Mapped['Mine'] = relationship(
        'Mine',
        back_populates='berths'
    )
    
    __table_args__ = (
        UniqueConstraint('mine_id', 'name', name='uq_berth_mine_name'),
        CheckConstraint('priority > 0', name='check_berth_priority_nonneg'),
        CheckConstraint()
    )
    
    def __repr__(self) -> str:
        return f"<Berth {self.name!r} (Mine #{self.mine_id})>"

    def to_dict(self, *, include_mine: bool = False, include_audit: bool = True) -> Dict[str, Any]:
        data = super().to_dict(include_audit=include_audit)
        if include_mine and self.mine:
            data["mine"] = {
                "id": self.mine.id,
                "name": self.mine.name,
                "code": self.mine.code,
            }
        return data