"""
ERP Bauxita - Complete Model Collection
=====================================

This file contains all the final models developed for the ERP Bauxita supply chain system.
The models are designed for Flask with SQLAlchemy and provide comprehensive functionality
for managing bauxite supply chain operations.

Models included:
1. Partner Management (PartnerEntity, Partner)
2. Product Management (Mine, Product)
3. Production Planning (Production, ProductionPartnerEnrollment)
4. VLD Management (VLD, VLDReassignmentHistory, VLDCancellationHistory, VLDDeferralHistory)
5. CBG Port Operations (CBGPortLineup)
6. Transloader Operations (CapesizeVessel, TransloaderOperation, TransloaderSchedule)
7. Capesize Schedule (CapesizeScheduleEntry, CapesizeSchedule)

Author: ERP Bauxita Development Team
Framework: Flask + SQLAlchemy
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, Decimal, ForeignKey, Enum, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date, timedelta
from enum import Enum as PyEnum
from typing import Dict, List, Any, Optional
import json

# Initialize SQLAlchemy
db = SQLAlchemy()

# Base Model with Audit Trail
class BaseModel(db.Model):
    """Base model with audit trail functionality."""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, nullable=True)  # User ID
    updated_by = Column(Integer, nullable=True)  # User ID
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# =============================================================================
# PARTNER MANAGEMENT MODELS
# =============================================================================

class PartnerEntity(BaseModel):
    """Partner Entity model - represents buyer entities (Halco buyers vs offtakers)."""
    __tablename__ = 'partner_entities'
    
    # Core fields
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_halco_buyer = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    partners = relationship('Partner', back_populates='entity', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_partner_entity_code', 'code'),
        Index('idx_partner_entity_halco_buyer', 'is_halco_buyer'),
    )
    
    def __repr__(self):
        return f'<PartnerEntity "{self.name}" ({self.code})>'
    
    @classmethod
    def get_halco_buyers(cls):
        """Get all Halco buyer entities."""
        return cls.query.filter_by(is_halco_buyer=True).all()
    
    @classmethod
    def get_offtakers(cls):
        """Get all offtaker entities."""
        return cls.query.filter_by(is_halco_buyer=False).all()


class Partner(BaseModel):
    """Partner model - individual clients within entities."""
    __tablename__ = 'partners'
    
    # Core fields
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    minimum_contractual_tonnage = Column(Integer, nullable=True)
    
    # Foreign keys
    entity_id = Column(Integer, ForeignKey('partner_entities.id'), nullable=False)
    
    # Relationships
    entity = relationship('PartnerEntity', back_populates='partners')
    
    # Indexes
    __table_args__ = (
        Index('idx_partner_code', 'code'),
        Index('idx_partner_entity_id', 'entity_id'),
    )
    
    def __repr__(self):
        return f'<Partner "{self.name}" ({self.code})>'
    
    @property
    def is_halco_buyer(self):
        """Check if partner belongs to Halco buyer entity."""
        return self.entity.is_halco_buyer if self.entity else False


# =============================================================================
# PRODUCT MANAGEMENT MODELS
# =============================================================================

class Mine(BaseModel):
    """Mine model - mining locations with port information."""
    __tablename__ = 'mines'
    
    # Core fields
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=True)
    country = Column(String(100), nullable=False)
    
    # Port information
    port_location = Column(String(255), nullable=False)
    port_latitude = Column(Decimal(10, 8), nullable=False)
    port_longitude = Column(Decimal(11, 8), nullable=False)
    port_berths = Column(Integer, default=1, nullable=False)
    port_shiploaders = Column(Integer, default=1, nullable=False)
    
    # Relationships
    products = relationship('Product', back_populates='mine', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_mine_code', 'code'),
        Index('idx_mine_country', 'country'),
        CheckConstraint('port_latitude >= -90 AND port_latitude <= 90', name='check_latitude_range'),
        CheckConstraint('port_longitude >= -180 AND port_longitude <= 180', name='check_longitude_range'),
        CheckConstraint('port_berths > 0', name='check_port_berths_positive'),
        CheckConstraint('port_shiploaders > 0', name='check_port_shiploaders_positive'),
    )
    
    def __repr__(self):
        return f'<Mine "{self.get_main_identifier()}">'
    
    def get_main_identifier(self):
        """Get main identifier - code if available, otherwise name."""
        return self.code if self.code else self.name


class Product(BaseModel):
    """Product model - bauxite products from mines."""
    __tablename__ = 'products'
    
    # Core fields
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    
    # Foreign keys
    mine_id = Column(Integer, ForeignKey('mines.id'), nullable=False)
    
    # Relationships
    mine = relationship('Mine', back_populates='products')
    
    # Indexes
    __table_args__ = (
        Index('idx_product_code', 'code'),
        Index('idx_product_mine_id', 'mine_id'),
        Index('idx_product_mine_name', 'mine_id', 'name'),  # Composite index for mine + name queries
    )
    
    def __repr__(self):
        return f'<Product "{self.name}" from {self.mine.get_main_identifier() if self.mine else "Unknown Mine"}>'


# =============================================================================
# PRODUCTION PLANNING MODELS
# =============================================================================

class Production(BaseModel):
    """Production planning model with scenario management."""
    __tablename__ = 'productions'
    
    # Core fields
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    contractual_year = Column(Integer, nullable=False)
    total_planned_tonnage = Column(Integer, nullable=False)
    start_date_contractual_year = Column(Date, nullable=False)
    end_date_contractual_year = Column(Date, nullable=False)
    standard_moisture_content = Column(Decimal(5, 2), nullable=False)
    
    # Status management
    is_draft = Column(Boolean, default=True, nullable=False)
    is_current_active_plan = Column(Boolean, default=False, nullable=False)
    
    # Scenario management
    scenario_name = Column(String(255), nullable=False)
    scenario_description = Column(Text, nullable=True)
    status = Column(Enum('draft', 'finalized', 'active', 'completed', 'archived', name='production_status'), 
                   default='draft', nullable=False)
    is_active_scenario = Column(Boolean, default=False, nullable=False)
    base_scenario_id = Column(Integer, ForeignKey('productions.id'), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    
    # Lifecycle timestamps
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    enrolled_partners = relationship('ProductionPartnerEnrollment', back_populates='production', cascade='all, delete-orphan')
    base_scenario = relationship('Production', remote_side=[id])
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_production_contractual_year', 'contractual_year'),
        Index('idx_production_status', 'status'),
        Index('idx_production_active_scenario', 'contractual_year', 'is_active_scenario'),
        Index('idx_production_scenario', 'contractual_year', 'is_draft', 'is_current_active_plan'),
        UniqueConstraint('contractual_year', 'is_current_active_plan', name='uq_one_active_plan_per_year'),
        UniqueConstraint('contractual_year', 'is_active_scenario', name='uq_one_active_scenario_per_year'),
        CheckConstraint('contractual_year >= 2000 AND contractual_year <= 2100', name='check_contractual_year_range'),
        CheckConstraint('total_planned_tonnage > 0', name='check_total_planned_tonnage_positive'),
        CheckConstraint('standard_moisture_content >= 0 AND standard_moisture_content <= 100', name='check_moisture_content_range'),
        CheckConstraint('start_date_contractual_year < end_date_contractual_year', name='check_date_order'),
    )
    
    def __repr__(self):
        status_indicator = "Active" if self.is_active_scenario else "Draft" if self.is_draft else "Finalized"
        return f'<Production "{self.name}" - {self.contractual_year} ({status_indicator})>'
    
    @validates('is_current_active_plan')
    def validate_active_plan(self, key, value):
        """Ensure only finalized plans can be active."""
        if value and self.is_draft:
            raise ValueError("Draft plans cannot be set as active")
        return value
    
    def get_contractual_year_duration_days(self):
        """Calculate duration of contractual year in days."""
        return (self.end_date_contractual_year - self.start_date_contractual_year).days + 1
    
    def get_enrolled_partners_count(self):
        """Get count of enrolled partners."""
        return len(self.enrolled_partners)
    
    def get_enrolled_halco_buyers(self):
        """Get enrolled Halco buyer partners."""
        return [enrollment for enrollment in self.enrolled_partners 
                if enrollment.partner.is_halco_buyer]
    
    def get_enrolled_offtakers(self):
        """Get enrolled offtaker partners."""
        return [enrollment for enrollment in self.enrolled_partners 
                if not enrollment.partner.is_halco_buyer]
    
    @classmethod
    def get_current_active_plan(cls):
        """Get the current active production plan."""
        return cls.query.filter_by(is_current_active_plan=True).first()
    
    @classmethod
    def get_plans_by_year(cls, year):
        """Get all production plans for a specific year."""
        return cls.query.filter_by(contractual_year=year).all()
    
    @classmethod
    def get_active_plan_by_year(cls, year):
        """Get the active production plan for a specific year."""
        return cls.query.filter_by(contractual_year=year, is_current_active_plan=True).first()


class ProductionPartnerEnrollment(BaseModel):
    """Association model for production partner enrollment with vessel sizes and tonnage."""
    __tablename__ = 'production_partner_enrollments'
    
    # Foreign keys
    production_id = Column(Integer, ForeignKey('productions.id'), nullable=False)
    partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    
    # Vessel and tonnage information
    vessel_size_kt = Column(Integer, nullable=False)
    minimum_tonnage = Column(Integer, nullable=False)
    adjusted_tonnage = Column(Integer, nullable=True)
    manual_incentive_tonnage = Column(Integer, nullable=True)
    calculated_incentive_tonnage = Column(Integer, nullable=True)
    
    # VLD calculations (no partial VLDs)
    calculated_vld_count = Column(Integer, nullable=True)
    calculated_vld_total_tonnage = Column(Integer, nullable=True)
    vld_tonnage_variance = Column(Integer, nullable=True)  # Remaining tonnage that doesn't fit in full VLDs
    
    # Relationships
    production = relationship('Production', back_populates='enrolled_partners')
    partner = relationship('Partner')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_production_partner_enrollment', 'production_id', 'partner_id'),
        Index('idx_production_partner_vessel_size', 'vessel_size_kt'),
        UniqueConstraint('production_id', 'partner_id', name='uq_production_partner_enrollment'),
        CheckConstraint('vessel_size_kt >= 10 AND vessel_size_kt <= 500', name='check_vessel_size_range'),
        CheckConstraint('minimum_tonnage > 0', name='check_minimum_tonnage_positive'),
    )
    
    def __repr__(self):
        return f'<ProductionPartnerEnrollment {self.partner.name if self.partner else "Unknown"} - {self.vessel_size_kt}kt>'
    
    def get_final_tonnage(self):
        """Get final tonnage (minimum + effective incentive)."""
        return self.minimum_tonnage + self.get_effective_incentive_tonnage()
    
    def get_effective_incentive_tonnage(self):
        """Get effective incentive tonnage (manual if set, otherwise calculated)."""
        if self.manual_incentive_tonnage is not None:
            return self.manual_incentive_tonnage
        return self.calculated_incentive_tonnage or 0
    
    def get_incentive_source(self):
        """Get source of incentive tonnage."""
        if self.manual_incentive_tonnage is not None:
            return 'manual'
        elif self.calculated_incentive_tonnage is not None:
            return 'calculated'
        return 'none'
    
    def is_using_manual_incentive(self):
        """Check if using manual incentive."""
        return self.manual_incentive_tonnage is not None
    
    def calculate_vlds_no_partial(self):
        """Calculate VLDs without partial VLDs (only full vessel loads)."""
        final_tonnage = self.get_final_tonnage()
        vessel_size_mt = self.vessel_size_kt * 1000
        
        # Calculate only full VLDs
        full_vlds = final_tonnage // vessel_size_mt
        remaining_tonnage = final_tonnage % vessel_size_mt
        allocated_tonnage = full_vlds * vessel_size_mt
        
        # Update calculated fields
        self.calculated_vld_count = full_vlds
        self.calculated_vld_total_tonnage = allocated_tonnage
        self.vld_tonnage_variance = remaining_tonnage  # Remaining tonnage for allocation
        
        return {
            'status': 'calculated',
            'final_tonnage': final_tonnage,
            'vessel_size_mt': vessel_size_mt,
            'full_vlds': full_vlds,
            'allocated_tonnage': allocated_tonnage,
            'remaining_tonnage': remaining_tonnage,
            'vld_count': full_vlds,
            'vld_total_tonnage': allocated_tonnage
        }
    
    def get_remaining_tonnage(self):
        """Get remaining tonnage that doesn't fit in full VLDs."""
        return self.vld_tonnage_variance or 0
    
    def has_remaining_tonnage(self):
        """Check if partner has remaining tonnage."""
        return self.get_remaining_tonnage() > 0
    
    def allocate_additional_tonnage(self, additional_tonnage):
        """Allocate additional tonnage from other partners' remaining tonnage."""
        vessel_size_mt = self.vessel_size_kt * 1000
        
        # Add additional tonnage
        current_allocated = self.calculated_vld_total_tonnage or 0
        new_total_tonnage = current_allocated + additional_tonnage
        
        # Recalculate VLDs with new tonnage
        full_vlds = new_total_tonnage // vessel_size_mt
        remaining_tonnage = new_total_tonnage % vessel_size_mt
        allocated_tonnage = full_vlds * vessel_size_mt
        
        # Update fields
        self.calculated_vld_count = full_vlds
        self.calculated_vld_total_tonnage = allocated_tonnage
        self.vld_tonnage_variance = remaining_tonnage
        
        return {
            'additional_tonnage_allocated': additional_tonnage,
            'new_vld_count': full_vlds,
            'new_allocated_tonnage': allocated_tonnage,
            'new_remaining_tonnage': remaining_tonnage
        }


