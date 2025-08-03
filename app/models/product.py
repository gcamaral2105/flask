from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from app.extensions import db
from app.lib import BaseModel

class Mine(BaseModel):
    """
    Mine Model
    
    Represents mining locations where bauxite is extracted.
    Each mine can produce multiple product subtypes.
    """
    
    __tablename__ = 'mine'
    
    
    # ---------------------------------------------------------------------
    # Core identifiers
    # ---------------------------------------------------------------------
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(
        db.String(200),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique mine name (human-readable)",
    )
    
    code: Optional[str] = db.Column(
        db.String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="Short internal code (optional)",
    )
    
    # ---------------------------------------------------------------------
    # Port / logistics information
    # ---------------------------------------------------------------------
    port_location: str = db.Column(
        db.String(150),
        nullable=False,
        comment="Name of the export port used by this mine",
    )
    
    port_latitude: Decimal = db.Column(
        db.Numeric(9, 6),
        nullable=False,
        comment="Port latitude in decimal degrees (-90 … +90)",
    )
    
    port_longitude: Decimal = db.Column(
        db.Numeric(9, 6),
        nullable=False,
        comment="Port longitude in decimal degrees (-180 … +180)",
    )
    
    port_berths: int = db.Column(
        db.SmallInteger,
        nullable=False,
        default=1,
        comment="Number of berths available to load vessels",
    )
    
    port_shiploaders: int = db.Column(
        db.SmallInteger,
        nullable=False,
        default=1,
        comment="Number of shiploaders available at the port",
    )
    
    products = db.relationship(
        "Product",
        back_populates="mines",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        return f"<Mine: {self.name!r}>"
    
class Product(BaseModel):
    """
    Commercial bauxite grade produced by a single mine.
    """

    __tablename__ = "products"

    id: int = db.Column(db.Integer, primary_key=True)

    # Descriptors -----------------------------------------------------------
    name: str = db.Column(
        db.String(100),
        unique=True,              # prevents the same grade name at two mines
        nullable=False,
        comment="Grade / product name shown to customers",
    )
    code: Optional[str] = db.Column(
        db.String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="Internal short code (optional)",
    )
    description: Optional[str] = db.Column(db.Text)

    # FK to Mine ------------------------------------------------------------
    mine_id: int = db.Column(
        db.Integer,
        db.ForeignKey("mines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mine = db.relationship("Mine", back_populates="products")

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.code or self.name}>"