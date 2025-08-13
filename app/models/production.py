from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from app.lib import BaseModel

from enum import Enum
from datetime import datetime, date

from sqlalchemy import (
    CheckConstraint,
    UniqueConstraint,
    Index,
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates, object_session, Session
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date, timedelta
import json

class ProductionStatus(str, Enum):
    DRAFT = 'draft'
    PLANNED = 'planned'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'

class Production(BaseModel):
    """Production planning model with scenario management."""
    
    __tablename__='productions'
    __mapper_args__={"eager_defaults": True}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    scenario_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment='Name of the scenario'
    )
    
    scenario_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True, 
        comment='Description'
    )
    
    contractual_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Contractual Year'
    )
    
    total_planned_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Total Tonnage planned (3% moisture)'
    )
    
    start_date_contractual_year: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment='Start Date of Contractual Year'
    )
    
    end_date_contractual_year: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment='End Date of Contractual Year'
    )
    
    standard_moisture_content: Mapped[Decimal] = mapped_column(
        Numeric(5,2),
        nullable=False,
        default=Decimal('3.00'),
        server_default=text("3.00"),
        comment='Moisture basis'
    )
    
    # ---------------------------------------------------------------------
    # Status Management
    # ---------------------------------------------------------------------
    status: Mapped[ProductionStatus] = mapped_column(
        SQLEnum(ProductionStatus, name='production_status', native_enum=True, create_constraint=True, validate_strings=True),
        nullable=False,
        default=ProductionStatus.DRAFT,
        server_default=text("'draft'"),
        comment='Scenario Status'
    )
    
    base_scenario_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('productions.id', ondelete='SET NULL'),
        nullable=True,
        comment='Original Scenario ID'
    )
    
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
        nullable=False
    )
    
    # ---------------------------------------------------------------------
    # Lifecycle Timestamps
    # ---------------------------------------------------------------------
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=None,
        nullable=True
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    enrolled_partners: Mapped[List['ProductionPartnerEnrollment']] = relationship(
        'ProductionPartnerEnrollment',
        back_populates='production', 
        cascade='all, delete-orphan', 
        single_parent=True, 
        passive_deletes=True,
        lazy="selectin"
    )
    
    base_scenario: Mapped[Optional['Production']] = relationship(
        'Production', 
        remote_side='Production.id', 
        backref='derived_scenarios')
    
    # ---------------------------------------------------------------------
    # Index and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        Index('idx_production_contractual_year', 'contractual_year'),
        Index('idx_production_year_status', 'contractual_year', 'status'),
        Index('uq_one_active_per_year', "contractual_year", unique=True, sqlite_where=(status == ProductionStatus.ACTIVE)),
        UniqueConstraint('contractual_year', 'scenario_name', 'version', name='uq_prod_year_name_version'),
        CheckConstraint('contractual_year BETWEEN 2000 AND 2100', name='check_contractual_year_range'),
        CheckConstraint('total_planned_tonnage > 0', name='check_total_planned_tonnage_positive'),
        CheckConstraint('standard_moisture_content BETWEEN 0 AND 100', name='check_moisture_content_range'),
        CheckConstraint('start_date_contractual_year < end_date_contractual_year', name='check_date_order')
    )
    
    def __repr__(self) -> str:
        return f'<Production "{self.scenario_name}" - {self.contractual_year} ({self.status.value})>'
    
    @validates("status")
    def _validate_single_active_per_year(self, key, value):
        """Checks when it is active"""
        if value == ProductionStatus.ACTIVE:
            sess = object_session(self)
            if sess is None:
                return value
            
            q = (
                sess.query(type(self))
                .filter(
                    type(self).contractual_year == self.contractual_year,
                    type(self).status == ProductionStatus.ACTIVE
                )
            )
            if self.id is not None:
                q = q.filter(type(self).id != self.id)
                
            if sess.query(q.exists()).scalar():
                raise ValueError(
                    f"There is already an ACTIVE scenario for the year {self.contractual_year}."
                )
        
        return value
    
    @property
    def duration_days(self) -> int:
        """Calculate duration of contractual year in days."""
        return (self.end_date_contractual_year - self.start_date_contractual_year).days +1

        
    def enrolled_partners_count(self) -> int:
        """Counts enrolled partners without forcing a full load of the relationship."""
        # se a relação já estiver no estado 'loaded', use len() — é O(1)
        if 'enrolled_partners' in self.__dict__:
            return len(self.enrolled_partners)

        sess = object_session(self)
        if sess is None:
            # fallback: se não estiver anexado, usar o que houver em memória
            return len(getattr(self, 'enrolled_partners', []) or [])
        # consulta leve com COUNT(*)
        from app.models.production import ProductionPartnerEnrollment  # import local p/ evitar circular
        return (
            sess.query(ProductionPartnerEnrollment)
            .filter(ProductionPartnerEnrollment.production_id == self.id)
            .count()
        )
        
    def get_enrolled_halco_buyers(self, session: 'Session') -> List['Partner']:
        """
        Returns partners enrolled in this production whose entity_type is HALCO.
        Works with either Partner.entity_type or Partner.entity.entity_type.
        """
        from app.models.partner import Partner, PartnerEntity, EntityTypeEnum
        from app.models.production import ProductionPartnerEnrollment as PPE

        # Tenta o campo direto em Partner; se não existir, join em PartnerEntity
        if hasattr(Partner, 'entity_type'):
            q = (
                session.query(Partner)
                .join(PPE, PPE.partner_id == Partner.id)
                .filter(PPE.production_id == self.id,
                        Partner.entity_type == EntityTypeEnum.HALCO)
            )
        else:
            q = (
                session.query(Partner)
                .join(PPE, PPE.partner_id == Partner.id)
                .join(PartnerEntity, Partner.entity_id == PartnerEntity.id)
                .filter(PPE.production_id == self.id,
                        PartnerEntity.entity_type == EntityTypeEnum.HALCO)
            )
        return q.all()
    
    def get_enrolled_offtakers(self, session: 'Session') -> List['Partner']:
        """
        Returns partners enrolled in this production whose entity_type is OFFTAKER.
        """
        from app.models.partner import Partner, PartnerEntity, EntityTypeEnum
        from app.models.production import ProductionPartnerEnrollment as PPE

        if hasattr(Partner, 'entity_type'):
            q = (
                session.query(Partner)
                .join(PPE, PPE.partner_id == Partner.id)
                .filter(PPE.production_id == self.id,
                        Partner.entity_type == EntityTypeEnum.OFFTAKER)
            )
        else:
            q = (
                session.query(Partner)
                .join(PPE, PPE.partner_id == Partner.id)
                .join(PartnerEntity, Partner.entity_id == PartnerEntity.id)
                .filter(PPE.production_id == self.id,
                        PartnerEntity.entity_type == EntityTypeEnum.OFFTAKER)
            )
        return q.all()
    
    @classmethod
    def get_current_active(cls, session: 'Session', year: Optional[int] = None) -> Optional['Production']:
        """
        Returns the ACTIVE production for the given year (defaults to today's year).
        Enforced by the partial unique index: at most one row can match.
        """
        y = year or date.today().year
        return (
            session.query(cls)
            .filter(cls.contractual_year == y, cls.status == ProductionStatus.ACTIVE)
            .one_or_none()
        )
        
    @classmethod
    def get_finalized_previous_years(cls, session: 'Session', up_to_year: Optional[int] = None) -> List['Production']:
        """
        Returns COMPLETED productions for years strictly less than up_to_year (defaults to today.year).
        """
        cutoff = up_to_year or date.today().year
        return (
            session.query(cls)
            .filter(cls.contractual_year < cutoff, cls.status == ProductionStatus.COMPLETED)
            .order_by(cls.contractual_year.desc(), cls.scenario_name.asc(), cls.version.desc())
            .all()
        )
        
