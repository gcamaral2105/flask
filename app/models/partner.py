from __future__ import annotations

from typing import List, Optional, Dict, Any
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel  # seu mixin com to_dict(), timestamps etc.


class Partner(BaseModel):
    """
    Representa um parceiro (cliente / offtaker / operador etc.)
    """
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Vessels owned/operated by this partner (corrigido back_populates)
    vessels: Mapped[List["Vessel"]] = relationship(
        "Vessel",
        back_populates="owner_partner",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Partner {self.name!r}>"

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
        })
        return base
