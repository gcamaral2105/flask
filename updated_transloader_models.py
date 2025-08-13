'''
Updated Transloader Models - ERP Bauxita
Dynamic Fleet Management System

This file contains the updated transloader models with dynamic fleet management,
replacing the static enum approach with a flexible, database-driven system.
'''

import enum
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    UniqueConstraint,
    Index,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.sql import func

Base = declarative_base()

# BaseModel definition
class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# ===============================================================================
# ENUMERATIONS
# ===============================================================================

class VesselStatus(enum.Enum):
    """Vessel operational status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class VesselType(enum.Enum):
    """Vessel type enumeration."""
    TRANSLOADER = "transloader"
    SHUTTLE = "shuttle"
    BARGE = "barge"
    FEEDER = "feeder"


class TransloaderOperationStatus(enum.Enum):
    """Transloader operation status enumeration."""
    PLANNED = "planned"
    CBG_LOADING = "cbg_loading"
    CBG_COMPLETED = "cbg_completed"
    TRANSIT_TO_CAPESIZE = "transit_to_capesize"
    DISCHARGING_TO_CAPESIZE = "discharging_to_capesize"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUBLET = "sublet"


class SubletStatus(enum.Enum):
    """Sublet status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ===============================================================================
# TRANSLOADER FLEET MODEL
# ===============================================================================