class ProductionPartnerEnrollment(BaseModel):
    """Association model for production partner enrollment with vessel sizes and tonnage."""
    
    __tablename__ = 'production_partner_enrollment'
    __mapper_args__ = {"eager_defaults": True}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # ---------------------------------------------------------------------
    # Foreign Keys
    # ---------------------------------------------------------------------
    production_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('productions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('partners.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    # ---------------------------------------------------------------------
    # Vessel and Tonnage Information
    # ---------------------------------------------------------------------
    vessel_size_t: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Vessel Lot Size in 3% moisture"
    )
    
    minimum_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Minimum Tonnage in 3% moisture"
    )
    
    adjusted_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    
    manual_incentive_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="When the incentive tonnage is inserted manually"
    )
    
    calculated_incentive_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="When the incentive tonnage is inserted automatically"
    )
    
    # ---------------------------------------------------------------------
    # VLD Calculations
    # ---------------------------------------------------------------------
    calculated_vld_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False
    )
    
    calculated_vld_total_tonnage: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False
    )
    
    vld_tonnage_variance: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    production: Mapped['Production'] = relationship(
        'Production',
        back_populates='enrolled_partners',
        passive_deletes=True,
    )
    
    partner: Mapped['Partner'] = relationship(
        'Partner',
        back_populates='enrollments'
    )
    
    vlds: Mapped[List['VLD']] = relationship(
        'VLD',
        back_populates='production',
        passive_delete=True
    )
    
    # ---------------------------------------------------------------------
    # Indexes and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        Index('idx_partner', 'partner_id'),
        UniqueConstraint('production_id', 'partner_id', name='uq_prod_partner'),
        CheckConstraint('vessel_size_t > 0', name='check_vessel_size_positive'),
        CheckConstraint('minimum_tonnage >= 0', name='check_min_tonnage_nonneg'),
        CheckConstraint('adjusted_tonnage IS NULL OR adjusted_tonnage >= 0', name='check_adjusted_tonnage_nonneg'),
        CheckConstraint('manual_incentive_tonnage IS NULL OR manual_incentive_tonnage >= 0', name='check_manual_incentive_nonneg'),
        CheckConstraint(
            'NOT (manual_incentive_tonnage IS NOT NULL AND calculated_incentive_tonnage IS NOT NULL)',
            name='check_incentive_manual_xor_calc'
        ),
    )
    
    @property
    def incentive_tonnage(self) -> int:
        return (
            self.manual_incentive_tonnage
            if self.manual_incentive_tonnage is not None
            else (self.calculated_incentive_tonnage or 0)
        )
        
    def __repr__(self) -> str:
        return f'<PPE id={self.id} prod={self.production_id} partner={self.partner_id} lot={self.vessel_size_t}>'
