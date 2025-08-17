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
    Date,
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


class VLDStatus(str, Enum):
    """VLD status enumeration."""
    PLANNED = "planned"
    NARROWED = "narrowed"
    NOMINATED = "nominated"
    LOADING = "loading"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    
class VLD(BaseModel):
    """VLD (Vessel Loading Date) model with comprehensive management."""
    __tablename__ = 'vlds'
    __mapper_args__ = {'eager_defaults': True}
    
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    vld_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="VLD date"
    )
    
    original_vld_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="In case of a deferral, track original date"
    )
    
    planned_tonnage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Planned Production for a partner"
    )
    
    vessel_size_t: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Planned vessel size for a partner"
    )
    
    # ---------------------------------------------------------------------
    # Status and Vessel Information
    # ---------------------------------------------------------------------
    status: Mapped[VLDStatus] = mapped_column(
        SQLEnum(VLDStatus, name="vld_status"), default=VLDStatus.PLANNED, server_default=text("'planned'"), nullable=False
    )
    
    vessel_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Vessel assigned to the VLD"
    )
    
    # ---------------------------------------------------------------------
    # Loader Number (assigned only vessel is loaded)
    # ---------------------------------------------------------------------
    loader_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
   # ---------------------------------------------------------------------
    # Layday and Narrow Period Management
    # -------------------------------------------------------------------- 
    layday_start: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="VLD Start Layday"
    )
    
    layday_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="VLD End Layday"
    )
    
    narrow_period_start: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="VLD Beginning of 7 days narrow"
    )
    
    narrow_period_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="VLD Ending of 7 days narrow"
    )
    
    narrow_exception_ok: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default=sql.false(),
    comment=" Allows exceptional out of layday narrows"
    )
    
    narrow_exception_reason: Mapped[Optional[str]] = mapped_column(
    Text, nullable=True, comment="Justifies exceptional narrow out of layday"
    )
    
    # ---------------------------------------------------------------------
    # Operational Tracking
    # ---------------------------------------------------------------------
    actual_tonnage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    moisture_content: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5,2),
        nullable=True
    )
    
    loading_start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    loading_completion_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Partner Management and Reassignment
    # ---------------------------------------------------------------------
    original_partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('partners.id', ondelete='RESTRICT'),
        nullable=False
    )
    
    current_partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('partners.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    reassignment_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False
    )
    
    last_reassignment_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Carry-over
    # ---------------------------------------------------------------------
    is_carry_over: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default=sql.false(),
    comment="True quando o VLD é usado por outro parceiro sem mudar a propriedade"
    )

    carry_over_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Justificativa/observação do carry-over"
    )
    
    # ---------------------------------------------------------------------
    # Cancellation Management
    # ---------------------------------------------------------------------
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
       Text,
       nullable=True 
    )
    
    cancelled_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    status_before_cancellation: Mapped[Optional[VLDStatus]] = mapped_column(
        SQLEnum(VLDStatus, name='vld_status'), nullable=True
    )
    
    uncancelled_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    uncancelled_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    cancellation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False
    )
    
    # ---------------------------------------------------------------------
    # Deferral Management
    # ---------------------------------------------------------------------
    is_deferred: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    total_deferred_days: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False
    )
    
    deferral_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0")
    )
    
    # ---------------------------------------------------------------------
    # Foreign Keys
    # ---------------------------------------------------------------------
    production_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('productions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    carried_by_partner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('partners.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
        comment="Parceiro que utiliza o VLD (sem alteração de propriedade)"
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    production: Mapped['Production'] = relationship(
        'Production',
        back_populates='vlds',
        lazy='selectin'
    )
    
    original_partner: Mapped['Partner'] = relationship(
        'Partner',
        foreign_keys=[original_partner_id]
    )
    
    current_partner: Mapped['Partner'] = relationship(
        'Partner',
        foreign_keys=[current_partner_id]
    )
    
    carried_by_partner: Mapped['Partner'] = relationship(
        'Partner',
        foreign_keys=[carried_by_partner_id]
    )
    
    reassignment_history: Mapped[List['VLDReassignmentHistory']] = relationship(
        'VLDReassignmentHistory',
        back_populates='vld',
        cascade='all, delete-orphan'
    )
    
    cancellation_history: Mapped[List['VLDCancellationHistory']] = relationship(
        'VLDCancellationHistory',
        back_populates='vld',
        cascade='all, delete-orphan'
    )
    
    deferral_history: Mapped[List['VLDDeferralHistory']] = relationship(
        'VLDDeferralHistory',
        back_populates='vld',
        cascade='all, delete-orphan'
    )

    lineups: Mapped[List["Lineup"]] = relationship(
        "Lineup",
        back_populates="vld",
        passive_deletes=True,
        lazy="selectin"
    )
    
    # ---------------------------------------------------------------------
    # Indexes and Constraints
    # ---------------------------------------------------------------------
    __table_args__ = (
        Index('idx_vld_date', 'vld_date'),
        Index('idx_vld_original_date', 'original_vld_date'),
        Index('idx_vld_current_partner', 'current_partner_id'),
        Index('idx_vld_status', 'status'),
        Index('idx_vld_date_partner', 'vld_date', 'current_partner_id'),
        UniqueConstraint('vld_date', 'current_partner_id', 'production_id', name='uq_vld_date_partner_production'),
        CheckConstraint('planned_tonnage > 0', name='check_planned_tonnage_positive'),
        CheckConstraint('vessel_size_t > 0', name='check_vessel_size_positive'),
        CheckConstraint('moisture_content >= 0 AND moisture_content <= 100', name='check_moisture_content_range'),
        CheckConstraint('total_deferred_days >= 0', name='check_total_deferred_days_nonneg'),
        CheckConstraint('deferral_count >= 0', name='check_deferral_count_nonneg'),
        CheckConstraint('cancellation_count >= 0', name='check_cancellation_count_nonneg'),
        CheckConstraint('(layday_start IS NULL) OR (layday_end IS NULL) OR (layday_start <= layday_end)', name='check_layday_range'),
        CheckConstraint('(narrow_period_start IS NULL) OR (narrow_period_end IS NULL) OR (narrow_period_start <= narrow_period_end)', name='check_narrow_range'),
        CheckConstraint("(narrow_exception_ok = 0) OR (narrow_exception_reason IS NOT NULL AND LENGTH(TRIM(narrow_exception_reason)) > 0)", name="check_narrow_exception_reason_when_ok"),
        CheckConstraint("(is_carry_over = 0 AND carried_by_partner_id IS NULL) OR (is_carry_over = 1 AND carried_by_partner_id IS NOT NULL)", name="check_carry_over_partner_presence"),
        CheckConstraint("carried_by_partner_id IS NULL OR carried_by_partner_id <> original_partner_id", name="check_carry_over_not_same_as_owner"),
        CheckConstraint("(is_carry_over = 0) OR (current_partner_id = original_partner_id)", name="check_carry_over_keeps_ownership"),
    )
    
    def __repr__(self):
        partner = getattr(self.current_partner, 'name', self.current_partner_id)
        return f'<VLD {self.vld_date} - {partner} - {self.status.value}>'
    
    @validates('status')
    def validate_status(self, key, value: VLDStatus):
        prev = getattr(self, 'status', None)
        if prev and prev != value:
            illegal = {
                VLDStatus.COMPLETED: {VLDStatus.PLANNED, VLDStatus.LOADING},
                VLDStatus.CANCELLED: {VLDStatus.LOADING, VLDStatus.NOMINATED},
            }
            if value in illegal.get(prev, set()):
                raise ValueError(f"Invalid status change: {prev.value} → {value.value}")

            # required fields per status
            if value in {VLDStatus.NOMINATED, VLDStatus.LOADING, VLDStatus.COMPLETED}:
                if not self.vessel_name:
                    raise ValueError(f"vessel_name is required when status is {value.value}")

            if value == VLDStatus.LOADING and not self.loading_start_time:
                self.loading_start_time = datetime.utcnow()

            if value == VLDStatus.COMPLETED:
                if not self.loading_completion_time:
                    self.loading_completion_time = datetime.utcnow()
                if not self.loader_number:
                    raise ValueError("loader_number is required when status is completed")
                if self.actual_tonnage is not None and self.actual_tonnage <= 0:
                    raise ValueError("actual_tonnage must be positive when completed")

            if value == VLDStatus.CANCELLED:
                # capture previous and require reason
                self.status_before_cancellation = prev
                if not self.cancellation_reason:
                    raise ValueError("cancellation_reason is required when cancelling")
                if not self.cancelled_date:
                    self.cancelled_date = datetime.utcnow()
                self.cancellation_count = (self.cancellation_count or 0) + 1

            if prev == VLDStatus.CANCELLED and value != VLDStatus.CANCELLED:
                # un-cancel flow
                if not self.uncancelled_reason:
                    raise ValueError("uncancelled_reason is required when reverting cancellation")
                if not self.uncancelled_date:
                    self.uncancelled_date = datetime.utcnow()

        return value
    
    @validates('actual_tonnage')
    def validate_actual(self, key, value):
        if value is not None and value <= 0:
            raise ValueError("actual_tonnage must be positive.")
        return value
    
    @validates('planned_tonnage', 'vessel_size_t')
    def validate_positive_numbers(self, key, value):
        if value is None or value <= 0:
            raise ValueError(f"{key} must be a positive integer.")
        return value
    
    @validates('moisture_content')
    def validate_moisture(self, key, value):
        if value is not None and not (Decimal('0') <= value <= Decimal('100')):
            raise ValueError("Moisture content must be between 0 and 100.")
        return value
    
    @validates('layday_start', 'layday_end', 'narrow_period_start', 'narrow_period_end',
           'vld_date', 'original_vld_date', 'narrow_exception_ok', 'narrow_exception_reason')
    def validate_date_ranges(self, key, value):
        # ordering
        if self.layday_start and self.layday_end and self.layday_start > self.layday_end:
            raise ValueError("Layday start must be ≤ layday end.")
        if self.narrow_period_start and self.narrow_period_end and self.narrow_period_start > self.narrow_period_end:
            raise ValueError("Narrow period start must be ≤ narrow period end.")

        # optional: exactly 7-day narrow
        if self.narrow_period_start and self.narrow_period_end:
            if (self.narrow_period_end - self.narrow_period_start).days != 6:
                raise ValueError("Narrow period must be exactly 7 consecutive days.")

        # keep vld_date within layday (remove if you also want exceptions here)
        if self.vld_date and self.layday_start and self.layday_end:
            if not (self.layday_start <= self.vld_date <= self.layday_end):
                raise ValueError("vld_date must be within layday window.")

        # narrow inside layday unless exception flag is set with a reason
        if self.narrow_period_start and self.narrow_period_end and self.layday_start and self.layday_end:
            narrow_inside = (self.layday_start <= self.narrow_period_start <= self.layday_end) and \
                            (self.layday_start <= self.narrow_period_end <= self.layday_end)
            if not narrow_inside:
                if not self.narrow_exception_ok:
                    raise ValueError("Narrow outside layday requires an exception (narrow_exception_ok=True).")
                if not self.narrow_exception_reason or not self.narrow_exception_reason.strip():
                    raise ValueError("narrow_exception_reason is required when allowing narrow outside layday.")

        # original date rule
        if self.original_vld_date and self.vld_date and self.original_vld_date > self.vld_date and not self.is_deferred:
            raise ValueError("original_vld_date cannot be after vld_date unless deferred.")

        return value
    
    def mark_carry_over(self, using_partner_id: int, *, reason: Optional[str] = None) -> None:
        if using_partner_id == self.original_partner_id:
            raise ValueError("Carry-over precisa ser para parceiro diferente do dono.")
        # Propriedade permanece com o dono
        self.current_partner_id = self.original_partner_id
        self.is_carry_over = True
        self.carried_by_partner_id = using_partner_id
        self.carry_over_reason = reason

    def clear_carry_over(self) -> None:
        self.is_carry_over = False
        self.carried_by_partner_id = None
        self.carry_over_reason = None

    def apply_deferral(self, new_date: date, reason: Optional[str] = None):
        if new_date <= self.vld_date:
            raise ValueError("New VLD date must be after current vld_date.")
        days = (new_date - self.vld_date).days

        self.deferral_history.append(VLDDeferralHistory(
            vld=self,
            old_vld_date=self.vld_date,
            new_vld_date=new_date,
            days_deferred=days,
            reason=reason
        ))
        self.original_vld_date = self.original_vld_date or self.vld_date
        self.vld_date = new_date
        self.is_deferred = True
        self.total_deferred_days = (self.total_deferred_days or 0) + days
        self.deferral_count = (self.deferral_count or 0) + 1

    
class VLDReassignmentHistory(BaseModel):
    """VLD reassignment history for audit trail."""
    __tablename__ = 'vld_reassignment_history'
    
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    vld_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('vlds.id', ondelete='CASCADE'),
        nullable=False
    )
    
    from_partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('partners.id'),
        nullable=False
    )
    
    to_partner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('partners.id'),
        nullable=False
    )
    
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    vld: Mapped['VLD'] = relationship(
        'VLD',
        back_populates='reassignment_history'
    )
    
    from_partner: Mapped['Partner'] = relationship(
        'Partner',
        foreign_keys=[from_partner_id]
    )
    
    to_partner: Mapped['Partner'] = relationship(
        'Partner',
        foreign_keys=[to_partner_id]
    )
    
    # ---------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        Index('idx_vld_reassignment_vld_id', 'vld_id'),
    )
    