# =============================================================================
# VLD MANAGEMENT MODELS
# =============================================================================

class VLDStatus(PyEnum):
    """VLD status enumeration."""
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    NARROW_RECEIVED = "narrow_received"
    LOADING = "loading"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VLD(BaseModel):
    """VLD (Vessel Loading Date) model with comprehensive management."""
    __tablename__ = 'vlds'
    
    # Core VLD information
    vld_date = Column(Date, nullable=False)
    original_vld_date = Column(Date, nullable=False)  # Never changes
    vld_number = Column(String(50), unique=True, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    planned_tonnage = Column(Integer, nullable=False)
    vessel_size_kt = Column(Integer, nullable=False)
    
    # Status and vessel information
    status = Column(Enum(VLDStatus), default=VLDStatus.PLANNED, nullable=False)
    vessel_name = Column(String(255), nullable=True)
    
    # Loader number (assigned only when vessel is loaded)
    loader_number = Column(String(50), unique=True, nullable=True)
    loader_assigned_at = Column(DateTime, nullable=True)
    loader_assigned_by = Column(Integer, nullable=True)  # User ID
    
    # Layday and narrow period management
    layday_start = Column(Date, nullable=True)
    layday_end = Column(Date, nullable=True)
    narrow_period_start = Column(Date, nullable=True)
    narrow_period_end = Column(Date, nullable=True)
    
    # Operational tracking
    actual_tonnage = Column(Integer, nullable=True)
    moisture_content = Column(Decimal(5, 2), nullable=True)
    loading_start_time = Column(DateTime, nullable=True)
    loading_completion_time = Column(DateTime, nullable=True)
    
    # Partner management and reassignment
    original_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    current_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    reassignment_count = Column(Integer, default=0, nullable=False)
    last_reassigned_at = Column(DateTime, nullable=True)
    last_reassigned_by = Column(Integer, nullable=True)
    last_reassignment_reason = Column(Text, nullable=True)
    
    # Cancellation management
    cancelled_reason = Column(Text, nullable=True)
    cancelled_date = Column(DateTime, nullable=True)
    cancelled_by = Column(Integer, nullable=True)
    status_before_cancellation = Column(Enum(VLDStatus), nullable=True)
    uncancelled_reason = Column(Text, nullable=True)
    uncancelled_date = Column(DateTime, nullable=True)
    uncancelled_by = Column(Integer, nullable=True)
    cancellation_count = Column(Integer, default=0, nullable=False)
    
    # Deferral management
    is_deferred = Column(Boolean, default=False, nullable=False)
    total_deferred_days = Column(Integer, default=0, nullable=False)
    deferral_count = Column(Integer, default=0, nullable=False)
    
    # Foreign keys
    production_id = Column(Integer, ForeignKey('productions.id'), nullable=False)
    
    # Relationships
    production = relationship('Production')
    original_partner = relationship('Partner', foreign_keys=[original_partner_id])
    current_partner = relationship('Partner', foreign_keys=[current_partner_id])
    reassignment_history = relationship('VLDReassignmentHistory', back_populates='vld', cascade='all, delete-orphan')
    cancellation_history = relationship('VLDCancellationHistory', back_populates='vld', cascade='all, delete-orphan')
    deferral_history = relationship('VLDDeferralHistory', back_populates='vld', cascade='all, delete-orphan')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_vld_date', 'vld_date'),
        Index('idx_vld_original_date', 'original_vld_date'),
        Index('idx_vld_production_id', 'production_id'),
        Index('idx_vld_current_partner', 'current_partner_id'),
        Index('idx_vld_status', 'status'),
        Index('idx_vld_loader_number', 'loader_number'),
        CheckConstraint('planned_tonnage > 0', name='check_planned_tonnage_positive'),
        CheckConstraint('vessel_size_kt > 0', name='check_vessel_size_positive'),
        CheckConstraint('moisture_content >= 0 AND moisture_content <= 100', name='check_moisture_content_range'),
    )
    
    def __repr__(self):
        return f'<VLD {self.vld_number} - {self.vld_date} ({self.status.value})>'
    
    def calculate_layday_period(self):
        """Calculate layday period (VLD - 5 days to VLD + 6 days)."""
        self.layday_start = self.vld_date - timedelta(days=5)
        self.layday_end = self.vld_date + timedelta(days=6)
        return {
            'layday_start': self.layday_start,
            'layday_end': self.layday_end,
            'layday_duration_days': 12
        }
    
    def set_narrow_period(self, start_date: date, end_date: date):
        """Set narrow period (7-day window within layday)."""
        # Validate narrow period
        if (end_date - start_date).days + 1 > 7:
            raise ValueError("Narrow period cannot exceed 7 days")
        
        if not self.layday_start or not self.layday_end:
            self.calculate_layday_period()
        
        if start_date < self.layday_start or end_date > self.layday_end:
            raise ValueError("Narrow period must be within layday period")
        
        self.narrow_period_start = start_date
        self.narrow_period_end = end_date
        
        # Update status if confirmed
        if self.status == VLDStatus.CONFIRMED:
            self.status = VLDStatus.NARROW_RECEIVED
        
        return {
            'narrow_period_start': self.narrow_period_start,
            'narrow_period_end': self.narrow_period_end,
            'narrow_period_days': (end_date - start_date).days + 1
        }
    
    def assign_loader_number(self, loader_number: str, assigned_by_user_id: int):
        """Assign loader number when vessel is loading."""
        # Validate status
        if self.status not in [VLDStatus.LOADING, VLDStatus.COMPLETED]:
            raise ValueError("Loader number can only be assigned during loading or after completion")
        
        # Check uniqueness
        existing = VLD.query.filter_by(loader_number=loader_number).first()
        if existing and existing.id != self.id:
            raise ValueError(f"Loader number {loader_number} is already assigned")
        
        self.loader_number = loader_number
        self.loader_assigned_at = datetime.utcnow()
        self.loader_assigned_by = assigned_by_user_id
        
        return {
            'loader_number': self.loader_number,
            'assigned_at': self.loader_assigned_at,
            'assigned_by': self.loader_assigned_by
        }
    
    def reassign_to_partner(self, new_partner_id: int, reason: str, user_id: int):
        """Reassign VLD to different partner."""
        if not self.can_be_reassigned():
            restrictions = self.get_reassignment_restrictions()
            raise ValueError(f"VLD cannot be reassigned: {', '.join(restrictions)}")
        
        old_partner_id = self.current_partner_id
        
        # Create history record
        history = VLDReassignmentHistory(
            vld_id=self.id,
            from_partner_id=old_partner_id,
            to_partner_id=new_partner_id,
            reason=reason,
            reassigned_by=user_id,
            reassigned_at=datetime.utcnow()
        )
        db.session.add(history)
        
        # Update VLD
        self.current_partner_id = new_partner_id
        self.reassignment_count += 1
        self.last_reassigned_at = datetime.utcnow()
        self.last_reassigned_by = user_id
        self.last_reassignment_reason = reason
        
        # Reset narrow period (new partner must set their own)
        self.narrow_period_start = None
        self.narrow_period_end = None
        if self.status == VLDStatus.NARROW_RECEIVED:
            self.status = VLDStatus.CONFIRMED
        
        return {
            'status': 'reassigned',
            'from_partner_id': old_partner_id,
            'to_partner_id': new_partner_id,
            'reassignment_count': self.reassignment_count
        }
    
    def can_be_reassigned(self):
        """Check if VLD can be reassigned."""
        return self.status not in [VLDStatus.LOADING, VLDStatus.COMPLETED]
    
    def get_reassignment_restrictions(self):
        """Get list of restrictions preventing reassignment."""
        restrictions = []
        if self.status == VLDStatus.LOADING:
            restrictions.append("VLD is currently loading")
        if self.status == VLDStatus.COMPLETED:
            restrictions.append("VLD is already completed")
        return restrictions
    
    def cancel_vld(self, reason: str, cancelled_by_user_id: int):
        """Cancel VLD with reason and user tracking."""
        if self.status == VLDStatus.CANCELLED:
            raise ValueError("VLD is already cancelled")
        
        # Store status before cancellation for potential uncancellation
        self.status_before_cancellation = self.status
        
        # Create history record
        history = VLDCancellationHistory(
            vld_id=self.id,
            action_type='cancelled',
            status_before=self.status.value,
            status_after='cancelled',
            reason=reason,
            action_by=cancelled_by_user_id,
            action_at=datetime.utcnow()
        )
        db.session.add(history)
        
        # Update VLD
        self.status = VLDStatus.CANCELLED
        self.cancelled_reason = reason
        self.cancelled_date = datetime.utcnow()
        self.cancelled_by = cancelled_by_user_id
        self.cancellation_count += 1
        
        # Clear loader number if assigned
        if self.loader_number:
            self.loader_number = None
            self.loader_assigned_at = None
            self.loader_assigned_by = None
        
        return {
            'status': 'cancelled',
            'reason': reason,
            'cancelled_at': self.cancelled_date,
            'previous_status': self.status_before_cancellation.value
        }
    
    def uncancel_vld(self, reason: str, uncancelled_by_user_id: int):
        """Uncancel VLD and restore to previous status."""
        if not self.can_be_uncancelled():
            raise ValueError("VLD cannot be uncancelled")
        
        previous_status = self.status_before_cancellation
        
        # Create history record
        history = VLDCancellationHistory(
            vld_id=self.id,
            action_type='uncancelled',
            status_before='cancelled',
            status_after=previous_status.value,
            reason=reason,
            action_by=uncancelled_by_user_id,
            action_at=datetime.utcnow()
        )
        db.session.add(history)
        
        # Restore VLD
        self.status = previous_status
        self.uncancelled_reason = reason
        self.uncancelled_date = datetime.utcnow()
        self.uncancelled_by = uncancelled_by_user_id
        
        # Clear cancellation fields
        self.cancelled_reason = None
        self.cancelled_date = None
        self.cancelled_by = None
        self.status_before_cancellation = None
        
        return {
            'status': 'uncancelled',
            'restored_status': previous_status.value,
            'reason': reason,
            'uncancelled_at': self.uncancelled_date
        }
    
    def can_be_uncancelled(self):
        """Check if VLD can be uncancelled."""
        return (self.status == VLDStatus.CANCELLED and 
                self.status_before_cancellation is not None)
    
    def defer_vld(self, days: int, reason: str, user_id: int):
        """Defer VLD by specified number of days."""
        if self.status in [VLDStatus.LOADING, VLDStatus.COMPLETED, VLDStatus.CANCELLED]:
            raise ValueError(f"Cannot defer VLD with status: {self.status.value}")
        
        old_date = self.vld_date
        new_date = self.vld_date + timedelta(days=days)
        
        # Create history record
        history = VLDDeferralHistory(
            vld_id=self.id,
            old_vld_date=old_date,
            new_vld_date=new_date,
            days_deferred=days,
            reason=reason,
            deferred_by=user_id,
            deferred_at=datetime.utcnow()
        )
        db.session.add(history)
        
        # Update VLD
        self.vld_date = new_date
        self.is_deferred = True
        self.total_deferred_days += days
        self.deferral_count += 1
        
        # Recalculate layday period
        self.calculate_layday_period()
        
        # Reset narrow period (partner must set new narrow period)
        self.narrow_period_start = None
        self.narrow_period_end = None
        if self.status == VLDStatus.NARROW_RECEIVED:
            self.status = VLDStatus.CONFIRMED
        
        return {
            'status': 'deferred',
            'old_date': old_date,
            'new_date': new_date,
            'days_deferred': days,
            'total_deferred_days': self.total_deferred_days,
            'new_layday_start': self.layday_start,
            'new_layday_end': self.layday_end
        }
    
    def is_reassigned(self):
        """Check if VLD has been reassigned."""
        return self.current_partner_id != self.original_partner_id
    
    def is_cancelled(self):
        """Check if VLD is cancelled."""
        return self.status == VLDStatus.CANCELLED
    
    def has_loader_number(self):
        """Check if VLD has loader number assigned."""
        return self.loader_number is not None


