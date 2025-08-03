from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any, List

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

    id: int = db.Column(db.Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Core identifiers
    # ---------------------------------------------------------------------
    name: str = db.Column(
        db.String(200),
        nullable=False,
        comment="Mine name"
    )

    code: Optional[str] = db.Column(
        db.String(50),
        unique=True,
        nullable=True,
        comment="Mine Code (if not provided, will use name as main recognition)"
    )

    country: str = db.Column(
        db.String(100),
        nullable=False,
        comment="Country of the mine"
    )

    # ---------------------------------------------------------------------
    # Port information
    # ---------------------------------------------------------------------
    port_location: str = db.Column(
        db.String(150),
        nullable=False,
        comment="Port Location"
    )

    port_latitude: Decimal = db.Column(
        db.Numeric(9, 6),
        nullable=False,
        comment="Port Latitude"
    )

    port_longitude: Decimal = db.Column(
        db.Numeric(9, 6),
        nullable=False,
        comment="Port Longitude"
    )

    port_berths: int = db.Column(
        db.SmallInteger,
        nullable=False,
        default=1,
        comment="Port berths"
    )

    port_shiploaders: int = db.Column(
        db.SmallInteger,
        nullable=False,
        default=1,
        comment="Port shiploaders"
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    products = db.relationship(
        "Product",
        back_populates="mine",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # ---------------------------------------------------------------------
    # Table-level constraints and indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        CheckConstraint("port_latitude BETWEEN -90 AND 90", name="ck_mines_lat_range"),
        CheckConstraint("port_longitude BETWEEN -180 AND 180", name="ck_mines_lon_range"),
        CheckConstraint("port_berths >= 0", name="ck_mines_berths_nonneg"),
        CheckConstraint("port_shiploaders >= 0", name="ck_mines_shiploaders_nonneg"),
        db.Index('idx_mine_code', 'code'),
        db.Index('idx_mine_name', 'name'),
        db.Index('idx_mine_country', 'country'),
    )

    # ---------------------------------------------------------------------
    # Business methods
    # ---------------------------------------------------------------------
    def get_main_identifier(self) -> str:
        """
        Get the main recognition identifier for this mine.
        If mine has a code, the code will be the main recognition.
        If mine does not have a code, it will be the same as the name.
        """
        return self.code if self.code else self.name

    # ---------------------------------------------------------------------
    # Validation and serialization
    # ---------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Validate mine data."""
        errors = []

        if not self.name or not self.name.strip():
            errors.append("Mine name is required")

        if not self.country or not self.country.strip():
            errors.append("Country is required")

        if not self.port_location or not self.port_location.strip():
            errors.append("Port location is required")

        # Validate coordinates
        if not (-90 <= self.port_latitude <= 90):
            errors.append("Port latitude must be between -90 and 90 degrees")

        if not (-180 <= self.port_longitude <= 180):
            errors.append("Port longitude must be between -180 and 180 degrees")

        # Validate port facilities
        if self.port_berths < 0:
            errors.append("Port berths cannot be negative")

        if self.port_shiploaders < 0:
            errors.append("Port shiploaders cannot be negative")

        return errors

    def __repr__(self) -> str:
        return f"<Mine {self.get_main_identifier()!r}>"

    def to_dict(self, *, include_products: bool = False, include_audit: bool = True) -> Dict[str, Any]:
        """Serialize the mine to a dictionary."""
        result = super().to_dict(include_audit=include_audit)
        result['main_identifier'] = self.get_main_identifier()

        if include_products:
            result["products"] = [
                pr.to_dict(include_audit=include_audit) for pr in self.products.all()
            ]
        else:
            result["products_count"] = self.products.count()

        return result


class Product(BaseModel):
    """
    Product Model

    Represents a bauxite product produced by a mine.
    Two products can have the same name but from different mines,
    and they are not intended to be the same product.
    """

    __tablename__ = "products"

    id: int = db.Column(db.Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Core identifiers
    # ---------------------------------------------------------------------
    name: str = db.Column(
        db.String(100),
        nullable=False,
        comment="Name of the product"
    )

    code: Optional[str] = db.Column(
        db.String(50),
        unique=True,
        nullable=True,
        comment="Code of the product (globally unique if provided)"
    )

    description: Optional[str] = db.Column(
        db.Text,
        comment="Description"
    )

    # ---------------------------------------------------------------------
    # Foreign key to Mine
    # ---------------------------------------------------------------------
    mine_id: int = db.Column(
        db.Integer,
        db.ForeignKey("mines.id", ondelete="CASCADE"),
        nullable=False,
        comment="Mine related to the product"
    )

    mine = db.relationship("Mine", back_populates="products")

    # ---------------------------------------------------------------------
    # Table-level constraints and indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        # Products can have same name but different mines (no unique constraint on name alone)
        # Only code needs to be globally unique (handled by unique=True on code column)
        db.Index('idx_product_mine', 'mine_id'),
        db.Index('idx_product_code', 'code'),
        db.Index('idx_product_name', 'name'),
        db.Index('idx_product_mine_name', 'mine_id', 'name'),  # For queries by mine and name
    )

    # ---------------------------------------------------------------------
    # Validation and serialization
    # ---------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Validate product data."""
        errors = []

        if not self.name or not self.name.strip():
            errors.append("Product name is required")

        if not self.mine_id:
            errors.append("Product must be associated with a mine")

        return errors

    def __repr__(self) -> str:
        mine_identifier = self.mine.get_main_identifier() if self.mine else 'Unknown'
        product_identifier = self.code if self.code else self.name
        return f"<Product {product_identifier!r} (Mine: {mine_identifier})>"

    def to_dict(self, *, include_mine: bool = True, include_audit: bool = True) -> Dict[str, Any]:
        """Serialize the product to a dictionary."""
        result = super().to_dict(include_audit=include_audit)

        if include_mine and self.mine:
            result["mine"] = {
                "id": self.mine.id,
                "name": self.mine.name,
                "code": self.mine.code,
                "main_identifier": self.mine.get_main_identifier(),
                "country": self.mine.country
            }

        return result