class TransloaderFleet(BaseModel):
    """
    Transloader Fleet Model
    
    Manages the fleet of transloader vessels dynamically.
    Supports adding/removing vessels without code changes.
    """
    __tablename__ = 'transloader_fleet'
    
    # Vessel identification
    vessel_name = Column(String(100), nullable=False, unique=True, index=True, comment="Official vessel name")
    vessel_code = Column(String(20), nullable=False, unique=True, index=True, comment="Short vessel code (e.g., 'ARG', 'ACA')")
    imo_number = Column(String(20), nullable=True, unique=True, index=True, comment="IMO number")
    call_sign = Column(String(20), nullable=True, comment="Radio call sign")
    
    # Vessel classification
    vessel_type = Column(Enum(VesselType), default=VesselType.TRANSLOADER, nullable=False, index=True)
    vessel_class = Column(String(50), nullable=True, comment="Vessel class (e.g., 'CSL Class', 'Handysize')")
    
    # Capacity and specifications
    capacity_mt = Column(Integer, nullable=False, comment="Vessel capacity in metric tons")
    dwt = Column(Integer, nullable=True, comment="Deadweight tonnage")
    grt = Column(Integer, nullable=True, comment="Gross register tonnage")
    nrt = Column(Integer, nullable=True, comment="Net register tonnage")
    
    # Physical dimensions
    length_m = Column(Decimal(precision=6, scale=2), nullable=True, comment="Length overall in meters")
    beam_m = Column(Decimal(precision=6, scale=2), nullable=True, comment="Beam in meters")
    draft_m = Column(Decimal(precision=6, scale=2), nullable=True, comment="Maximum draft in meters")
    air_draft_m = Column(Decimal(precision=6, scale=2), nullable=True, comment="Air draft in meters")
    
    # Operational parameters
    loading_rate_tph = Column(Integer, nullable=True, comment="Loading rate in tonnes per hour")
    discharge_rate_tph = Column(Integer, nullable=True, comment="Discharge rate in tonnes per hour")
    transit_speed_knots = Column(Decimal(precision=4, scale=1), nullable=True, comment="Typical transit speed")
    fuel_consumption_mt_day = Column(Decimal(precision=6, scale=2), nullable=True, comment="Daily fuel consumption")
    
    # Operational status
    status = Column(Enum(VesselStatus), default=VesselStatus.ACTIVE, nullable=False, index=True)
    is_available = Column(Boolean, default=True, nullable=False, index=True, comment="Available for operations")
    current_location = Column(String(100), nullable=True, comment="Current vessel location")
    
    # Maintenance and certification
    last_maintenance_date = Column(Date, nullable=True, comment="Last maintenance completion date")
    next_maintenance_due = Column(Date, nullable=True, comment="Next maintenance due date")
    maintenance_interval_days = Column(Integer, default=90, nullable=False, comment="Maintenance interval in days")
    last_survey_date = Column(Date, nullable=True, comment="Last survey date")
    next_survey_due = Column(Date, nullable=True, comment="Next survey due date")
    
    # Certification and compliance
    flag_state = Column(String(50), nullable=True, comment="Flag state")
    classification_society = Column(String(100), nullable=True, comment="Classification society")
    safety_certificate_expiry = Column(Date, nullable=True, comment="Safety certificate expiry date")
    
    # Commercial information
    owner_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False, index=True, comment="Vessel owner")
    operator_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=True, index=True, comment="Vessel operator (if different from owner)")
    charter_rate_usd_day = Column(Decimal(precision=10, scale=2), nullable=True, comment="Daily charter rate in USD")
    
    # Performance tracking
    total_operations_completed = Column(Integer, default=0, nullable=False, comment="Total operations completed")
    total_tonnage_handled = Column(Integer, default=0, nullable=False, comment="Total tonnage handled")
    average_loading_rate_tph = Column(Decimal(precision=8, scale=2), nullable=True, comment="Average loading rate")
    average_discharge_rate_tph = Column(Decimal(precision=8, scale=2), nullable=True, comment="Average discharge rate")
    utilization_percentage = Column(Decimal(precision=5, scale=2), nullable=True, comment="Vessel utilization percentage")
    
    # Audit fields
    last_updated_by = Column(Integer, nullable=True, comment="User who last updated this vessel")
    
    # Relationships
    owner_partner = relationship('Partner', foreign_keys=[owner_partner_id])
    operator_partner = relationship('Partner', foreign_keys=[operator_partner_id])
    operations = relationship('TransloaderOperation', back_populates='transloader_fleet_vessel', cascade='all, delete-orphan')
    maintenance_records = relationship('VesselMaintenanceRecord', back_populates='vessel', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_transloader_fleet_name_code', 'vessel_name', 'vessel_code'),
        Index('idx_transloader_fleet_status_available', 'status', 'is_available'),
        Index('idx_transloader_fleet_owner', 'owner_partner_id'),
        Index('idx_transloader_fleet_type_status', 'vessel_type', 'status'),
        Index('idx_transloader_fleet_maintenance_due', 'next_maintenance_due'),
        Index('idx_transloader_fleet_capacity', 'capacity_mt'),
    )
    
    @classmethod
    def get_available_vessels(cls, vessel_type=None, min_capacity=None):
        """Get all available vessels for operations."""
        query = cls.query.filter_by(status=VesselStatus.ACTIVE, is_available=True)
        
        if vessel_type:
            query = query.filter_by(vessel_type=vessel_type)
        
        if min_capacity:
            query = query.filter(cls.capacity_mt >= min_capacity)
        
        return query.order_by(cls.vessel_name).all()
    
    @classmethod
    def get_vessels_by_owner(cls, partner_id, include_inactive=False):
        """Get vessels by owner partner."""
        query = cls.query.filter_by(owner_partner_id=partner_id)
        
        if not include_inactive:
            query = query.filter(cls.status != VesselStatus.RETIRED)
        
        return query.order_by(cls.vessel_name).all()
    
    @classmethod
    def get_fleet_statistics(cls):
        """Get comprehensive fleet statistics."""
        vessels = cls.query.all()
        
        if not vessels:
            return {
                'total_vessels': 0,
                'active_vessels': 0,
                'available_vessels': 0,
                'total_capacity_mt': 0,
                'average_capacity_mt': 0,
                'vessels_by_status': {},
                'vessels_by_type': {},
                'vessels_by_owner': {}
            }
        
        total_vessels = len(vessels)
        active_vessels = len([v for v in vessels if v.status == VesselStatus.ACTIVE])
        available_vessels = len([v for v in vessels if v.status == VesselStatus.ACTIVE and v.is_available])
        total_capacity = sum(v.capacity_mt for v in vessels)
        average_capacity = total_capacity / total_vessels if total_vessels > 0 else 0
        
        # Group by status
        vessels_by_status = {}
        for status in VesselStatus:
            count = len([v for v in vessels if v.status == status])
            vessels_by_status[status.value] = count
        
        # Group by type
        vessels_by_type = {}
        for vessel_type in VesselType:
            count = len([v for v in vessels if v.vessel_type == vessel_type])
            vessels_by_type[vessel_type.value] = count
        
        # Group by owner
        vessels_by_owner = {}
        for vessel in vessels:
            owner_name = vessel.owner_partner.name if vessel.owner_partner else 'Unknown'
            if owner_name not in vessels_by_owner:
                vessels_by_owner[owner_name] = {'count': 0, 'total_capacity': 0}
            vessels_by_owner[owner_name]['count'] += 1
            vessels_by_owner[owner_name]['total_capacity'] += vessel.capacity_mt
        
        return {
            'total_vessels': total_vessels,
            'active_vessels': active_vessels,
            'available_vessels': available_vessels,
            'total_capacity_mt': total_capacity,
            'average_capacity_mt': round(average_capacity, 0),
            'vessels_by_status': vessels_by_status,
            'vessels_by_type': vessels_by_type,
            'vessels_by_owner': vessels_by_owner
        }
    
    def schedule_maintenance(self, maintenance_date, maintenance_type, estimated_duration_days, updated_by_user_id):
        """Schedule vessel maintenance."""
        self.is_available = False
        self.status = VesselStatus.MAINTENANCE
        self.next_maintenance_due = maintenance_date
        self.last_updated_by = updated_by_user_id
        
        # Create maintenance record
        maintenance_record = VesselMaintenanceRecord(
            vessel_id=self.id,
            maintenance_type=maintenance_type,
            scheduled_start_date=maintenance_date,
            estimated_duration_days=estimated_duration_days,
            status='scheduled',
            scheduled_by=updated_by_user_id
        )
        self.maintenance_records.append(maintenance_record)
        
        return {
            'status': 'maintenance_scheduled',
            'vessel_name': self.vessel_name,
            'maintenance_date': maintenance_date,
            'maintenance_type': maintenance_type,
            'estimated_duration_days': estimated_duration_days
        }
    
    def complete_maintenance(self, completion_date, actual_duration_days, maintenance_notes, updated_by_user_id):
        """Complete vessel maintenance."""
        self.is_available = True
        self.status = VesselStatus.ACTIVE
        self.last_maintenance_date = completion_date
        self.next_maintenance_due = completion_date + timedelta(days=self.maintenance_interval_days)
        self.last_updated_by = updated_by_user_id
        
        # Update latest maintenance record
        latest_maintenance = self.maintenance_records[-1] if self.maintenance_records else None
        if latest_maintenance and latest_maintenance.status == 'scheduled':
            latest_maintenance.actual_start_date = completion_date - timedelta(days=actual_duration_days)
            latest_maintenance.actual_completion_date = completion_date
            latest_maintenance.actual_duration_days = actual_duration_days
            latest_maintenance.maintenance_notes = maintenance_notes
            latest_maintenance.status = 'completed'
            latest_maintenance.completed_by = updated_by_user_id
        
        return {
            'status': 'maintenance_completed',
            'vessel_name': self.vessel_name,
            'completion_date': completion_date,
            'next_due': self.next_maintenance_due,
            'actual_duration_days': actual_duration_days
        }
    
    def update_performance_metrics(self):
        """Update vessel performance metrics based on completed operations."""
        completed_operations = [op for op in self.operations if op.status == TransloaderOperationStatus.COMPLETED]
        
        if not completed_operations:
            return
        
        self.total_operations_completed = len(completed_operations)
        self.total_tonnage_handled = sum(op.actual_tonnage or op.planned_tonnage for op in completed_operations)
        
        # Calculate average loading rate
        loading_rates = [op.cbg_loading_duration_hours for op in completed_operations if op.cbg_loading_duration_hours and op.actual_tonnage]
        if loading_rates:
            total_loading_time = sum(float(rate) for rate in loading_rates)
            total_tonnage_loaded = sum(op.actual_tonnage for op in completed_operations if op.cbg_loading_duration_hours and op.actual_tonnage)
            if total_loading_time > 0:
                self.average_loading_rate_tph = Decimal(str(round(total_tonnage_loaded / total_loading_time, 2)))
        
        # Calculate average discharge rate
        discharge_rates = [op.discharge_duration_hours for op in completed_operations if op.discharge_duration_hours and op.actual_tonnage]
        if discharge_rates:
            total_discharge_time = sum(float(rate) for rate in discharge_rates)
            total_tonnage_discharged = sum(op.actual_tonnage for op in completed_operations if op.discharge_duration_hours and op.actual_tonnage)
            if total_discharge_time > 0:
                self.average_discharge_rate_tph = Decimal(str(round(total_tonnage_discharged / total_discharge_time, 2)))
    
    def get_vessel_summary(self):
        """Get comprehensive vessel summary."""
        return {
            'vessel_info': {
                'vessel_name': self.vessel_name,
                'vessel_code': self.vessel_code,
                'imo_number': self.imo_number,
                'vessel_type': self.vessel_type.value,
                'vessel_class': self.vessel_class
            },
            'specifications': {
                'capacity_mt': self.capacity_mt,
                'dwt': self.dwt,
                'length_m': float(self.length_m) if self.length_m else None,
                'beam_m': float(self.beam_m) if self.beam_m else None,
                'draft_m': float(self.draft_m) if self.draft_m else None
            },
            'operational': {
                'status': self.status.value,
                'is_available': self.is_available,
                'current_location': self.current_location,
                'loading_rate_tph': self.loading_rate_tph,
                'discharge_rate_tph': self.discharge_rate_tph,
                'transit_speed_knots': float(self.transit_speed_knots) if self.transit_speed_knots else None
            },
            'maintenance': {
                'last_maintenance_date': self.last_maintenance_date,
                'next_maintenance_due': self.next_maintenance_due,
                'maintenance_interval_days': self.maintenance_interval_days
            },
            'commercial': {
                'owner': self.owner_partner.name if self.owner_partner else None,
                'operator': self.operator_partner.name if self.operator_partner else None,
                'charter_rate_usd_day': float(self.charter_rate_usd_day) if self.charter_rate_usd_day else None
            },
            'performance': {
                'total_operations_completed': self.total_operations_completed,
                'total_tonnage_handled': self.total_tonnage_handled,
                'average_loading_rate_tph': float(self.average_loading_rate_tph) if self.average_loading_rate_tph else None,
                'average_discharge_rate_tph': float(self.average_discharge_rate_tph) if self.average_discharge_rate_tph else None,
                'utilization_percentage': float(self.utilization_percentage) if self.utilization_percentage else None
            }
        }
    
    def __repr__(self):
        return f"<TransloaderFleet {self.vessel_name} ({self.vessel_code}) - {self.status.value}>"


