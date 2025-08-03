from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Any, Dict

from app.extensions import db
from app.lib import BaseModel
from sqlalchemy import CheckConstraint, UniqueConstraint


class Mine(BaseModel):
    """
    Mine Model

    Represents mining locations where bauxite is extracted.
    Each mine can produce multiple products.
    """

    __tablename__ = "mines"

    # ---------------------------------------------------------------------
    # Core identifiers
    # ---------------------------------------------------------------------
    id: int = db.Column(db.Integer, primary_key=True)

    name: str = db.Column(
        db.String(200),
        unique=True,
        nullable=False,
        index=True,      # (optional: unique already creates an index)
        comment="Unique mine name (human-readable)",
    )

    code: Optional[str] = db.Column(
        db.String(50),
        unique=True,
        nullable=True,
        index=True,      # (optional)
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
        comment="Number of ship-loaders available at the port",
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    products = db.relationship(
        "Product",
        back_populates="mine",
        cascade="all, delete-orphan",
        lazy="dynamic",
        passive_deletes=True,      # leverages DB-level ON DELETE CASCADE
    )

    # ---------------------------------------------------------------------
    # Table-level constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint("port_latitude BETWEEN -90 AND 90",   name="ck_mines_lat_range"),
        CheckConstraint("port_longitude BETWEEN -180 AND 180", name="ck_mines_lon_range"),
        CheckConstraint("port_berths >= 0",                    name="ck_mines_berths_nonneg"),
        CheckConstraint("port_shiploaders >= 0",               name="ck_mines_shiploaders_nonneg"),
    )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Mine {self.name!r}>"

    def to_dict(self, *, include_products: bool = False, include_audit: bool = True) -> Dict[str, Any]:
        """
        Serialize the mine to a dictionary.
        """
        result = super().to_dict(include_audit=include_audit)

        if include_products:
            result["products"] = [
                pr.to_dict(include_audit=include_audit) for pr in self.products.all()
            ]
        else:
            result["products_count"] = self.products.count()

        return result


class Product(BaseModel):
    """
    Commercial bauxite grade produced by one mine.
    """

    __tablename__ = "products"

    id: int = db.Column(db.Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Descriptors
    # ---------------------------------------------------------------------
    name: str = db.Column(
        db.String(100),
        nullable=False,
        comment="Grade / product name shown to customers; unique *per* mine",
    )

    code: Optional[str] = db.Column(
        db.String(50),
        unique=True,     # still globally unique
        nullable=True,
        index=True,      # (optional)
        comment="Internal short code (optional)",
    )

    description: Optional[str] = db.Column(db.Text)

    # ---------------------------------------------------------------------
    # Foreign key to Mine
    # ---------------------------------------------------------------------
    mine_id: int = db.Column(
        db.Integer,
        db.ForeignKey("mines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mine = db.relationship("Mine", back_populates="products")

    # ---------------------------------------------------------------------
    # Table-level constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        UniqueConstraint(
            "mine_id",
            "name",
            name="uq_products_mine_id_name"  # ensures per-mine uniqueness
        ),
    )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.code or self.name}>"

    def to_dict(self, *, include_relations: bool = True, include_audit: bool = True) -> Dict[str, Any]:
        """
        Serialize the product to a dictionary.
        """
        result = super().to_dict(include_audit=include_audit)

        if include_relations:
            result["mine"] = (
                {"id": self.mine.id, "name": self.mine.name} if self.mine else None
            )

        return result

    # ---------------------------------------------------------------------
    # Validation hook (optional business rules)
    # ---------------------------------------------------------------------
    def validate(self) -> List[str]:
        """
        Return a list of validation error messages.
        """
        errors: List[str] = []

        if not self.name or not self.name.strip():
            errors.append("Product name is required.")

        # Example extra rule:
        # if self.code and not re.fullmatch(r"[A-Z0-9_-]{2,50}", self.code):
        #     errors.append("Invalid code format.")

        return errors
