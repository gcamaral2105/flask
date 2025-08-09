from __future__ import annotations

from app.extensions import db
from app.lib import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy import func


class PartnerEntity(BaseModel):
    """
    Partner Entity Model
    
    Represents a buyer entity in the bauxite supply chain.
    An entity can be either a Halco buyer or not, and can have
    multiple partners (clients) associated with it.
    """

    __tablename__ = 'partner_entities'

    id: int = db.Column(db.Integer, primary_key=True)
    
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    name: str = db.Column(
        db.String(100), 
        nullable=False,
        comment="Name of the entity"
    )
    
    code: str = db.Column(
        db.String(20), 
        unique=True, 
        nullable=False,
        comment="Code of the entity"
    )
    
    description: Optional[str] = db.Column(
        db.Text,
        comment="Description"
    )

    is_halco_buyer: bool = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        comment="If is Halco Buyer or not"
    )

    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    partners = db.relationship(
        'Partner', 
        back_populates='entity', 
        lazy='selectin', 
        cascade='all, delete-orphan',
        passive_deletes=True
    )
    
    # ---------------------------------------------------------------------
    # Table constraints and indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        db.Index('idx_entity_halco', 'is_halco_buyer'),
    )

    # ---------------------------------------------------------------------
    # Validation and serialization
    # ---------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Validate the partner entity data."""
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Entity name is required")
            
        if not self.code or not self.code.strip():
            errors.append("Entity code is required")
            
        if len(self.name) > 100:
            errors.append("Entity name must be 100 characters or less")
            
        if len(self.code) > 20:
            errors.append("Entity code must be 20 characters or less")
            
        return errors

    def __repr__(self) -> str:
        buyer_type = "Halco Buyer" if self.is_halco_buyer else "Offtaker"
        return f'<PartnerEntity {self.name} ({buyer_type})>'
    
    def to_dict(self, include_partners: bool = False, include_audit: bool = True) -> Dict[str, Any]:
        """Convert to dictionary with optional partner inclusion."""
        result = super().to_dict(include_audit=include_audit)
        result['partners_count'] = self.partners_count
        
        if include_partners:
            result['partners'] = [p.to_dict(include_audit=include_audit) for p in self.partners]
            
        return result


class Partner(BaseModel):
    """
    Partner Model
    
    Represents a specific client within a partner entity.
    Each partner belongs to an entity and has minimum contractual tonnage.
    """

    __tablename__ = 'partners'

    id: int = db.Column(db.Integer, primary_key=True)
    
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    name: str = db.Column(
        db.String(100), 
        nullable=False,
        comment="Name of the partner"
    )
    
    code: str = db.Column(
        db.String(20), 
        unique=True, 
        nullable=False,
        comment="Code of the partner"
    )
    
    description: Optional[str] = db.Column(
        db.Text,
        comment="Description"
    )

    minimum_contractual_tonnage: Optional[int] = db.Column(
        db.Integer,
        comment="Minimum contractual tonnage (flexible, can change every contractual year)"
    )

    # ---------------------------------------------------------------------
    # Foreign key to parent entity
    # ---------------------------------------------------------------------
    entity_id: int = db.Column(
        db.Integer, 
        db.ForeignKey('partner_entities.id', ondelete='CASCADE'), 
        nullable=False,
        comment="Which entity belongs this partner"
    )

    entity = db.relationship('PartnerEntity', back_populates='partners', lazy='selectin')
    
    # ---------------------------------------------------------------------
    # Table constraints and indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        db.Index('idx_partner_entity', 'entity_id'),
        db.CheckConstraint('minimum_contractual_tonnage >= 0', name='ck_partner_tonnage_nonneg'),
    )

    # ---------------------------------------------------------------------
    # Validation and serialization
    # ---------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Validate the partner data."""
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Partner name is required")
            
        if not self.code or not self.code.strip():
            errors.append("Partner code is required")
            
        if not self.entity_id:
            errors.append("Partner must be associated with an entity")
            
        if len(self.name) > 100:
            errors.append("Partner name must be 100 characters or less")
            
        if len(self.code) > 20:
            errors.append("Partner code must be 20 characters or less")
            
        if self.minimum_contractual_tonnage is not None and self.minimum_contractual_tonnage < 0:
            errors.append("Minimum contractual tonnage cannot be negative")
            
        return errors

    def __repr__(self) -> str:
        entity_name = self.entity.name if self.entity else 'Unknown'
        return f'<Partner {self.name} (Entity: {entity_name})>'
    
    def to_dict(self, include_entity: bool = True, include_audit: bool = True) -> Dict[str, Any]:
        """Convert to dictionary with optional entity details."""
        result = super().to_dict(include_audit=include_audit)
        
        if include_entity and self.entity:
            result['entity_name'] = self.entity.name
            result['entity_code'] = self.entity.code
            result['is_halco_buyer'] = self.entity.is_halco_buyer
            
        return result
    
PartnerEntity.partners_count = db.column_property(
    db.select(func.count(Partner.id))
    .where(Partner.entity_id == PartnerEntity.id)
    .correlate_except(Partner)
    .scalar_subquery()
)