# ===============================================================================
# VESSEL MAINTENANCE RECORD MODEL
# ===============================================================================

class VesselMaintenanceRecord(BaseModel):
    """
    Vessel Maintenance Record Model
    
    Tracks maintenance activities for transloader vessels.
    """
    __tablename__ = 'vessel_maintenance_records'
    
    # Foreign key to vessel
    vessel_id = Column(Integer, ForeignKey('transloader_fleet.id'), nullable=False, index=True)
    
    # Maintenance details
    maintenance_type = Column(String(100), nullable=False, comment="Type of maintenance (e.g., 'Dry Dock', 'Engine Overhaul')")
    description = Column(Text, nullable=True, comment="Detailed maintenance description")
    
    # Scheduling
    scheduled_start_date = Column(Date, nullable=False, comment="Scheduled maintenance start date")
    scheduled_completion_date = Column(Date, nullable=True, comment="Scheduled maintenance completion date")
    estimated_duration_days = Column(Integer, nullable=False, comment="Estimated duration in days")
    
    # Actual execution
    actual_start_date = Column(Date, nullable=True, comment="Actual maintenance start date")
    actual_completion_date = Column(Date, nullable=True, comment="Actual maintenance completion date")
    actual_duration_days = Column(Integer, nullable=True, comment="Actual duration in days")
    
    # Status and notes
    status = Column(String(20), default='scheduled', nullable=False, comment="Maintenance status")
    maintenance_notes = Column(Text, nullable=True, comment="Maintenance completion notes")
    
    # Cost tracking
    estimated_cost_usd = Column(Decimal(precision=12, scale=2), nullable=True, comment="Estimated maintenance cost")
    actual_cost_usd = Column(Decimal(precision=12, scale=2), nullable=True, comment="Actual maintenance cost")
    
    # Service provider
    service_provider = Column(String(200), nullable=True, comment="Maintenance service provider")
    location = Column(String(100), nullable=True, comment="Maintenance location")
    
    # Audit information
    scheduled_by = Column(Integer, nullable=False, comment="User who scheduled the maintenance")
    completed_by = Column(Integer, nullable=True, comment="User who marked maintenance as completed")
    
    # Relationships
    vessel = relationship('TransloaderFleet', back_populates='maintenance_records')
    
    # Indexes
    __table_args__ = (
        Index('idx_vessel_maintenance_vessel', 'vessel_id'),
        Index('idx_vessel_maintenance_status', 'status'),
        Index('idx_vessel_maintenance_dates', 'scheduled_start_date', 'actual_completion_date'),
    )
    
    def __repr__(self):
        return f"<VesselMaintenanceRecord {self.vessel.vessel_name if self.vessel else 'Unknown'} - {self.maintenance_type} ({self.status})>"


# ===============================================================================
# UPDATED TRANSLOADER OPERATION MODEL
# ===============================================================================

