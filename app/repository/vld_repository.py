"""
VLD Repository
=============

Repository for VLD (Vessel Loading Date) model with specialized operations 
for vessel loading date management, scheduling, and planning.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.orm import joinedload, selectinload

from app.lib.repository.base import BaseRepository
from app.models.vld import VLD, VLDStatus, VLDReassignmentHistory, VLDCancellationHistory, VLDDeferralHistory
from app.models.partner import Partner
from app.models.production import Production


class VLDRepository(BaseRepository[VLD]):
    """Repository for VLD operations."""
    
    def __init__(self):
        super().__init__(VLD)
    
    def get_by_production(self, production_id: int) -> List[VLD]:
        """Get all VLDs for a specific production."""
        return self.session.query(VLD).filter(
            VLD.production_id == production_id
        ).options(
            selectinload(VLD.current_partner),
            selectinload(VLD.original_partner)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_by_partner(self, partner_id: int, 
                      production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs for a specific partner."""
        query = self.session.query(VLD).filter(
            VLD.current_partner_id == partner_id
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.production)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_by_date_range(self, start_date: date, end_date: date,
                         production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs within a date range."""
        query = self.session.query(VLD).filter(
            and_(
                VLD.vld_date >= start_date,
                VLD.vld_date <= end_date
            )
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner),
            selectinload(VLD.production)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_by_status(self, status: VLDStatus,
                     production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs by status."""
        query = self.session.query(VLD).filter(
            VLD.status == status
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_active_vlds(self, production_id: Optional[int] = None) -> List[VLD]:
        """Get active VLDs (not completed or cancelled)."""
        query = self.session.query(VLD).filter(
            VLD.status.in_([
                VLDStatus.PLANNED,
                VLDStatus.NARROWED,
                VLDStatus.NOMINATED,
                VLDStatus.LOADING
            ])
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_upcoming_vlds(self, days_ahead: int = 30,
                         production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs coming up in the next N days."""
        end_date = date.today() + timedelta(days=days_ahead)
        
        query = self.session.query(VLD).filter(
            and_(
                VLD.vld_date >= date.today(),
                VLD.vld_date <= end_date,
                VLD.status != VLDStatus.CANCELLED
            )
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_overdue_vlds(self, production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs that are overdue (past VLD date but not completed)."""
        query = self.session.query(VLD).filter(
            and_(
                VLD.vld_date < date.today(),
                VLD.status.in_([
                    VLDStatus.PLANNED,
                    VLDStatus.NARROWED,
                    VLDStatus.NOMINATED,
                    VLDStatus.LOADING
                ])
            )
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner)
        ).order_by(VLD.vld_date.asc()).all()
    
    def get_deferred_vlds(self, production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs that have been deferred."""
        query = self.session.query(VLD).filter(
            VLD.is_deferred == True
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner),
            selectinload(VLD.deferral_history)
        ).order_by(desc(VLD.total_deferred_days)).all()
    
    def get_cancelled_vlds(self, production_id: Optional[int] = None) -> List[VLD]:
        """Get cancelled VLDs."""
        query = self.session.query(VLD).filter(
            VLD.status == VLDStatus.CANCELLED
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner),
            selectinload(VLD.cancellation_history)
        ).order_by(desc(VLD.cancelled_date)).all()
    
    def get_reassigned_vlds(self, production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs that have been reassigned."""
        query = self.session.query(VLD).filter(
            VLD.reassignment_count > 0
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner),
            selectinload(VLD.original_partner),
            selectinload(VLD.reassignment_history)
        ).order_by(desc(VLD.reassignment_count)).all()
    
    def get_carried_over_vlds(self, entity_id: int,
                             production_id: Optional[int] = None) -> List[VLD]:
        """Get VLDs carried over by a specific entity."""
        # This would need to be implemented based on the entity relationship
        # For now, return VLDs where original and current partners differ
        query = self.session.query(VLD).filter(
            VLD.original_partner_id != VLD.current_partner_id
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner),
            selectinload(VLD.original_partner)
        ).order_by(VLD.vld_date.asc()).all()
    
    def create_vld(self, production_id: int, partner_id: int, vld_date: date,
                  planned_tonnage: int, vessel_size_t: int,
                  **kwargs) -> VLD:
        """Create a new VLD."""
        # Calculate layday automatically (5 days before, 6 days after)
        layday_start = vld_date - timedelta(days=5)
        layday_end = vld_date + timedelta(days=6)
        
        vld = VLD(
            production_id=production_id,
            original_partner_id=partner_id,
            current_partner_id=partner_id,
            vld_date=vld_date,
            planned_tonnage=planned_tonnage,
            vessel_size_t=vessel_size_t,
            layday_start=layday_start,
            layday_end=layday_end,
            status=VLDStatus.PLANNED,
            **kwargs
        )
        
        self.session.add(vld)
        self.session.commit()
        return vld
    
    def update_status(self, vld_id: int, new_status: VLDStatus,
                     **kwargs) -> Optional[VLD]:
        """Update VLD status with validation."""
        vld = self.get_by_id(vld_id)
        if not vld:
            return None
        
        # Update additional fields based on status
        if new_status == VLDStatus.NOMINATED:
            if 'vessel_name' in kwargs:
                vld.vessel_name = kwargs['vessel_name']
        
        elif new_status == VLDStatus.LOADING:
            if not vld.loading_start_time:
                vld.loading_start_time = datetime.utcnow()
        
        elif new_status == VLDStatus.COMPLETED:
            if not vld.loading_completion_time:
                vld.loading_completion_time = datetime.utcnow()
            if 'actual_tonnage' in kwargs:
                vld.actual_tonnage = kwargs['actual_tonnage']
            if 'moisture_content' in kwargs:
                vld.moisture_content = kwargs['moisture_content']
            if 'loader_number' in kwargs:
                vld.loader_number = kwargs['loader_number']
        
        vld.status = new_status
        self.session.commit()
        return vld
    
    def set_narrow_period(self, vld_id: int, narrow_start: date, narrow_end: date,
                         exception_reason: Optional[str] = None) -> Optional[VLD]:
        """Set narrow period for a VLD."""
        vld = self.get_by_id(vld_id)
        if not vld:
            return None
        
        # Check if narrow is within layday
        if vld.layday_start and vld.layday_end:
            narrow_within_layday = (
                vld.layday_start <= narrow_start <= vld.layday_end and
                vld.layday_start <= narrow_end <= vld.layday_end
            )
            
            if not narrow_within_layday:
                if not exception_reason:
                    raise ValueError("Narrow period outside layday requires exception reason")
                vld.narrow_exception_ok = True
                vld.narrow_exception_reason = exception_reason
        
        vld.narrow_period_start = narrow_start
        vld.narrow_period_end = narrow_end
        vld.status = VLDStatus.NARROWED
        
        self.session.commit()
        return vld
    
    def reassign_vld(self, vld_id: int, new_partner_id: int,
                    reason: str) -> Optional[VLD]:
        """Reassign VLD to a different partner."""
        vld = self.get_by_id(vld_id)
        if not vld:
            return None
        
        old_partner_id = vld.current_partner_id
        
        # Create reassignment history record
        history = VLDReassignmentHistory(
            vld_id=vld_id,
            old_partner_id=old_partner_id,
            new_partner_id=new_partner_id,
            reason=reason,
            reassigned_at=datetime.utcnow()
        )
        
        vld.current_partner_id = new_partner_id
        vld.reassignment_count = (vld.reassignment_count or 0) + 1
        vld.last_reassignment_reason = reason
        
        self.session.add(history)
        self.session.commit()
        return vld
    
    def defer_vld(self, vld_id: int, new_date: date,
                 reason: Optional[str] = None) -> Optional[VLD]:
        """Defer VLD to a new date."""
        vld = self.get_by_id(vld_id)
        if not vld:
            return None
        
        if new_date <= vld.vld_date:
            raise ValueError("New VLD date must be after current date")
        
        old_date = vld.vld_date
        days_deferred = (new_date - old_date).days
        
        # Create deferral history
        history = VLDDeferralHistory(
            vld_id=vld_id,
            old_vld_date=old_date,
            new_vld_date=new_date,
            days_deferred=days_deferred,
            reason=reason,
            deferred_at=datetime.utcnow()
        )
        
        # Update VLD
        if not vld.original_vld_date:
            vld.original_vld_date = old_date
        
        vld.vld_date = new_date
        vld.is_deferred = True
        vld.total_deferred_days = (vld.total_deferred_days or 0) + days_deferred
        vld.deferral_count = (vld.deferral_count or 0) + 1
        
        # Recalculate layday
        vld.layday_start = new_date - timedelta(days=5)
        vld.layday_end = new_date + timedelta(days=6)
        
        self.session.add(history)
        self.session.commit()
        return vld
    
    def cancel_vld(self, vld_id: int, reason: str) -> Optional[VLD]:
        """Cancel a VLD."""
        vld = self.get_by_id(vld_id)
        if not vld:
            return None
        
        # Create cancellation history
        history = VLDCancellationHistory(
            vld_id=vld_id,
            reason=reason,
            cancelled_at=datetime.utcnow(),
            status_before_cancellation=vld.status
        )
        
        vld.status_before_cancellation = vld.status
        vld.status = VLDStatus.CANCELLED
        vld.cancellation_reason = reason
        vld.cancelled_date = datetime.utcnow()
        vld.cancellation_count = (vld.cancellation_count or 0) + 1
        
        self.session.add(history)
        self.session.commit()
        return vld
    
    def uncancel_vld(self, vld_id: int, reason: str) -> Optional[VLD]:
        """Restore a cancelled VLD."""
        vld = self.get_by_id(vld_id)
        if not vld or vld.status != VLDStatus.CANCELLED:
            return None
        
        # Restore previous status
        previous_status = vld.status_before_cancellation or VLDStatus.PLANNED
        vld.status = previous_status
        vld.uncancelled_reason = reason
        vld.uncancelled_date = datetime.utcnow()
        
        self.session.commit()
        return vld
    
    def get_vld_statistics(self, production_id: Optional[int] = None,
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get comprehensive VLD statistics."""
        query = self.session.query(VLD)
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        if start_date and end_date:
            query = query.filter(
                and_(
                    VLD.vld_date >= start_date,
                    VLD.vld_date <= end_date
                )
            )
        
        total_vlds = query.count()
        
        # Status distribution
        status_stats = query.with_entities(
            VLD.status,
            func.count(VLD.id).label('count')
        ).group_by(VLD.status).all()
        
        # Tonnage statistics
        tonnage_stats = query.with_entities(
            func.sum(VLD.planned_tonnage).label('total_planned'),
            func.sum(VLD.actual_tonnage).label('total_actual'),
            func.avg(VLD.planned_tonnage).label('avg_planned'),
            func.avg(VLD.actual_tonnage).label('avg_actual')
        ).first()
        
        # Deferral statistics
        deferred_count = query.filter(VLD.is_deferred == True).count()
        avg_deferral_days = query.filter(
            VLD.total_deferred_days > 0
        ).with_entities(
            func.avg(VLD.total_deferred_days)
        ).scalar() or 0
        
        # Reassignment statistics
        reassigned_count = query.filter(VLD.reassignment_count > 0).count()
        
        # Cancellation statistics
        cancelled_count = query.filter(VLD.status == VLDStatus.CANCELLED).count()
        
        return {
            'total_vlds': total_vlds,
            'status_distribution': {
                status.value: count for status, count in status_stats
            },
            'tonnage': {
                'total_planned': int(tonnage_stats.total_planned) if tonnage_stats.total_planned else 0,
                'total_actual': int(tonnage_stats.total_actual) if tonnage_stats.total_actual else 0,
                'average_planned': float(tonnage_stats.avg_planned) if tonnage_stats.avg_planned else 0,
                'average_actual': float(tonnage_stats.avg_actual) if tonnage_stats.avg_actual else 0,
                'achievement_rate': (tonnage_stats.total_actual / tonnage_stats.total_planned * 100) 
                                  if tonnage_stats.total_planned else 0
            },
            'deferrals': {
                'deferred_count': deferred_count,
                'deferral_rate': deferred_count / total_vlds * 100 if total_vlds else 0,
                'average_deferral_days': round(float(avg_deferral_days), 1)
            },
            'reassignments': {
                'reassigned_count': reassigned_count,
                'reassignment_rate': reassigned_count / total_vlds * 100 if total_vlds else 0
            },
            'cancellations': {
                'cancelled_count': cancelled_count,
                'cancellation_rate': cancelled_count / total_vlds * 100 if total_vlds else 0
            }
        }
    
    def get_partner_vld_performance(self, partner_id: int,
                                   production_id: Optional[int] = None) -> Dict[str, Any]:
        """Get VLD performance metrics for a specific partner."""
        query = self.session.query(VLD).filter(
            VLD.current_partner_id == partner_id
        )
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        vlds = query.all()
        completed_vlds = [v for v in vlds if v.status == VLDStatus.COMPLETED]
        
        total_planned = sum(v.planned_tonnage for v in vlds)
        total_actual = sum(v.actual_tonnage for v in completed_vlds if v.actual_tonnage)
        
        on_time_completions = sum(
            1 for v in completed_vlds
            if v.loading_completion_time and v.vld_date and
            v.loading_completion_time.date() <= v.vld_date
        )
        
        return {
            'partner_id': partner_id,
            'total_vlds': len(vlds),
            'completed_vlds': len(completed_vlds),
            'completion_rate': len(completed_vlds) / len(vlds) * 100 if vlds else 0,
            'tonnage': {
                'planned': total_planned,
                'actual': total_actual,
                'achievement_rate': total_actual / total_planned * 100 if total_planned else 0
            },
            'punctuality': {
                'on_time_completions': on_time_completions,
                'on_time_rate': on_time_completions / len(completed_vlds) * 100 if completed_vlds else 0
            },
            'deferrals': sum(1 for v in vlds if v.is_deferred),
            'cancellations': sum(1 for v in vlds if v.status == VLDStatus.CANCELLED),
            'reassignments': sum(1 for v in vlds if v.reassignment_count > 0)
        }
    
    def get_monthly_vld_schedule(self, year: int, month: int,
                                production_id: Optional[int] = None) -> Dict[str, Any]:
        """Get VLD schedule for a specific month."""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        vlds = self.get_by_date_range(start_date, end_date, production_id)
        
        # Group by date
        schedule = {}
        for vld in vlds:
            date_str = vld.vld_date.isoformat()
            if date_str not in schedule:
                schedule[date_str] = []
            
            schedule[date_str].append({
                'vld_id': vld.id,
                'partner': vld.current_partner.name if vld.current_partner else None,
                'planned_tonnage': vld.planned_tonnage,
                'vessel_size': vld.vessel_size_t,
                'status': vld.status.value,
                'vessel_name': vld.vessel_name,
                'is_deferred': vld.is_deferred,
                'narrow_start': vld.narrow_period_start.isoformat() if vld.narrow_period_start else None,
                'narrow_end': vld.narrow_period_end.isoformat() if vld.narrow_period_end else None
            })
        
        # Calculate monthly totals
        total_planned = sum(v.planned_tonnage for v in vlds)
        total_actual = sum(v.actual_tonnage for v in vlds if v.actual_tonnage)
        
        return {
            'year': year,
            'month': month,
            'schedule': schedule,
            'summary': {
                'total_vlds': len(vlds),
                'total_planned_tonnage': total_planned,
                'total_actual_tonnage': total_actual,
                'partners': len(set(v.current_partner_id for v in vlds)),
                'status_counts': {
                    status.value: len([v for v in vlds if v.status == status])
                    for status in VLDStatus
                }
            }
        }
    
    def search_vlds(self, search_term: str,
                   production_id: Optional[int] = None) -> List[VLD]:
        """Search VLDs by vessel name, partner name, or loader number."""
        query = self.session.query(VLD).join(Partner, VLD.current_partner_id == Partner.id)
        
        search_filter = or_(
            VLD.vessel_name.ilike(f"%{search_term}%"),
            VLD.loader_number.ilike(f"%{search_term}%"),
            Partner.name.ilike(f"%{search_term}%")
        )
        
        query = query.filter(search_filter)
        
        if production_id:
            query = query.filter(VLD.production_id == production_id)
        
        return query.options(
            selectinload(VLD.current_partner)
        ).order_by(desc(VLD.vld_date)).all()