class CancellationAction(str, Enum):
    CANCELLED = "cancelled"
    UNCANCELLED = "uncancelled"
    
class VLDCancellationHistory(BaseModel):
    """VLD cancellation/uncancellation history for audit trail"""
    __tablename__ = 'vld_cancellation_history'
    
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    vld_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('vlds.id', ondelete='CASCADE'),
        nullable=False
    )
    
    action_type: Mapped[CancellationAction] = mapped_column(
        SQLEnum(CancellationAction, name="cancellation_action_type"),
        nullable=False
    )
    
    status_before: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    status_after: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    reason: Mapped[Optional[str]]= mapped_column(
        Text,
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    vld: Mapped['VLD'] = relationship(
        'VLD',
        back_populates='cancellation_history'
    )
    
    # ---------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        Index('idx_vld_cancellation_vld_id', 'vld_id'),
        Index('idx_vld_cancellation_action', 'action_type'),
    )
    
class VLDDeferralHistory(BaseModel):
    """VLD deferral history for audit trail."""
    __tablename__ = 'vld_deferral_history'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ---------------------------------------------------------------------
    # Core fields
    # ---------------------------------------------------------------------
    vld_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('vlds.id', ondelete='CASCADE'),
        nullable=False
    )
    
    old_vld_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    
    new_vld_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    
    days_deferred: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    reason: Mapped[Optional[str]]= mapped_column(
        Text,
        nullable=True
    )
    
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------
    vld: Mapped['VLD'] = relationship(
        'VLD',
        back_populates='deferral_history'
    )
    
    # ---------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------
    __table_args__ = (
        Index('idx_vld_deferral_vld_id', 'vld_id'),
    )