class TransloaderOperation(BaseModel):
    """
    Enhanced Transloader Operation Model
    
    Now uses dynamic fleet management instead of static enum.
    Supports flexible vessel assignment and comprehensive tracking.
    """
    __tablename__ = 'transloader_operations'
    
    # Operation identification
    operation_number = Column(String(50), nullable=False, unique=True, index=True, comment="Operation number (e.g., 'TL-2025-001-1')")
    
    # Foreign keys
    transloader_schedule_id = Column(Integer, ForeignKey('transloader_schedules.id'), nullable=False, index=True)
    capesize_vessel_id = Column(Integer, ForeignKey('capesize_schedule_entries.id'), nullable=False, index=True)
    cbg_lineup_id = Column(Integer, ForeignKey('cbg_port_lineup.id'), nullable=True, index=True)
    
    # DYNAMIC VESSEL ASSIGNMENT (replaces static enum)
    transloader_fleet_vessel_id = Column(Integer, ForeignKey('transloader_fleet.id'), nullable=False, index=True, comment="Assigned transloader vessel from fleet")
    
    # Tonnage information
    planned_tonnage = Column(Integer, nullable=False, comment="Planned tonnage for this operation")
    actual_tonnage = Column(Integer, nullable=True, comment="Actual tonnage transferred")
    
    # CBG loading phase
    cbg_loading_start = Column(DateTime, nullable=True, comment="CBG loading start time")
    cbg_loading_completion = Column(DateTime, nullable=True, comment="CBG loading completion time")
    cbg_loading_duration_hours = Column(Decimal(precision=6, scale=2), nullable=True, comment="CBG loading duration")
    cbg_loading_rate_tph = Column(Decimal(precision=8, scale=2), nullable=True, comment="CBG loading rate in tonnes per hour")
    
    # Transit phase
    transit_start = Column(DateTime, nullable=True, comment="Transit to Capesize start time")
    transit_completion = Column(DateTime, nullable=True, comment="Transit to Capesize completion time")
    transit_duration_hours = Column(Decimal(precision=6, scale=2), nullable=True, comment="Transit duration")
    transit_distance_nm = Column(Decimal(precision=6, scale=2), nullable=True, comment="Transit distance in nautical miles")
    
    # Capesize discharge phase
    discharge_start = Column(DateTime, nullable=True, comment="Discharge to Capesize start time")
    discharge_completion = Column(DateTime, nullable=True, comment="Discharge to Capesize completion time")
    discharge_duration_hours = Column(Decimal(precision=6, scale=2), nullable=True, comment="Discharge duration")
    discharge_rate_tph = Column(Decimal(precision=8, scale=2), nullable=True, comment="Discharge rate in tonnes per hour")
    
    # Quality information
    moisture_content = Column(Decimal(precision=5, scale=2), nullable=True, comment="Cargo moisture content")
    
    # Operation status
    status = Column(Enum(TransloaderOperationStatus), default=TransloaderOperationStatus.PLANNED, nullable=False, index=True)
    
    # Cargo hold constraint tracking
    cargo_hold_deadline = Column(DateTime, nullable=True, comment="Deadline to complete CBG loading (based on Capesize ETA)")
    cargo_hold_violation = Column(Boolean, default=False, nullable=False, comment="Whether cargo hold constraint was violated")
    days_until_capesize_eta = Column(Integer, nullable=True, comment="Days between CBG completion and Capesize ETA")
    
    # ENHANCED SUBLET functionality
    is_sublet = Column(Boolean, default=False, nullable=False, index=True, comment="Whether this operation is sublet to another partner")
    sublet_status = Column(Enum(SubletStatus), nullable=True, comment="Sublet status if applicable")
    sublet_to_partner_id = Column(Integer, ForeignKey('partners.id'), nullable=True, index=True, comment="Partner this operation is sublet to")
    sublet_reason = Column(Text, nullable=True, comment="Reason for subletting")
    sublet_commercial_terms = Column(Text, nullable=True, comment="Commercial terms for sublet")
    sublet_created_at = Column(DateTime, nullable=True, comment="When sublet was created")
    sublet_created_by = Column(Integer, nullable=True, comment="User who created sublet")
    sublet_approved_at = Column(DateTime, nullable=True, comment="When sublet was approved")
    sublet_approved_by = Column(Integer, nullable=True, comment="User who approved sublet")
    sublet_approval_notes = Column(Text, nullable=True, comment="Approval notes for sublet")
    sublet_completed_at = Column(DateTime, nullable=True, comment="When sublet was completed")
    sublet_completed_by = Column(Integer, nullable=True, comment="User who completed sublet")
    sublet_completion_notes = Column(Text, nullable=True, comment="Completion notes for sublet")
    sublet_cancelled_at = Column(DateTime, nullable=True, comment="When sublet was cancelled")
    sublet_cancelled_by = Column(Integer, nullable=True, comment="User who cancelled sublet")
    sublet_cancellation_reason = Column(Text, nullable=True, comment="Reason for sublet cancellation")
    
    # Performance tracking
    total_operation_duration_hours = Column(Decimal(precision=6, scale=2), nullable=True, comment="Total operation duration from start to completion")
    fuel_consumption_mt = Column(Decimal(precision=8, scale=2), nullable=True, comment="Fuel consumption for this operation")
    operation_cost_usd = Column(Decimal(precision=12, scale=2), nullable=True, comment="Total operation cost")
    
    # Weather and conditions
    weather_conditions = Column(String(200), nullable=True, comment="Weather conditions during operation")
    sea_state = Column(String(50), nullable=True, comment="Sea state during operation")
    
    # Audit fields
    last_updated_by = Column(Integer, nullable=True, comment="User who last updated this operation")
    
    # Relationships
    transloader_schedule = relationship('TransloaderSchedule', back_populates='operations')
    capesize_vessel = relationship('CapesizeScheduleEntry')
    cbg_lineup = relationship('CBGPortLineup')
    sublet_to_partner = relationship('Partner', foreign_keys=[sublet_to_partner_id])
    transloader_fleet_vessel = relationship('TransloaderFleet', back_populates='operations')  # NEW RELATIONSHIP
    
    # Indexes
    __table_args__ = (
        Index('idx_transloader_op_schedule_vessel', 'transloader_schedule_id', 'transloader_fleet_vessel_id'),
        Index('idx_transloader_op_status', 'status'),
        Index('idx_transloader_op_capesize', 'capesize_vessel_id'),
        Index('idx_transloader_op_sublet', 'is_sublet', 'sublet_status'),
        Index('idx_transloader_op_cargo_hold', 'cargo_hold_deadline'),
        Index('idx_transloader_op_fleet_vessel', 'transloader_fleet_vessel_id'),
    )
    
    # ENHANCED METHODS WITH DYNAMIC FLEET SUPPORT
    
    def get_vessel_name(self):
        """Get the vessel name from the dynamic fleet."""
        return self.transloader_fleet_vessel.vessel_name if self.transloader_fleet_vessel else "Unknown Vessel"
    
    def get_vessel_code(self):
        """Get the vessel code from the dynamic fleet."""
        return self.transloader_fleet_vessel.vessel_code if self.transloader_fleet_vessel else "UNK"
    
    def get_vessel_capacity(self):
        """Get the vessel capacity from the dynamic fleet."""
        return self.transloader_fleet_vessel.capacity_mt if self.transloader_fleet_vessel else 0
    
    def get_vessel_specifications(self):
        """Get comprehensive vessel specifications."""
        if not self.transloader_fleet_vessel:
            return None
        
        return self.transloader_fleet_vessel.get_vessel_summary()
    
    def create_sublet(self, sublet_to_partner_id, reason, commercial_terms, created_by_user_id):
        """Create sublet arrangement."""
        if self.is_sublet:
            raise ValueError("Operation is already sublet")
        
        if self.status not in [TransloaderOperationStatus.PLANNED]:
            raise ValueError(f"Cannot sublet operation in status: {self.status.value}")
        
        self.is_sublet = True
        self.sublet_status = SubletStatus.ACTIVE
        self.sublet_to_partner_id = sublet_to_partner_id
        self.sublet_reason = reason
        self.sublet_commercial_terms = commercial_terms
        self.sublet_created_at = datetime.utcnow()
        self.sublet_created_by = created_by_user_id
        self.status = TransloaderOperationStatus.SUBLET
        
        return {
            'status': 'sublet_created',
            'vessel_name': self.get_vessel_name(),
            'vessel_code': self.get_vessel_code(),
            'sublet_to_partner_id': sublet_to_partner_id,
            'reason': reason,
            'commercial_terms': commercial_terms,
            'created_at': self.sublet_created_at
        }
    
    def start_cbg_loading(self, start_time, updated_by_user_id=None):
        """Start CBG loading phase with vessel performance tracking."""
        if self.status != TransloaderOperationStatus.PLANNED and self.status != TransloaderOperationStatus.SUBLET:
            raise ValueError(f"Cannot start CBG loading from status: {self.status.value}")
        
        self.cbg_loading_start = start_time
        self.status = TransloaderOperationStatus.CBG_LOADING
        self.last_updated_by = updated_by_user_id
        
        return {
            'status': 'cbg_loading_started',
            'vessel_name': self.get_vessel_name(),
            'vessel_capacity': self.get_vessel_capacity(),
            'start_time': start_time
        }
    
    def complete_cbg_loading(self, actual_completion, actual_tonnage, moisture_content=None, updated_by_user_id=None):
        """Complete CBG loading phase with enhanced performance tracking."""
        if self.status != TransloaderOperationStatus.CBG_LOADING:
            raise ValueError(f"Cannot complete CBG loading from status: {self.status.value}")
        
        self.cbg_loading_completion = actual_completion
        self.actual_tonnage = actual_tonnage
        self.status = TransloaderOperationStatus.CBG_COMPLETED
        self.last_updated_by = updated_by_user_id
        
        if moisture_content:
            self.moisture_content = moisture_content
        
        # Calculate loading duration and rate
        if self.cbg_loading_start:
            duration = (actual_completion - self.cbg_loading_start).total_seconds() / 3600
            self.cbg_loading_duration_hours = Decimal(str(round(duration, 2)))
            
            if duration > 0:
                rate = actual_tonnage / duration
                self.cbg_loading_rate_tph = Decimal(str(round(rate, 2)))
        
        # Check cargo hold constraint
        within_limit = True
        days_until_capesize = None
        
        if self.capesize_vessel and self.capesize_vessel.eta:
            days_until_capesize = (self.capesize_vessel.eta.date() - actual_completion.date()).days
            self.days_until_capesize_eta = days_until_capesize
            
            # Check if within cargo hold limit
            cargo_hold_limit = getattr(self.capesize_vessel, 'cargo_hold_days', 5)
            if days_until_capesize > cargo_hold_limit:
                self.cargo_hold_violation = True
                within_limit = False
        
        return {
            'status': 'cbg_loading_completed',
            'vessel_name': self.get_vessel_name(),
            'completion_time': actual_completion,
            'actual_tonnage': actual_tonnage,
            'loading_duration_hours': float(self.cbg_loading_duration_hours) if self.cbg_loading_duration_hours else None,
            'loading_rate_tph': float(self.cbg_loading_rate_tph) if self.cbg_loading_rate_tph else None,
            'within_hold_limit': within_limit,
            'days_until_capesize_eta': days_until_capesize,
            'cargo_hold_violation': self.cargo_hold_violation
        }
    
    def start_transit_to_capesize(self, start_time, updated_by_user_id=None):
        """Start transit to Capesize phase."""
        if self.status != TransloaderOperationStatus.CBG_COMPLETED:
            raise ValueError(f"Cannot start transit from status: {self.status.value}")
        
        self.transit_start = start_time
        self.status = TransloaderOperationStatus.TRANSIT_TO_CAPESIZE
        self.last_updated_by = updated_by_user_id
        
        return {
            'status': 'transit_started',
            'vessel_name': self.get_vessel_name(),
            'start_time': start_time
        }
    
    def start_discharge_to_capesize(self, start_time, updated_by_user_id=None):
        """Start discharge to Capesize phase."""
        if self.status != TransloaderOperationStatus.TRANSIT_TO_CAPESIZE:
            raise ValueError(f"Cannot start discharge from status: {self.status.value}")
        
        # Complete transit phase
        if self.transit_start:
            transit_duration = (start_time - self.transit_start).total_seconds() / 3600
            self.transit_duration_hours = Decimal(str(round(transit_duration, 2)))
        
        self.transit_completion = start_time
        self.discharge_start = start_time
        self.status = TransloaderOperationStatus.DISCHARGING_TO_CAPESIZE
        self.last_updated_by = updated_by_user_id
        
        return {
            'status': 'discharge_started',
            'vessel_name': self.get_vessel_name(),
            'start_time': start_time,
            'transit_duration_hours': float(self.transit_duration_hours) if self.transit_duration_hours else None
        }
    
    def complete_discharge_to_capesize(self, completion_time, updated_by_user_id=None):
        """Complete discharge to Capesize phase with performance tracking."""
        if self.status != TransloaderOperationStatus.DISCHARGING_TO_CAPESIZE:
            raise ValueError(f"Cannot complete discharge from status: {self.status.value}")
        
        self.discharge_completion = completion_time
        self.status = TransloaderOperationStatus.COMPLETED
        self.last_updated_by = updated_by_user_id
        
        # Calculate discharge duration and rate
        if self.discharge_start:
            duration = (completion_time - self.discharge_start).total_seconds() / 3600
            self.discharge_duration_hours = Decimal(str(round(duration, 2)))
            
            if duration > 0 and self.actual_tonnage:
                rate = self.actual_tonnage / duration
                self.discharge_rate_tph = Decimal(str(round(rate, 2)))
        
        # Calculate total operation duration
        if self.cbg_loading_start:
            total_duration = (completion_time - self.cbg_loading_start).total_seconds() / 3600
            self.total_operation_duration_hours = Decimal(str(round(total_duration, 2)))
        
        # Update vessel performance metrics
        if self.transloader_fleet_vessel:
            self.transloader_fleet_vessel.update_performance_metrics()
        
        return {
            'status': 'operation_completed',
            'vessel_name': self.get_vessel_name(),
            'completion_time': completion_time,
            'discharge_duration_hours': float(self.discharge_duration_hours) if self.discharge_duration_hours else None,
            'discharge_rate_tph': float(self.discharge_rate_tph) if self.discharge_rate_tph else None,
            'total_operation_duration_hours': float(self.total_operation_duration_hours) if self.total_operation_duration_hours else None
        }
    
    @classmethod
    def get_operations_by_vessel(cls, vessel_id, include_completed=True):
        """Get operations by specific vessel."""
        query = cls.query.filter_by(transloader_fleet_vessel_id=vessel_id)
        
        if not include_completed:
            query = query.filter(cls.status != TransloaderOperationStatus.COMPLETED)
        
        return query.order_by(cls.cbg_loading_start.desc()).all()
    
    @classmethod
    def get_vessel_utilization_statistics(cls, vessel_id, start_date=None, end_date=None):
        """Get comprehensive utilization statistics for a specific vessel."""
        query = cls.query.filter_by(transloader_fleet_vessel_id=vessel_id)
        
        if start_date:
            query = query.filter(cls.cbg_loading_start >= start_date)
        if end_date:
            query = query.filter(cls.cbg_loading_start <= end_date)
        
        operations = query.all()
        
        if not operations:
            return {
                'vessel_id': vessel_id,
                'total_operations': 0,
                'completed_operations': 0,
                'total_tonnage_handled': 0,
                'average_loading_rate_tph': 0,
                'average_discharge_rate_tph': 0,
                'average_operation_duration_hours': 0
            }
        
        completed_operations = [op for op in operations if op.status == TransloaderOperationStatus.COMPLETED]
        total_tonnage = sum(op.actual_tonnage or op.planned_tonnage for op in operations)
        
        # Calculate averages for completed operations
        avg_loading_rate = 0
        avg_discharge_rate = 0
        avg_duration = 0
        
        if completed_operations:
            loading_rates = [float(op.cbg_loading_rate_tph) for op in completed_operations if op.cbg_loading_rate_tph]
            discharge_rates = [float(op.discharge_rate_tph) for op in completed_operations if op.discharge_rate_tph]
            durations = [float(op.total_operation_duration_hours) for op in completed_operations if op.total_operation_duration_hours]
            
            avg_loading_rate = sum(loading_rates) / len(loading_rates) if loading_rates else 0
            avg_discharge_rate = sum(discharge_rates) / len(discharge_rates) if discharge_rates else 0
            avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'vessel_id': vessel_id,
            'total_operations': len(operations),
            'completed_operations': len(completed_operations),
            'total_tonnage_handled': total_tonnage,
            'average_loading_rate_tph': round(avg_loading_rate, 2),
            'average_discharge_rate_tph': round(avg_discharge_rate, 2),
            'average_operation_duration_hours': round(avg_duration, 2)
        }
    
    def get_operation_summary(self):
        """Get comprehensive operation summary."""
        return {
            'operation_info': {
                'operation_number': self.operation_number,
                'status': self.status.value,
                'planned_tonnage': self.planned_tonnage,
                'actual_tonnage': self.actual_tonnage
            },
            'vessel_info': {
                'vessel_name': self.get_vessel_name(),
                'vessel_code': self.get_vessel_code(),
                'vessel_capacity': self.get_vessel_capacity()
            },
            'timing': {
                'cbg_loading_start': self.cbg_loading_start,
                'cbg_loading_completion': self.cbg_loading_completion,
                'transit_start': self.transit_start,
                'discharge_start': self.discharge_start,
                'discharge_completion': self.discharge_completion,
                'total_duration_hours': float(self.total_operation_duration_hours) if self.total_operation_duration_hours else None
            },
            'performance': {
                'cbg_loading_rate_tph': float(self.cbg_loading_rate_tph) if self.cbg_loading_rate_tph else None,
                'discharge_rate_tph': float(self.discharge_rate_tph) if self.discharge_rate_tph else None,
                'cargo_hold_violation': self.cargo_hold_violation,
                'days_until_capesize_eta': self.days_until_capesize_eta
            },
            'sublet_info': {
                'is_sublet': self.is_sublet,
                'sublet_status': self.sublet_status.value if self.sublet_status else None,
                'sublet_to_partner': self.sublet_to_partner.name if self.sublet_to_partner else None
            } if self.is_sublet else None
        }
    
    def __repr__(self):
        vessel_name = self.get_vessel_name()
        sublet_info = f" (SUBLET to {self.sublet_to_partner.name})" if self.is_sublet and self.sublet_to_partner else ""
        return f"<TransloaderOperation {self.operation_number} - {vessel_name} ({self.status.value}){sublet_info}>"