class VLDReassignmentHistory(BaseModel):
    """VLD reassignment history for audit trail."""
    __tablename__ = 'vld_reassignment_history'
    
    vld_id = Column(Integer, ForeignKey('vlds.id'), nullable=False)
    from_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    to_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    reason = Column(Text, nullable=False)
    reassigned_by = Column(Integer, nullable=False)  # User ID
    reassigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    vld = relationship('VLD', back_populates='reassignment_history')
    from_partner = relationship('Partner', foreign_keys=[from_partner_id])
    to_partner = relationship('Partner', foreign_keys=[to_partner_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_vld_reassignment_vld_id', 'vld_id'),
        Index('idx_vld_reassignment_date', 'reassigned_at'),
    )


class VLDCancellationHistory(BaseModel):
    """VLD cancellation/uncancellation history for audit trail."""
    __tablename__ = 'vld_cancellation_history'
    
    vld_id = Column(Integer, ForeignKey('vlds.id'), nullable=False)
    action_type = Column(Enum('cancelled', 'uncancelled', name='cancellation_action_type'), nullable=False)
    status_before = Column(String(50), nullable=False)
    status_after = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    action_by = Column(Integer, nullable=False)  # User ID
    action_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    vld = relationship('VLD', back_populates='cancellation_history')
    
    # Indexes
    __table_args__ = (
        Index('idx_vld_cancellation_vld_id', 'vld_id'),
        Index('idx_vld_cancellation_action', 'action_type'),
        Index('idx_vld_cancellation_date', 'action_at'),
    )


class VLDDeferralHistory(BaseModel):
    """VLD deferral history for audit trail."""
    __tablename__ = 'vld_deferral_history'
    
    vld_id = Column(Integer, ForeignKey('vlds.id'), nullable=False)
    old_vld_date = Column(Date, nullable=False)
    new_vld_date = Column(Date, nullable=False)
    days_deferred = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    deferred_by = Column(Integer, nullable=False)  # User ID
    deferred_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    vld = relationship('VLD', back_populates='deferral_history')
    
    # Indexes
    __table_args__ = (
        Index('idx_vld_deferral_vld_id', 'vld_id'),
        Index('idx_vld_deferral_date', 'deferred_at'),
    )


# =============================================================================
# CBG PORT OPERATIONS MODELS
# =============================================================================

class CBGPortLineupStatus(PyEnum):
    """CBG Port Lineup status enumeration."""
    SCHEDULED = "scheduled"
    ETA_RECEIVED = "eta_received"
    ARRIVED = "arrived"
    NOR_TENDERED = "nor_tendered"
    BERTHED = "berthed"
    LOADING = "loading"
    COMPLETED = "completed"
    DEPARTED = "departed"
    CANCELLED = "cancelled"


class QuayType(PyEnum):
    """CBG port quays."""
    Q1 = "Q1"
    Q2 = "Q2"


class CBGPortLineup(BaseModel):
    """CBG Port Lineup model for tracking vessel operations at the port."""
    __tablename__ = 'cbg_port_lineup'
    
    # Core vessel information
    vessel_name = Column(String(255), nullable=False)
    
    # VLD and partner relationships
    vld_id = Column(Integer, ForeignKey('vlds.id'), nullable=True)
    partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False)
    
    # Loader number (assigned after loading completion)
    loader_number = Column(String(50), unique=True, nullable=True)
    
    # Operational timing
    eta = Column(DateTime, nullable=True)  # Estimated Time of Arrival
    ata = Column(DateTime, nullable=True)  # Actual Time of Arrival
    nor = Column(DateTime, nullable=True)  # Notice of Readiness
    etb = Column(DateTime, nullable=True)  # Estimated Time of Berthing
    atb = Column(DateTime, nullable=True)  # Actual Time of Berthing
    loading_start = Column(DateTime, nullable=True)
    loading_completion = Column(DateTime, nullable=True)
    ets = Column(DateTime, nullable=True)  # Estimated Time of Sailing
    ats = Column(DateTime, nullable=True)  # Actual Time of Sailing
    
    # Product and tonnage
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    planned_tonnage = Column(Integer, nullable=False)
    actual_tonnage = Column(Integer, nullable=True)
    
    # Port operations
    status = Column(Enum(CBGPortLineupStatus), default=CBGPortLineupStatus.SCHEDULED, nullable=False)
    quay = Column(Enum(QuayType), nullable=True)
    berth_number = Column(String(10), nullable=True)
    shiploader_number = Column(String(10), nullable=True)
    
    # Additional information
    moisture_content = Column(Decimal(5, 2), nullable=True)
    remarks = Column(Text, nullable=True)
    
    # Relationships
    vld = relationship('VLD')
    partner = relationship('Partner')
    product = relationship('Product')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_cbg_lineup_vessel_name', 'vessel_name'),
        Index('idx_cbg_lineup_partner_id', 'partner_id'),
        Index('idx_cbg_lineup_status', 'status'),
        Index('idx_cbg_lineup_quay_status', 'quay', 'status'),
        Index('idx_cbg_lineup_eta', 'eta'),
        Index('idx_cbg_lineup_loading_dates', 'loading_start', 'loading_completion'),
        CheckConstraint('planned_tonnage > 0', name='check_planned_tonnage_positive'),
        CheckConstraint('moisture_content >= 0 AND moisture_content <= 100', name='check_moisture_content_range'),
    )
    
    def __repr__(self):
        return f'<CBGPortLineup {self.vessel_name} - {self.status.value}>'
    
    def update_eta(self, new_eta: datetime):
        """Update vessel ETA."""
        self.eta = new_eta
        if self.status == CBGPortLineupStatus.SCHEDULED:
            self.status = CBGPortLineupStatus.ETA_RECEIVED
        
        return {
            'vessel_name': self.vessel_name,
            'new_eta': self.eta,
            'status': self.status.value
        }
    
    def record_arrival(self, ata: datetime, updated_by_user_id: int = None):
        """Record actual vessel arrival."""
        self.ata = ata
        self.status = CBGPortLineupStatus.ARRIVED
        
        # Calculate ETA variance
        eta_variance = None
        if self.eta:
            eta_variance = (ata - self.eta).total_seconds() / 3600  # Hours
        
        return {
            'vessel_name': self.vessel_name,
            'ata': self.ata,
            'eta_variance_hours': eta_variance,
            'status': self.status.value
        }
    
    def tender_nor(self, nor_time: datetime):
        """Record Notice of Readiness tendering."""
        self.nor = nor_time
        self.status = CBGPortLineupStatus.NOR_TENDERED
        
        return {
            'vessel_name': self.vessel_name,
            'nor': self.nor,
            'status': self.status.value
        }
    
    def record_berthing(self, atb: datetime, berth_number: str = None, quay: QuayType = None, updated_by_user_id: int = None):
        """Record vessel berthing."""
        self.atb = atb
        self.status = CBGPortLineupStatus.BERTHED
        
        if berth_number:
            self.berth_number = berth_number
        if quay:
            self.quay = quay
        
        # Calculate berthing delay
        berthing_delay = None
        if self.etb:
            berthing_delay = (atb - self.etb).total_seconds() / 3600  # Hours
        
        return {
            'vessel_name': self.vessel_name,
            'atb': self.atb,
            'berth_number': self.berth_number,
            'quay': self.quay.value if self.quay else None,
            'berthing_delay_hours': berthing_delay,
            'status': self.status.value
        }
    
    def start_loading(self, loading_start: datetime, shiploader_number: str = None):
        """Start loading operation."""
        self.loading_start = loading_start
        self.status = CBGPortLineupStatus.LOADING
        
        if shiploader_number:
            self.shiploader_number = shiploader_number
        
        return {
            'vessel_name': self.vessel_name,
            'loading_start': self.loading_start,
            'shiploader_number': self.shiploader_number,
            'status': self.status.value
        }
    
    def complete_loading(self, loading_completion: datetime, actual_tonnage: int, 
                        moisture_content: float = None, loader_number: str = None):
        """Complete loading operation."""
        self.loading_completion = loading_completion
        self.actual_tonnage = actual_tonnage
        self.status = CBGPortLineupStatus.COMPLETED
        
        if moisture_content is not None:
            self.moisture_content = moisture_content
        if loader_number:
            self.loader_number = loader_number
        
        # Calculate loading statistics
        loading_duration = None
        loading_rate = None
        tonnage_variance = actual_tonnage - self.planned_tonnage
        
        if self.loading_start:
            loading_duration = (loading_completion - self.loading_start).total_seconds() / 3600  # Hours
            if loading_duration > 0:
                loading_rate = actual_tonnage / loading_duration  # MT per hour
        
        return {
            'vessel_name': self.vessel_name,
            'loading_completion': self.loading_completion,
            'actual_tonnage': self.actual_tonnage,
            'tonnage_variance': tonnage_variance,
            'loading_duration_hours': loading_duration,
            'loading_rate_mt_per_hour': loading_rate,
            'moisture_content': float(self.moisture_content) if self.moisture_content else None,
            'loader_number': self.loader_number,
            'status': self.status.value
        }
    
    def record_departure(self, ats: datetime):
        """Record vessel departure."""
        self.ats = ats
        self.status = CBGPortLineupStatus.DEPARTED
        
        # Calculate total port time
        port_time = None
        if self.ata:
            port_time = (ats - self.ata).total_seconds() / 3600  # Hours
        
        return {
            'vessel_name': self.vessel_name,
            'ats': self.ats,
            'total_port_time_hours': port_time,
            'status': self.status.value
        }
    
    def get_operational_summary(self):
        """Get comprehensive operational summary."""
        summary = {
            'vessel_name': self.vessel_name,
            'partner_name': self.partner.name if self.partner else None,
            'product_name': self.product.name if self.product else None,
            'status': self.status.value,
            'quay': self.quay.value if self.quay else None,
            'berth_number': self.berth_number,
            'shiploader_number': self.shiploader_number,
            'loader_number': self.loader_number,
            
            # Timing
            'eta': self.eta,
            'ata': self.ata,
            'nor': self.nor,
            'etb': self.etb,
            'atb': self.atb,
            'loading_start': self.loading_start,
            'loading_completion': self.loading_completion,
            'ets': self.ets,
            'ats': self.ats,
            
            # Tonnage and quality
            'planned_tonnage': self.planned_tonnage,
            'actual_tonnage': self.actual_tonnage,
            'moisture_content': float(self.moisture_content) if self.moisture_content else None,
            
            # Performance metrics
            'eta_variance_hours': None,
            'loading_duration_hours': None,
            'loading_rate_mt_per_hour': None,
            'total_port_time_hours': None,
            'tonnage_variance': None
        }
        
        # Calculate performance metrics
        if self.eta and self.ata:
            summary['eta_variance_hours'] = (self.ata - self.eta).total_seconds() / 3600
        
        if self.loading_start and self.loading_completion:
            loading_duration = (self.loading_completion - self.loading_start).total_seconds() / 3600
            summary['loading_duration_hours'] = loading_duration
            if self.actual_tonnage and loading_duration > 0:
                summary['loading_rate_mt_per_hour'] = self.actual_tonnage / loading_duration
        
        if self.ata and self.ats:
            summary['total_port_time_hours'] = (self.ats - self.ata).total_seconds() / 3600
        
        if self.actual_tonnage:
            summary['tonnage_variance'] = self.actual_tonnage - self.planned_tonnage
        
        return summary
    
    @classmethod
    def get_current_lineup(cls, days_ahead: int = 7):
        """Get current port lineup for next N days."""
        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
        return cls.query.filter(
            cls.eta <= cutoff_date,
            cls.status.in_([
                CBGPortLineupStatus.SCHEDULED,
                CBGPortLineupStatus.ETA_RECEIVED,
                CBGPortLineupStatus.ARRIVED,
                CBGPortLineupStatus.NOR_TENDERED,
                CBGPortLineupStatus.BERTHED,
                CBGPortLineupStatus.LOADING
            ])
        ).order_by(cls.eta).all()
    
    @classmethod
    def get_vessels_by_status(cls, status: CBGPortLineupStatus):
        """Get vessels by operational status."""
        return cls.query.filter_by(status=status).all()
    
    @classmethod
    def get_vessels_by_quay(cls, quay: QuayType, include_completed: bool = False):
        """Get vessels by quay (Q1 or Q2)."""
        query = cls.query.filter_by(quay=quay)
        
        if not include_completed:
            query = query.filter(cls.status != CBGPortLineupStatus.COMPLETED)
        
        return query.all()
    
    @classmethod
    def get_partner_vessels(cls, partner_id: int, include_completed: bool = False):
        """Get vessels for specific partner."""
        query = cls.query.filter_by(partner_id=partner_id)
        
        if not include_completed:
            query = query.filter(cls.status != CBGPortLineupStatus.COMPLETED)
        
        return query.order_by(cls.eta).all()
    
    @classmethod
    def get_loading_statistics(cls, start_date: date = None, end_date: date = None):
        """Get loading statistics for specified period."""
        query = cls.query.filter(cls.status == CBGPortLineupStatus.COMPLETED)
        
        if start_date:
            query = query.filter(cls.loading_completion >= start_date)
        if end_date:
            query = query.filter(cls.loading_completion <= end_date)
        
        vessels = query.all()
        
        if not vessels:
            return {
                'total_vessels': 0,
                'total_tonnage': 0,
                'average_loading_time': 0,
                'average_loading_rate': 0,
                'average_port_time': 0
            }
        
        total_tonnage = sum(v.actual_tonnage for v in vessels if v.actual_tonnage)
        loading_times = []
        loading_rates = []
        port_times = []
        
        for vessel in vessels:
            if vessel.loading_start and vessel.loading_completion:
                loading_time = (vessel.loading_completion - vessel.loading_start).total_seconds() / 3600
                loading_times.append(loading_time)
                
                if vessel.actual_tonnage and loading_time > 0:
                    loading_rates.append(vessel.actual_tonnage / loading_time)
            
            if vessel.ata and vessel.ats:
                port_time = (vessel.ats - vessel.ata).total_seconds() / 3600
                port_times.append(port_time)
        
        return {
            'total_vessels': len(vessels),
            'total_tonnage': total_tonnage,
            'average_loading_time': sum(loading_times) / len(loading_times) if loading_times else 0,
            'average_loading_rate': sum(loading_rates) / len(loading_rates) if loading_rates else 0,
            'average_port_time': sum(port_times) / len(port_times) if port_times else 0
        }
    
    @classmethod
    def get_quay_utilization(cls, start_date: date, end_date: date):
        """Get quay utilization statistics."""
        vessels = cls.query.filter(
            cls.loading_completion >= start_date,
            cls.loading_completion <= end_date,
            cls.status == CBGPortLineupStatus.COMPLETED
        ).all()
        
        q1_vessels = [v for v in vessels if v.quay == QuayType.Q1]
        q2_vessels = [v for v in vessels if v.quay == QuayType.Q2]
        
        total_vessels = len(vessels)
        q1_count = len(q1_vessels)
        q2_count = len(q2_vessels)
        
        return {
            'total_vessels': total_vessels,
            'q1_vessels': q1_count,
            'q2_vessels': q2_count,
            'q1_percentage': (q1_count / total_vessels * 100) if total_vessels > 0 else 0,
            'q2_percentage': (q2_count / total_vessels * 100) if total_vessels > 0 else 0,
            'q1_tonnage': sum(v.actual_tonnage for v in q1_vessels if v.actual_tonnage),
            'q2_tonnage': sum(v.actual_tonnage for v in q2_vessels if v.actual_tonnage)
        }


