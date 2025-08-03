from app.extensions import db
from app.lib import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum


class EntityTypeEnum(str, Enum):
    """Enumeration for partner entity types."""
    HALCO = 'halco_buyer'
    OFFTAKER = 'offtaker'


class PartnerEntity(BaseModel):
    """
    Partner Entity Model
    
    Represents one of the buyer's entities in the bauxite supply chain.
    An entity can be either a Halco buyer or an offtaker, and can have
    multiple partners (clients) associated with it.
    """

    __tablename__ = 'partner_entities'

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(
        db.String(100), 
        nullable=False,
        comment="Name of the partner entity"
    )
    code: str = db.Column(
        db.String(20), 
        unique=True, 
        nullable=False,
        comment="Unique code identifier for the entity"
    )
    description: Optional[str] = db.Column(
        db.Text,
        comment="Detailed description of the entity"
    )

    # Entity type classification
    entity_type: EntityTypeEnum = db.Column(
        db.Enum(EntityTypeEnum, name='entity_type_enum'),
        default=EntityTypeEnum.OFFTAKER,
        nullable=False,
        comment="Type of entity (Halco buyer or offtaker)"
    )

    # Relationships
    partners = db.relationship(
        'Partner', 
        backref='entity', 
        lazy='select', 
        cascade='all, delete-orphan'
    )
    
    # Table constraints and indexes
    __table_args__ = (
        db.Index('idx_entity_type', 'entity_type'),
        db.Index('idx_entity_code', 'code'),
    )

    def __repr__(self) -> str:
        return f'<PartnerEntity {self.name} ({self.entity_type.value})>'
    
    def to_dict(self, include_partners: bool = False, include_audit: bool = True) -> Dict[str, Any]:
        """
        Convert to dictionary with optional partner inclusion.
        
        Args:
            include_partners: Whether to include related partners
            include_audit: Whether to include audit fields
            
        Returns:
            Dictionary representation of the entity
        """
        result = super().to_dict(include_audit=include_audit)
        result['entity_type'] = self.entity_type.value
        
        if include_partners:
            result['partners'] = [p.to_dict(include_audit=include_audit) for p in self.partners]
        else:
            result['partners_count'] = len(self.partners)
            
        return result
    
    def validate(self) -> List[str]:
        """
        Validate the partner entity data.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Entity name is required")
            
        if not self.code or not self.code.strip():
            errors.append("Entity code is required")
            
        if len(self.name) > 100:
            errors.append("Entity name must be 100 characters or less")
            
        if len(self.code) > 20:
            errors.append("Entity code must be 20 characters or less")
            
        # Code should be alphanumeric and uppercase
        if self.code and not self.code.replace('_', '').replace('-', '').isalnum():
            errors.append("Entity code should contain only alphanumeric characters, hyphens, and underscores")
            
        return errors


class Partner(BaseModel):
    """
    Partner Model
    
    Represents a specific client within a partner entity.
    Each partner belongs to an entity and has specific volume requirements
    and distribution parameters.
    """

    __tablename__ = 'partners'

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(
        db.String(100), 
        nullable=False,
        comment="Name of the partner/client"
    )
    code: str = db.Column(
        db.String(20), 
        unique=True, 
        nullable=False,
        comment="Unique code identifier for the partner"
    )
    description: Optional[str] = db.Column(
        db.Text,
        comment="Detailed description of the partner"
    )

    # Foreign key to parent entity
    entity_id: int = db.Column(
        db.Integer, 
        db.ForeignKey('partner_entities.id', ondelete='CASCADE'), 
        nullable=False,
        comment="ID of the parent entity"
    )

    # Business parameters
    minimum_volume: Optional[int] = db.Column(
        db.Integer,
        comment="Minimum volume requirement in metric tons (3-month period)"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        db.Index('idx_partner_entity', 'entity_id'),
        db.Index('idx_partner_code', 'code'),
        db.CheckConstraint(
            'minimum_volume >= 0',
            name='positive_minimum_volume'
        ),
    )

    def __repr__(self) -> str:
        entity_name = self.entity.name if self.entity else 'Unknown'
        status = "Active" if self.is_active else "Inactive"
        return f'<Partner {self.name} ({entity_name}) - {status}>'
    
    def to_dict(self, include_entity: bool = True, include_audit: bool = True) -> Dict[str, Any]:
        """
        Convert to dictionary with optional entity details.
        
        Args:
            include_entity: Whether to include parent entity details
            include_audit: Whether to include audit fields
            
        Returns:
            Dictionary representation of the partner
        """
        result = super().to_dict(include_audit=include_audit)
        
        if include_entity and self.entity:
            result['entity_name'] = self.entity.name
            result['entity_type'] = self.entity.entity_type.value
        
        # Convert volume to float for JSON serialization
        if self.minimum_volume is not None:
            result['minimum_volume'] = float(self.minimum_volume)
            
        return result
    
    def validate(self) -> List[str]:
        """
        Validate the partner data.
        
        Returns:
            List of validation error messages (empty if valid)
        """
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
            
        # Volume validation
        if self.minimum_volume is not None and self.minimum_volume < 0:
            errors.append("Minimum volume cannot be negative")
            
        # Code should be alphanumeric and uppercase
        if self.code and not self.code.replace('_', '').replace('-', '').isalnum():
            errors.append("Partner code should contain only alphanumeric characters, hyphens, and underscores")
            
        return errors
    
    def get_volume_mt_per_month(self) -> Optional[float]:
        """
        Calculate average monthly volume requirement.
        
        Returns:
            Average monthly volume in metric tons, or None if not set
        """
        if self.minimum_volume is None:
            return None
        return self.minimum_volume / 3.0
    
    def activate(self, user_id: Optional[int] = None) -> None:
        """
        Activate the partner.
        
        Args:
            user_id: ID of the user performing the activation
        """
        self.is_active = True
        self.update_audit_fields(user_id)
    
    def deactivate(self, user_id: Optional[int] = None) -> None:
        """
        Deactivate the partner.
        
        Args:
            user_id: ID of the user performing the deactivation
        """
        self.is_active = False
        self.update_audit_fields(user_id)
    
    def toggle_status(self, user_id: Optional[int] = None) -> bool:
        """
        Toggle the partner's active status.
        
        Args:
            user_id: ID of the user performing the toggle
            
        Returns:
            New active status (True if now active, False if now inactive)
        """
        self.is_active = not self.is_active
        self.update_audit_fields(user_id)
        return self.is_active
    
    @classmethod
    def get_active_partners(cls):
        """
        Get all active partners.
        
        Returns:
            Query object for active partners
        """
        return cls.query.filter(cls.is_active == True)
    
    @classmethod
    def get_inactive_partners(cls):
        """
        Get all inactive partners.
        
        Returns:
            Query object for inactive partners
        """
        return cls.query.filter(cls.is_active == False)
    
    @classmethod
    def get_active_partners_by_entity(cls, entity_id: int):
        """
        Get all active partners for a specific entity.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            Query object for active partners of the entity
        """
        return cls.query.filter(
            cls.entity_id == entity_id,
            cls.is_active == True
        )