# ===============================================================================
# UPDATED TRANSLOADER SCHEDULE MODEL
# ===============================================================================

class TransloaderSchedule(BaseModel):
    """
    Enhanced Transloader Schedule Model
    
    Now supports dynamic fleet management and advanced vessel assignment.
    """
    __tablename__ = 'transloader_schedules'
    
    # Schedule identification
    name = Column(String(255), nullable=False, index=True, comment="Schedule name")
    description = Column(Text, nullable=True, comment="Schedule description")
    year = Column(Integer, nullable=False, index=True, comment="Schedule year")
    
    # Schedule settings
    allow_sublet_operations = Column(Boolean, default=True, nullable=False, comment="Whether sublet operations are allowed")
    require_sublet_approval = Column(Boolean, default=True, nullable=False, comment="Whether sublet operations require approval")
    max_sublet_percentage = Column(Decimal(precision=5, scale=2), default=50.0, nullable=False, comment="Maximum percentage of operations that can be sublet")
    
    # Fleet management settings
    enable_automatic_vessel_assignment = Column(Boolean, default=True, nullable=False, comment="Enable automatic vessel assignment based on availability")
    preferred_vessel_assignment_strategy = Column(String(50), default='round_robin', nullable=False, comment="Vessel assignment strategy")
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False, index=True, comment="Whether this is the active schedule")
    is_published = Column(Boolean, default=False, nullable=False, comment="Whether this schedule is published")
    
    # Relationships
    operations = relationship('TransloaderOperation', back_populates='transloader_schedule', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('year', 'is_active', name='uq_transloader_schedule_active_year'),
        Index('idx_transloader_schedule_year_active', 'year', 'is_active'),
    )
    
    @classmethod
    def get_active_schedule(cls):
        """Get the currently active transloader schedule."""
        return cls.query.filter_by(is_active=True).first()
    
    def get_available_vessels(self, operation_date=None, min_capacity=None):
        """Get available vessels for assignment."""
        available_vessels = TransloaderFleet.get_available_vessels(
            vessel_type=VesselType.TRANSLOADER,
            min_capacity=min_capacity
        )
        
        if operation_date:
            # Filter out vessels that are scheduled for maintenance on the operation date
            available_vessels = [
                vessel for vessel in available_vessels
                if not (vessel.next_maintenance_due and vessel.next_maintenance_due <= operation_date)
            ]
        
        return available_vessels
    
    def assign_vessel_to_operation(self, operation_id, vessel_id=None, assignment_strategy=None):
        """Assign vessel to operation using specified strategy or automatic assignment."""
        operation = next((op for op in self.operations if op.id == operation_id), None)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found in this schedule")
        
        if vessel_id:
            # Manual assignment
            vessel = TransloaderFleet.query.get(vessel_id)
            if not vessel:
                raise ValueError(f"Vessel {vessel_id} not found")
            
            if vessel.status != VesselStatus.ACTIVE or not vessel.is_available:
                raise ValueError(f"Vessel {vessel.vessel_name} is not available")
            
            operation.transloader_fleet_vessel_id = vessel_id
            
            return {
                'status': 'vessel_assigned',
                'operation_number': operation.operation_number,
                'vessel_name': vessel.vessel_name,
                'vessel_code': vessel.vessel_code,
                'assignment_type': 'manual'
            }
        
        elif self.enable_automatic_vessel_assignment:
            # Automatic assignment
            strategy = assignment_strategy or self.preferred_vessel_assignment_strategy
            available_vessels = self.get_available_vessels()
            
            if not available_vessels:
                raise ValueError("No vessels available for assignment")
            
            assigned_vessel = self._apply_assignment_strategy(available_vessels, strategy)
            operation.transloader_fleet_vessel_id = assigned_vessel.id
            
            return {
                'status': 'vessel_assigned',
                'operation_number': operation.operation_number,
                'vessel_name': assigned_vessel.vessel_name,
                'vessel_code': assigned_vessel.vessel_code,
                'assignment_type': 'automatic',
                'assignment_strategy': strategy
            }
        
        else:
            raise ValueError("Automatic vessel assignment is disabled and no vessel specified")
    
    def _apply_assignment_strategy(self, available_vessels, strategy):
        """Apply vessel assignment strategy."""
        if strategy == 'round_robin':
            # Assign to vessel with least recent assignment
            vessel_last_operation = {}
            for vessel in available_vessels:
                last_op = TransloaderOperation.query.filter_by(
                    transloader_fleet_vessel_id=vessel.id
                ).order_by(TransloaderOperation.cbg_loading_start.desc()).first()
                
                vessel_last_operation[vessel.id] = last_op.cbg_loading_start if last_op and last_op.cbg_loading_start else datetime.min
            
            return min(available_vessels, key=lambda v: vessel_last_operation[v.id])
        
        elif strategy == 'capacity_optimized':
            # Assign vessel with capacity closest to planned tonnage
            if self.operations:
                avg_tonnage = sum(op.planned_tonnage for op in self.operations) / len(self.operations)
                return min(available_vessels, key=lambda v: abs(v.capacity_mt - avg_tonnage))
            else:
                return available_vessels[0]
        
        elif strategy == 'performance_based':
            # Assign vessel with best performance metrics
            return max(available_vessels, key=lambda v: v.average_loading_rate_tph or 0)
        
        else:
            # Default: first available
            return available_vessels[0]
    
    def optimize_vessel_assignments(self):
        """Optimize vessel assignments for all operations in the schedule."""
        unassigned_operations = [op for op in self.operations if not op.transloader_fleet_vessel_id]
        optimization_results = []
        
        for operation in unassigned_operations:
            try:
                result = self.assign_vessel_to_operation(operation.id)
                optimization_results.append({
                    'operation_number': operation.operation_number,
                    'status': 'success',
                    'result': result
                })
            except ValueError as e:
                optimization_results.append({
                    'operation_number': operation.operation_number,
                    'status': 'error',
                    'error': str(e)
                })
        
        successful_assignments = [r for r in optimization_results if r['status'] == 'success']
        
        return {
            'status': 'optimization_completed',
            'total_operations': len(unassigned_operations),
            'successful_assignments': len(successful_assignments),
            'failed_assignments': len(optimization_results) - len(successful_assignments),
            'results': optimization_results
        }
    
    def get_fleet_utilization_summary(self):
        """Get comprehensive fleet utilization summary for this schedule."""
        fleet_vessels = TransloaderFleet.get_available_vessels(vessel_type=VesselType.TRANSLOADER)
        utilization_summary = {}
        
        for vessel in fleet_vessels:
            vessel_operations = [op for op in self.operations if op.transloader_fleet_vessel_id == vessel.id]
            completed_operations = [op for op in vessel_operations if op.status == TransloaderOperationStatus.COMPLETED]
            
            total_tonnage = sum(op.actual_tonnage or op.planned_tonnage for op in vessel_operations)
            utilization_percentage = (len(vessel_operations) / len(self.operations) * 100) if self.operations else 0
            
            utilization_summary[vessel.vessel_name] = {
                'vessel_code': vessel.vessel_code,
                'total_operations': len(vessel_operations),
                'completed_operations': len(completed_operations),
                'total_tonnage': total_tonnage,
                'utilization_percentage': round(utilization_percentage, 1),
                'capacity_mt': vessel.capacity_mt,
                'status': vessel.status.value,
                'is_available': vessel.is_available
            }
        
        return {
            'schedule_name': self.name,
            'year': self.year,
            'total_operations': len(self.operations),
            'total_fleet_vessels': len(fleet_vessels),
            'vessel_utilization': utilization_summary
        }
    
    def __repr__(self):
        status = "Active" if self.is_active else ("Published" if self.is_published else "Draft")
        return f"<TransloaderSchedule '{self.name}' - {self.year} ({status})>"


# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

def initialize_default_fleet(alcoa_partner_id):
    """Initialize the fleet with default CSL vessels."""
    default_vessels = [
        {
            'vessel_name': 'CSL Argosy',
            'vessel_code': 'ARG',
            'imo_number': '9123456',
            'capacity_mt': 58000,
            'dwt': 65000,
            'length_m': 225.0,
            'beam_m': 23.0,
            'draft_m': 12.5,
            'loading_rate_tph': 2000,
            'discharge_rate_tph': 1800,
            'transit_speed_knots': 12.5,
            'vessel_class': 'CSL Class',
            'flag_state': 'Canada',
            'owner_partner_id': alcoa_partner_id
        },
        {
            'vessel_name': 'CSL Acadian',
            'vessel_code': 'ACA',
            'imo_number': '9123457',
            'capacity_mt': 58000,
            'dwt': 65000,
            'length_m': 225.0,
            'beam_m': 23.0,
            'draft_m': 12.5,
            'loading_rate_tph': 2000,
            'discharge_rate_tph': 1800,
            'transit_speed_knots': 12.5,
            'vessel_class': 'CSL Class',
            'flag_state': 'Canada',
            'owner_partner_id': alcoa_partner_id
        }
    ]
    
    created_vessels = []
    for vessel_data in default_vessels:
        vessel = TransloaderFleet(**vessel_data)
        created_vessels.append(vessel)
    
    return created_vessels