# =============================================================================
# TRANSLOADER OPERATIONS MODELS
# =============================================================================

class TransloaderOperationStatus(PyEnum):
    """Transloader operation status enumeration."""
    PLANNED = "planned"
    CBG_LOADING = "cbg_loading"
    TRANSIT = "transit"
    DISCHARGING = "discharging"
    COMPLETED = "completed"
    DELAYED = "delayed"
    SUBLET = "sublet"


class SubletStatus(PyEnum):
    """Sublet status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TransloaderVessel(PyEnum):
    """Transloader vessel enumeration."""
    CSL_ARGOSY = "CSL Argosy"
    CSL_ACADIAN = "CSL Acadian"


class CapesizeVessel(BaseModel):
    """Capesize vessel model for transloader operations."""
    __tablename__ = 'capesize_vessels'
    
    # Core vessel information
    vessel_name = Column(String(255), nullable=False)
    target_tonnage = Column(Integer, nullable=False)
    current_tonnage = Column(Integer, default=0, nullable=False)
    
    # Timing
    eta_anchorage = Column(DateTime, nullable=False)
    ata_anchorage = Column(DateTime, nullable=True)
    departure_anchorage = Column(DateTime, nullable=True)
    
    # Operational parameters
    max_cargo_hold_days = Column(Integer, default=5, nullable=False)
    operations_completed = Column(Integer, default=0, nullable=False)
    
    # Status
    status = Column(Enum('scheduled', 'arrived', 'loading', 'completed', 'departed', name='capesize_status'), 
                   default='scheduled', nullable=False)
    
    # Relationships
    transloader_operations = relationship('TransloaderOperation', back_populates='capesize_vessel')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_capesize_vessel_name', 'vessel_name'),
        Index('idx_capesize_eta', 'eta_anchorage'),
        Index('idx_capesize_status', 'status'),
        CheckConstraint('target_tonnage > 0', name='check_target_tonnage_positive'),
        CheckConstraint('current_tonnage >= 0', name='check_current_tonnage_non_negative'),
        CheckConstraint('max_cargo_hold_days > 0', name='check_cargo_hold_days_positive'),
    )
    
    def __repr__(self):
        return f'<CapesizeVessel {self.vessel_name} - {self.current_tonnage}/{self.target_tonnage}MT>'
    
    def get_cargo_hold_deadline(self):
        """Get deadline for transloader cargo hold (max days before Capesize arrival)."""
        return self.eta_anchorage - timedelta(days=self.max_cargo_hold_days)
    
    def get_completion_percentage(self):
        """Get loading completion percentage."""
        if self.target_tonnage == 0:
            return 0
        return (self.current_tonnage / self.target_tonnage) * 100
    
    def is_completed(self):
        """Check if Capesize is completed (95% threshold)."""
        return self.get_completion_percentage() >= 95.0
    
    def add_tonnage(self, tonnage: int):
        """Add tonnage from transloader operation."""
        self.current_tonnage += tonnage
        self.operations_completed += 1
        
        if self.is_completed() and self.status == 'loading':
            self.status = 'completed'
        
        return {
            'current_tonnage': self.current_tonnage,
            'completion_percentage': self.get_completion_percentage(),
            'operations_completed': self.operations_completed,
            'is_completed': self.is_completed()
        }


class TransloaderOperation(BaseModel):
    """Transloader operation model for ship-to-ship operations."""
    __tablename__ = 'transloader_operations'
    
    # Core operation information
    operation_number = Column(String(50), unique=True, nullable=False)
    vessel_name = Column(Enum(TransloaderVessel), nullable=False)
    planned_tonnage = Column(Integer, nullable=False)
    actual_tonnage = Column(Integer, nullable=True)
    
    # Timing
    cbg_loading_start = Column(DateTime, nullable=False)
    cbg_loading_completion = Column(DateTime, nullable=True)
    anchorage_arrival = Column(DateTime, nullable=True)
    discharge_start = Column(DateTime, nullable=True)
    discharge_completion = Column(DateTime, nullable=True)
    
    # Status and relationships
    status = Column(Enum(TransloaderOperationStatus), default=TransloaderOperationStatus.PLANNED, nullable=False)
    capesize_vessel_id = Column(Integer, ForeignKey('capesize_vessels.id'), nullable=False)
    cbg_lineup_id = Column(Integer, ForeignKey('cbg_port_lineup.id'), nullable=True)
    
    # Sublet management
    is_sublet = Column(Boolean, default=False, nullable=False)
    sublet_to_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=True)
    sublet_status = Column(Enum(SubletStatus), nullable=True)
    sublet_reason = Column(Text, nullable=True)
    sublet_commercial_terms = Column(Text, nullable=True)
    sublet_created_at = Column(DateTime, nullable=True)
    sublet_created_by = Column(Integer, nullable=True)  # User ID
    sublet_approved_at = Column(DateTime, nullable=True)
    sublet_approved_by = Column(Integer, nullable=True)  # User ID
    sublet_approval_notes = Column(Text, nullable=True)
    manual_incentive_tonnage = Column(Integer, nullable=True)
    calculated_incentive_tonnage = Column(Integer, nullable=True)
    
    # Operational details
    moisture_content = Column(Decimal(5, 2), nullable=True)
    remarks = Column(Text, nullable=True)
    
    # Relationships
    capesize_vessel = relationship('CapesizeVessel', back_populates='transloader_operations')
    cbg_lineup = relationship('CBGPortLineup')
    sublet_partner = relationship('Partner')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_transloader_operation_number', 'operation_number'),
        Index('idx_transloader_vessel_name', 'vessel_name'),
        Index('idx_transloader_status', 'status'),
        Index('idx_transloader_capesize', 'capesize_vessel_id'),
        Index('idx_transloader_sublet', 'is_sublet', 'sublet_status'),
        CheckConstraint('planned_tonnage > 0', name='check_planned_tonnage_positive'),
        CheckConstraint('moisture_content >= 0 AND moisture_content <= 100', name='check_moisture_content_range'),
    )
    
    def __repr__(self):
        sublet_indicator = " (SUBLET)" if self.is_sublet else ""
        return f'<TransloaderOperation {self.operation_number} - {self.vessel_name.value}{sublet_indicator}>'
    
    def create_sublet(self, sublet_to_partner_id: int, reason: str, commercial_terms: str, created_by_user_id: int):
        """Create sublet arrangement."""
        if self.status != TransloaderOperationStatus.PLANNED:
            raise ValueError("Can only sublet planned operations")
        
        self.is_sublet = True
        self.sublet_to_partner_id = sublet_to_partner_id
        self.sublet_status = SubletStatus.ACTIVE
        self.sublet_reason = reason
        self.sublet_commercial_terms = commercial_terms
        self.sublet_created_at = datetime.utcnow()
        self.sublet_created_by = created_by_user_id
        self.status = TransloaderOperationStatus.SUBLET
        
        return {
            'status': 'sublet_created',
            'operation_number': self.operation_number,
            'sublet_to_partner_id': sublet_to_partner_id,
            'reason': reason,
            'commercial_terms': commercial_terms,
            'created_at': self.sublet_created_at
        }
    
    def approve_sublet(self, approved_by_user_id: int, approval_notes: str = None):
        """Approve sublet arrangement."""
        if not self.is_sublet or self.sublet_status != SubletStatus.ACTIVE:
            raise ValueError("No active sublet to approve")
        
        self.sublet_approved_at = datetime.utcnow()
        self.sublet_approved_by = approved_by_user_id
        self.sublet_approval_notes = approval_notes
        
        return {
            'status': 'sublet_approved',
            'operation_number': self.operation_number,
            'approved_at': self.sublet_approved_at,
            'approved_by': approved_by_user_id,
            'approval_notes': approval_notes
        }
    
    def complete_sublet(self, completion_notes: str = None, completed_by_user_id: int = None):
        """Complete sublet arrangement."""
        if not self.is_sublet or self.sublet_status != SubletStatus.ACTIVE:
            raise ValueError("No active sublet to complete")
        
        self.sublet_status = SubletStatus.COMPLETED
        if completion_notes:
            self.remarks = completion_notes
        
        return {
            'status': 'sublet_completed',
            'operation_number': self.operation_number,
            'completion_notes': completion_notes
        }
    
    def cancel_sublet(self, cancellation_reason: str, cancelled_by_user_id: int):
        """Cancel sublet and return to Alcoa."""
        if not self.is_sublet:
            raise ValueError("Operation is not sublet")
        
        self.is_sublet = False
        self.sublet_status = SubletStatus.CANCELLED
        self.sublet_reason = f"CANCELLED: {cancellation_reason}"
        self.status = TransloaderOperationStatus.PLANNED
        
        return {
            'status': 'sublet_cancelled',
            'operation_number': self.operation_number,
            'cancellation_reason': cancellation_reason,
            'returned_to_alcoa': True
        }
    
    def start_cbg_loading(self):
        """Start CBG loading phase."""
        self.status = TransloaderOperationStatus.CBG_LOADING
        return {'status': 'cbg_loading_started', 'operation_number': self.operation_number}
    
    def complete_cbg_loading(self, completion_time: datetime, actual_tonnage: int = None):
        """Complete CBG loading phase."""
        self.cbg_loading_completion = completion_time
        if actual_tonnage:
            self.actual_tonnage = actual_tonnage
        self.status = TransloaderOperationStatus.TRANSIT
        
        return {
            'status': 'cbg_loading_completed',
            'operation_number': self.operation_number,
            'completion_time': completion_time,
            'actual_tonnage': self.actual_tonnage
        }
    
    def arrive_at_anchorage(self, arrival_time: datetime):
        """Arrive at Capesize anchorage."""
        self.anchorage_arrival = arrival_time
        self.status = TransloaderOperationStatus.DISCHARGING
        
        return {
            'status': 'arrived_at_anchorage',
            'operation_number': self.operation_number,
            'arrival_time': arrival_time
        }
    
    def complete_discharge(self, completion_time: datetime, moisture_content: float = None):
        """Complete ship-to-ship discharge."""
        self.discharge_completion = completion_time
        if moisture_content:
            self.moisture_content = moisture_content
        self.status = TransloaderOperationStatus.COMPLETED
        
        # Update Capesize vessel
        if self.capesize_vessel:
            tonnage_to_add = self.actual_tonnage or self.planned_tonnage
            capesize_result = self.capesize_vessel.add_tonnage(tonnage_to_add)
        
        return {
            'status': 'operation_completed',
            'operation_number': self.operation_number,
            'completion_time': completion_time,
            'moisture_content': float(self.moisture_content) if self.moisture_content else None,
            'capesize_update': capesize_result if self.capesize_vessel else None
        }
    
    def get_operation_summary(self):
        """Get comprehensive operation summary."""
        return {
            'operation_number': self.operation_number,
            'vessel_name': self.vessel_name.value,
            'status': self.status.value,
            'planned_tonnage': self.planned_tonnage,
            'actual_tonnage': self.actual_tonnage,
            'capesize_vessel': self.capesize_vessel.vessel_name if self.capesize_vessel else None,
            
            # Sublet information
            'is_sublet': self.is_sublet,
            'sublet_partner': self.sublet_partner.name if self.sublet_partner else None,
            'sublet_status': self.sublet_status.value if self.sublet_status else None,
            'sublet_reason': self.sublet_reason,
            'sublet_commercial_terms': self.sublet_commercial_terms,
            
            # Timing
            'cbg_loading_start': self.cbg_loading_start,
            'cbg_loading_completion': self.cbg_loading_completion,
            'anchorage_arrival': self.anchorage_arrival,
            'discharge_start': self.discharge_start,
            'discharge_completion': self.discharge_completion,
            
            # Quality and operational
            'moisture_content': float(self.moisture_content) if self.moisture_content else None,
            'remarks': self.remarks
        }
    
    @classmethod
    def get_sublet_statistics(cls, schedule_id: int = None):
        """Get comprehensive sublet statistics."""
        query = cls.query
        if schedule_id:
            # Assuming schedule_id relates to a specific time period or schedule
            pass  # Add filtering logic as needed
        
        operations = query.all()
        total_operations = len(operations)
        sublet_operations = [op for op in operations if op.is_sublet]
        alcoa_operations = [op for op in operations if not op.is_sublet]
        
        # Group sublet operations by partner
        sublet_by_partner = {}
        for op in sublet_operations:
            if op.sublet_partner:
                partner_name = op.sublet_partner.name
                if partner_name not in sublet_by_partner:
                    sublet_by_partner[partner_name] = {
                        'count': 0,
                        'total_tonnage': 0,
                        'active': 0,
                        'completed': 0
                    }
                
                sublet_by_partner[partner_name]['count'] += 1
                sublet_by_partner[partner_name]['total_tonnage'] += op.planned_tonnage
                
                if op.sublet_status == SubletStatus.ACTIVE:
                    sublet_by_partner[partner_name]['active'] += 1
                elif op.sublet_status == SubletStatus.COMPLETED:
                    sublet_by_partner[partner_name]['completed'] += 1
        
        # Group by vessel
        sublet_by_vessel = {}
        for op in sublet_operations:
            vessel_name = op.vessel_name.value
            if vessel_name not in sublet_by_vessel:
                sublet_by_vessel[vessel_name] = {'count': 0}
            sublet_by_vessel[vessel_name]['count'] += 1
        
        # Calculate percentages
        for vessel_name in sublet_by_vessel:
            sublet_by_vessel[vessel_name]['percentage'] = (
                sublet_by_vessel[vessel_name]['count'] / len(sublet_operations) * 100
            ) if sublet_operations else 0
        
        return {
            'total_operations': total_operations,
            'alcoa_operations': len(alcoa_operations),
            'sublet_operations': len(sublet_operations),
            'sublet_percentage': (len(sublet_operations) / total_operations * 100) if total_operations > 0 else 0,
            'sublet_by_partner': sublet_by_partner,
            'sublet_by_vessel': sublet_by_vessel
        }


class TransloaderSchedule(BaseModel):
    """Transloader schedule model for managing CSL operations."""
    __tablename__ = 'transloader_schedules'
    
    # Core schedule information
    schedule_name = Column(String(255), nullable=False)
    schedule_year = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    
    # Schedule settings
    allow_sublet_operations = Column(Boolean, default=True, nullable=False)
    require_sublet_approval = Column(Boolean, default=True, nullable=False)
    max_sublet_percentage = Column(Decimal(5, 2), default=50.0, nullable=False)
    
    # Status
    status = Column(Enum('draft', 'active', 'completed', 'archived', name='schedule_status'), 
                   default='draft', nullable=False)
    
    # Relationships
    operations = relationship('TransloaderOperation', cascade='all, delete-orphan')
    capesize_vessels = relationship('CapesizeVessel', cascade='all, delete-orphan')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_transloader_schedule_year', 'schedule_year'),
        Index('idx_transloader_schedule_status', 'status'),
        CheckConstraint('max_sublet_percentage >= 0 AND max_sublet_percentage <= 100', name='check_sublet_percentage_range'),
    )
    
    def __repr__(self):
        return f'<TransloaderSchedule {self.schedule_name} - {self.schedule_year}>'
    
    def create_bulk_sublet(self, operation_ids: List[int], sublet_to_partner_id: int, 
                          reason: str, commercial_terms: str, created_by_user_id: int):
        """Create multiple sublet operations at once."""
        results = []
        
        for operation_id in operation_ids:
            operation = TransloaderOperation.query.get(operation_id)
            if operation:
                try:
                    result = operation.create_sublet(
                        sublet_to_partner_id=sublet_to_partner_id,
                        reason=reason,
                        commercial_terms=commercial_terms,
                        created_by_user_id=created_by_user_id
                    )
                    results.append(result)
                except ValueError as e:
                    results.append({
                        'operation_id': operation_id,
                        'status': 'error',
                        'message': str(e)
                    })
        
        return {
            'bulk_sublet_created': len([r for r in results if r.get('status') == 'sublet_created']),
            'errors': len([r for r in results if r.get('status') == 'error']),
            'results': results
        }
    
    def validate_sublet_constraints(self):
        """Validate sublet percentage constraints."""
        total_operations = len(self.operations)
        sublet_operations = len([op for op in self.operations if op.is_sublet])
        
        if total_operations == 0:
            return {'is_valid': True, 'sublet_percentage': 0}
        
        sublet_percentage = (sublet_operations / total_operations) * 100
        is_valid = sublet_percentage <= float(self.max_sublet_percentage)
        
        return {
            'is_valid': is_valid,
            'sublet_percentage': sublet_percentage,
            'max_allowed_percentage': float(self.max_sublet_percentage),
            'total_operations': total_operations,
            'sublet_operations': sublet_operations,
            'excess_operations': max(0, sublet_operations - int(total_operations * float(self.max_sublet_percentage) / 100))
        }
    
    def get_sublet_summary(self):
        """Get comprehensive sublet summary for the schedule."""
        validation = self.validate_sublet_constraints()
        statistics = TransloaderOperation.get_sublet_statistics()
        
        return {
            'schedule_name': self.schedule_name,
            'schedule_year': self.schedule_year,
            'sublet_settings': {
                'allow_sublet_operations': self.allow_sublet_operations,
                'require_sublet_approval': self.require_sublet_approval,
                'max_sublet_percentage': float(self.max_sublet_percentage)
            },
            'validation': validation,
            'statistics': statistics
        }


# =============================================================================
# CAPESIZE SCHEDULE MODELS
# =============================================================================

class IncotermType(PyEnum):
    """Incoterm type enumeration."""
    CIF = "CIF"  # Cost, Insurance, and Freight
    FOB = "FOB"  # Free on Board


class AnchorageLocation(PyEnum):
    """Anchorage location enumeration."""
    ANCHORAGE_A = "Anchorage A"
    ANCHORAGE_B = "Anchorage B"
    ANCHORAGE_C = "Anchorage C"


class CapesizeScheduleStatus(PyEnum):
    """Capesize schedule status enumeration."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    ARRIVED = "arrived"
    LOADING = "loading"
    COMPLETED = "completed"
    DEPARTED = "departed"
    CANCELLED = "cancelled"


class CapesizeScheduleEntry(BaseModel):
    """Individual Capesize vessel schedule entry."""
    __tablename__ = 'capesize_schedule_entries'
    
    # Core vessel information
    vessel_name = Column(String(255), nullable=False)
    vessel_imo = Column(String(20), nullable=True)
    vessel_dwt = Column(Integer, nullable=True)
    
    # Commercial information
    incoterm = Column(Enum(IncotermType), default=IncotermType.FOB, nullable=False)
    
    # Timing
    eta = Column(DateTime, nullable=False)  # Estimated Time of Arrival
    ata = Column(DateTime, nullable=True)   # Actual Time of Arrival
    etb = Column(DateTime, nullable=True)   # Estimated Time of Berthing (at anchorage)
    atb = Column(DateTime, nullable=True)   # Actual Time of Berthing
    etc = Column(DateTime, nullable=True)   # Estimated Time of Completion
    atc = Column(DateTime, nullable=True)   # Actual Time of Completion
    etd = Column(DateTime, nullable=True)   # Estimated Time of Departure
    atd = Column(DateTime, nullable=True)   # Actual Time of Departure
    
    # Anchorage information
    anchorage_location = Column(Enum(AnchorageLocation), nullable=True)
    anchorage_latitude = Column(Decimal(10, 8), nullable=True)
    anchorage_longitude = Column(Decimal(11, 8), nullable=True)
    
    # Cargo information
    target_tonnage = Column(Integer, nullable=False)
    actual_tonnage = Column(Integer, nullable=True)
    moisture_content = Column(Decimal(5, 2), nullable=True)
    
    # Operational parameters
    max_cargo_hold_days = Column(Integer, default=5, nullable=False)
    planned_transloader_operations = Column(Integer, default=3, nullable=False)
    actual_transloader_operations = Column(Integer, default=0, nullable=False)
    
    # Status
    status = Column(Enum(CapesizeScheduleStatus), default=CapesizeScheduleStatus.SCHEDULED, nullable=False)
    
    # Foreign keys
    schedule_id = Column(Integer, ForeignKey('capesize_schedules.id'), nullable=False)
    
    # Relationships
    schedule = relationship('CapesizeSchedule', back_populates='entries')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_capesize_entry_vessel_name', 'vessel_name'),
        Index('idx_capesize_entry_eta', 'eta'),
        Index('idx_capesize_entry_status', 'status'),
        Index('idx_capesize_entry_incoterm_status', 'incoterm', 'status'),
        Index('idx_capesize_entry_schedule_id', 'schedule_id'),
        CheckConstraint('target_tonnage > 0', name='check_target_tonnage_positive'),
        CheckConstraint('max_cargo_hold_days > 0', name='check_cargo_hold_days_positive'),
        CheckConstraint('planned_transloader_operations > 0', name='check_planned_operations_positive'),
    )
    
    def __repr__(self):
        return f'<CapesizeScheduleEntry {self.vessel_name} - {self.status.value} ({self.incoterm.value})>'
    
    def get_cargo_hold_deadline(self):
        """Get deadline for transloader cargo hold."""
        return self.eta - timedelta(days=self.max_cargo_hold_days)
    
    def confirm_schedule(self, confirmed_eta: datetime, anchorage_location: AnchorageLocation, 
                        incoterm: IncotermType = None, updated_by_user_id: int = None):
        """Confirm Capesize schedule with final details."""
        self.eta = confirmed_eta
        self.anchorage_location = anchorage_location
        if incoterm:
            self.incoterm = incoterm
        self.status = CapesizeScheduleStatus.CONFIRMED
        
        # Set anchorage coordinates based on location
        anchorage_coords = {
            AnchorageLocation.ANCHORAGE_A: (-14.123456, -39.123456),
            AnchorageLocation.ANCHORAGE_B: (-14.234567, -39.234567),
            AnchorageLocation.ANCHORAGE_C: (-14.345678, -39.345678)
        }
        
        if anchorage_location in anchorage_coords:
            lat, lon = anchorage_coords[anchorage_location]
            self.anchorage_latitude = lat
            self.anchorage_longitude = lon
        
        return {
            'status': 'confirmed',
            'vessel_name': self.vessel_name,
            'confirmed_eta': self.eta,
            'anchorage_location': self.anchorage_location.value,
            'incoterm': self.incoterm.value,
            'cargo_hold_deadline': self.get_cargo_hold_deadline()
        }
    
    def update_eta(self, new_eta: datetime, reason: str = None):
        """Update ETA with impact analysis."""
        old_eta = self.eta
        self.eta = new_eta
        
        # Calculate impact
        eta_change_hours = (new_eta - old_eta).total_seconds() / 3600
        new_cargo_hold_deadline = self.get_cargo_hold_deadline()
        
        return {
            'status': 'eta_updated',
            'vessel_name': self.vessel_name,
            'old_eta': old_eta,
            'new_eta': new_eta,
            'eta_change_hours': eta_change_hours,
            'new_cargo_hold_deadline': new_cargo_hold_deadline,
            'reason': reason
        }
    
    def record_arrival(self, ata: datetime):
        """Record actual arrival at anchorage."""
        self.ata = ata
        self.status = CapesizeScheduleStatus.ARRIVED
        
        # Calculate ETA variance
        eta_variance_hours = (ata - self.eta).total_seconds() / 3600
        
        return {
            'status': 'arrived',
            'vessel_name': self.vessel_name,
            'ata': self.ata,
            'eta_variance_hours': eta_variance_hours
        }
    
    def start_loading(self, loading_start: datetime):
        """Start loading operations."""
        self.atb = loading_start  # Actual time of berthing at anchorage
        self.status = CapesizeScheduleStatus.LOADING
        
        return {
            'status': 'loading_started',
            'vessel_name': self.vessel_name,
            'loading_start': loading_start
        }
    
    def complete_loading(self, completion_time: datetime, actual_tonnage: int, 
                        actual_operations: int, moisture_content: float = None):
        """Complete loading operations."""
        self.atc = completion_time
        self.actual_tonnage = actual_tonnage
        self.actual_transloader_operations = actual_operations
        if moisture_content:
            self.moisture_content = moisture_content
        self.status = CapesizeScheduleStatus.COMPLETED
        
        # Calculate performance metrics
        tonnage_efficiency = (actual_tonnage / self.target_tonnage * 100) if self.target_tonnage > 0 else 0
        operations_efficiency = (actual_operations / self.planned_transloader_operations * 100) if self.planned_transloader_operations > 0 else 0
        
        loading_duration = None
        if self.atb:
            loading_duration = (completion_time - self.atb).total_seconds() / 3600  # Hours
        
        return {
            'status': 'loading_completed',
            'vessel_name': self.vessel_name,
            'actual_tonnage': actual_tonnage,
            'actual_operations': actual_operations,
            'tonnage_efficiency': tonnage_efficiency,
            'operations_efficiency': operations_efficiency,
            'loading_duration_hours': loading_duration,
            'moisture_content': float(self.moisture_content) if self.moisture_content else None
        }
    
    def record_departure(self, departure_time: datetime):
        """Record vessel departure."""
        self.atd = departure_time
        self.status = CapesizeScheduleStatus.DEPARTED
        
        # Calculate total anchorage time
        anchorage_time = None
        if self.ata:
            anchorage_time = (departure_time - self.ata).total_seconds() / 3600  # Hours
        
        return {
            'status': 'departed',
            'vessel_name': self.vessel_name,
            'departure_time': departure_time,
            'total_anchorage_time_hours': anchorage_time
        }
    
    def get_schedule_summary(self):
        """Get comprehensive schedule summary."""
        return {
            'vessel_information': {
                'vessel_name': self.vessel_name,
                'vessel_imo': self.vessel_imo,
                'vessel_dwt': self.vessel_dwt,
                'status': self.status.value
            },
            
            'commercial': {
                'incoterm': self.incoterm.value,
                'target_tonnage': self.target_tonnage,
                'actual_tonnage': self.actual_tonnage
            },
            
            'timing': {
                'eta': self.eta,
                'ata': self.ata,
                'etb': self.etb,
                'atb': self.atb,
                'etc': self.etc,
                'atc': self.atc,
                'etd': self.etd,
                'atd': self.atd
            },
            
            'anchorage': {
                'location': self.anchorage_location.value if self.anchorage_location else None,
                'latitude': float(self.anchorage_latitude) if self.anchorage_latitude else None,
                'longitude': float(self.anchorage_longitude) if self.anchorage_longitude else None
            },
            
            'operations': {
                'max_cargo_hold_days': self.max_cargo_hold_days,
                'planned_transloader_operations': self.planned_transloader_operations,
                'actual_transloader_operations': self.actual_transloader_operations,
                'cargo_hold_deadline': self.get_cargo_hold_deadline()
            },
            
            'quality': {
                'moisture_content': float(self.moisture_content) if self.moisture_content else None
            }
        }