def add_new_vessel_to_fleet(vessel_name, vessel_code, capacity_mt, owner_partner_id, **kwargs):
    """Add a new vessel to the fleet dynamically."""
    vessel = TransloaderFleet(
        vessel_name=vessel_name,
        vessel_code=vessel_code,
        capacity_mt=capacity_mt,
        owner_partner_id=owner_partner_id,
        **kwargs
    )
    
    return vessel

# ===============================================================================
# USAGE EXAMPLES
# ===============================================================================

"""
EXAMPLE USAGE:

# 1. Add a new vessel to the fleet
new_vessel = add_new_vessel_to_fleet(
    vessel_name="CSL Thunder Bay",
    vessel_code="THB",
    capacity_mt=60000,
    owner_partner_id=alcoa_partner_id,
    dwt=67000,
    length_m=230.0,
    loading_rate_tph=2200,
    vessel_class="CSL Enhanced Class"
)

# 2. Get available vessels
available_vessels = TransloaderFleet.get_available_vessels(min_capacity=55000)

# 3. Assign vessel to operation
schedule = TransloaderSchedule.get_active_schedule()
result = schedule.assign_vessel_to_operation(
    operation_id=123,
    vessel_id=new_vessel.id
)

# 4. Get fleet statistics
fleet_stats = TransloaderFleet.get_fleet_statistics()

# 5. Schedule maintenance
maintenance_result = new_vessel.schedule_maintenance(
    maintenance_date=date(2025, 3, 15),
    maintenance_type="Dry Dock",
    estimated_duration_days=14,
    updated_by_user_id=1
)

# 6. Get vessel utilization
utilization = TransloaderOperation.get_vessel_utilization_statistics(
    vessel_id=new_vessel.id,
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31)
)
"""