class CapesizeSchedule(BaseModel):
    """Master Capesize schedule for managing mother vessel operations."""
    __tablename__ = 'capesize_schedules'
    
    # Core schedule information
    schedule_name = Column(String(255), nullable=False)
    schedule_year = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    
    # Schedule parameters
    total_target_tonnage = Column(Integer, nullable=False)
    total_planned_vessels = Column(Integer, nullable=False)
    
    # Status and lifecycle
    status = Column(Enum('draft', 'published', 'active', 'completed', 'archived', name='capesize_schedule_status'), 
                   default='draft', nullable=False)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(Integer, nullable=True)  # User ID
    
    # Relationships
    entries = relationship('CapesizeScheduleEntry', back_populates='schedule', cascade='all, delete-orphan')
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_capesize_schedule_year', 'schedule_year'),
        Index('idx_capesize_schedule_status', 'status'),
        CheckConstraint('total_target_tonnage > 0', name='check_total_target_tonnage_positive'),
        CheckConstraint('total_planned_vessels > 0', name='check_total_planned_vessels_positive'),
    )
    
    def __repr__(self):
        return f'<CapesizeSchedule {self.schedule_name} - {self.schedule_year}>'
    
    def publish_schedule(self, published_by_user_id: int):
        """Publish schedule for operational use."""
        # Deactivate previous schedules for the same year
        previous_schedules = CapesizeSchedule.query.filter(
            CapesizeSchedule.schedule_year == self.schedule_year,
            CapesizeSchedule.status.in_(['published', 'active']),
            CapesizeSchedule.id != self.id
        ).all()
        
        for schedule in previous_schedules:
            schedule.status = 'archived'
        
        # Publish this schedule
        self.status = 'published'
        self.published_at = datetime.utcnow()
        self.published_by = published_by_user_id
        
        return {
            'status': 'published',
            'schedule_name': self.schedule_name,
            'published_at': self.published_at,
            'deactivated_schedules': len(previous_schedules)
        }
    
    def get_schedule_statistics(self):
        """Get comprehensive schedule statistics."""
        total_entries = len(self.entries)
        
        # Group by status
        status_counts = {}
        for entry in self.entries:
            status = entry.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Group by incoterm
        incoterm_stats = {}
        for entry in self.entries:
            incoterm = entry.incoterm.value
            if incoterm not in incoterm_stats:
                incoterm_stats[incoterm] = {
                    'count': 0,
                    'target_tonnage': 0,
                    'actual_tonnage': 0
                }
            
            incoterm_stats[incoterm]['count'] += 1
            incoterm_stats[incoterm]['target_tonnage'] += entry.target_tonnage
            if entry.actual_tonnage:
                incoterm_stats[incoterm]['actual_tonnage'] += entry.actual_tonnage
        
        # Calculate percentages for incoterms
        for incoterm in incoterm_stats:
            incoterm_stats[incoterm]['percentage'] = (
                incoterm_stats[incoterm]['count'] / total_entries * 100
            ) if total_entries > 0 else 0
        
        # Performance metrics
        completed_entries = [e for e in self.entries if e.status == CapesizeScheduleStatus.COMPLETED]
        total_actual_tonnage = sum(e.actual_tonnage for e in completed_entries if e.actual_tonnage)
        
        return {
            'schedule_overview': {
                'schedule_name': self.schedule_name,
                'schedule_year': self.schedule_year,
                'status': self.status,
                'total_planned_vessels': self.total_planned_vessels,
                'total_target_tonnage': self.total_target_tonnage
            },
            
            'progress': {
                'total_entries': total_entries,
                'completed_vessels': len(completed_entries),
                'completion_percentage': (len(completed_entries) / total_entries * 100) if total_entries > 0 else 0,
                'total_actual_tonnage': total_actual_tonnage,
                'tonnage_efficiency': (total_actual_tonnage / self.total_target_tonnage * 100) if self.total_target_tonnage > 0 else 0
            },
            
            'status_breakdown': status_counts,
            'incoterm_breakdown': incoterm_stats
        }
    
    @classmethod
    def get_vessels_by_incoterm(cls, incoterm: IncotermType, schedule_id: int = None, include_completed: bool = True):
        """Get vessels filtered by incoterm."""
        query = CapesizeScheduleEntry.query.filter_by(incoterm=incoterm)
        
        if schedule_id:
            query = query.filter_by(schedule_id=schedule_id)
        
        if not include_completed:
            query = query.filter(CapesizeScheduleEntry.status != CapesizeScheduleStatus.COMPLETED)
        
        return query.all()
    
    @classmethod
    def get_active_schedule_by_year(cls, year: int):
        """Get active schedule for specific year."""
        return cls.query.filter(
            cls.schedule_year == year,
            cls.status.in_(['published', 'active'])
        ).first()


# =============================================================================
# MODEL REGISTRATION AND INITIALIZATION
# =============================================================================

def create_all_tables(app):
    """Create all database tables."""
    with app.app_context():
        db.create_all()


def init_app(app):
    """Initialize the database with the Flask app."""
    db.init_app(app)
    return db


# Export all models for easy importing
__all__ = [
    # Base
    'BaseModel', 'db',
    
    # Partner Management
    'PartnerEntity', 'Partner',
    
    # Product Management
    'Mine', 'Product',
    
    # Production Planning
    'Production', 'ProductionPartnerEnrollment',
    
    # VLD Management
    'VLD', 'VLDReassignmentHistory', 'VLDCancellationHistory', 'VLDDeferralHistory',
    'VLDStatus',
    
    # CBG Port Operations
    'CBGPortLineup', 'CBGPortLineupStatus', 'QuayType',
    
    # Transloader Operations
    'CapesizeVessel', 'TransloaderOperation', 'TransloaderSchedule',
    'TransloaderOperationStatus', 'SubletStatus', 'TransloaderVessel',
    
    # Capesize Schedule
    'CapesizeScheduleEntry', 'CapesizeSchedule',
    'IncotermType', 'AnchorageLocation', 'CapesizeScheduleStatus',
    
    # Utility functions
    'create_all_tables', 'init_app'
]

"""
Usage Example:
=============

from flask import Flask
from complete_erp_bauxita_models import db, init_app, create_all_tables
from complete_erp_bauxita_models import Partner, PartnerEntity, Production, VLD, CBGPortLineup

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_bauxita.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_app(app)

# Create tables
create_all_tables(app)

# Use models
with app.app_context():
    # Create partner entity
    alcoa_entity = PartnerEntity(
        name="Alcoa Corporation",
        code="ALCOA",
        description="Major aluminum producer",
        is_halco_buyer=True
    )
    db.session.add(alcoa_entity)
    db.session.commit()
    
    # Create partner
    alcoa_partner = Partner(
        name="Alcoa World Alumina",
        code="AWA",
        description="Alcoa's alumina division",
        entity_id=alcoa_entity.id,
        minimum_contractual_tonnage=5112000
    )
    db.session.add(alcoa_partner)
    db.session.commit()
"""

