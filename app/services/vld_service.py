"""
VLD Service
==========

Business logic service for VLD (Vessel Loading Date) management with 
comprehensive scheduling, planning, and optimization capabilities.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.repository.vld_repository import VLDRepository
from app.repository.production_repository import ProductionRepository
from app.repository.partner_repository import PartnerRepository
from app.models.vld import VLD, VLDStatus
from app.models.production import Production
from app.models.partner import Partner


class VLDService:
    """Service for VLD business logic."""
    
    def __init__(self):
        self.vld_repo = VLDRepository()
        self.production_repo = ProductionRepository()
        self.partner_repo = PartnerRepository()
    
    def create_vld_schedule(self, production_id: int, partner_allocations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create VLD schedule for a production based on partner allocations."""
        production = self.production_repo.get_by_id(production_id)
        if not production:
            raise ValueError(f"Production {production_id} not found")
        
        if not production.is_active:
            raise ValueError("Production must be active to create VLD schedule")
        
        created_vlds = []
        errors = []
        
        for allocation in partner_allocations:
            try:
                partner_id = allocation['partner_id']
                tonnage = allocation['tonnage']
                vessel_size = allocation.get('vessel_size_t', 180000)  # Default capesize
                start_date = datetime.strptime(allocation['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(allocation['end_date'], '%Y-%m-%d').date()
                
                # Generate VLDs for the period
                vlds = self._generate_vlds_for_period(
                    production_id, partner_id, tonnage, vessel_size, start_date, end_date
                )
                
                created_vlds.extend(vlds)
                
            except Exception as e:
                errors.append({
                    'partner_id': allocation.get('partner_id'),
                    'error': str(e)
                })
        
        return {
            'success': len(errors) == 0,
            'created_vlds': len(created_vlds),
            'vlds': [vld.to_dict() for vld in created_vlds],
            'errors': errors,
            'message': f'Created {len(created_vlds)} VLDs with {len(errors)} errors'
        }
    
    def set_narrow_period(self, vld_id: int, narrow_start: date, narrow_end: date,
                         exception_reason: Optional[str] = None) -> Dict[str, Any]:
        """Set narrow period for a VLD with validation."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status != VLDStatus.PLANNED:
            raise ValueError("VLD must be in planned status to set narrow period")
        
        # Validate narrow period duration (must be exactly 7 days)
        if (narrow_end - narrow_start).days != 6:
            raise ValueError("Narrow period must be exactly 7 consecutive days")
        
        # Check if narrow is within layday
        narrow_within_layday = True
        if vld.layday_start and vld.layday_end:
            narrow_within_layday = (
                vld.layday_start <= narrow_start <= vld.layday_end and
                vld.layday_start <= narrow_end <= vld.layday_end
            )
        
        if not narrow_within_layday and not exception_reason:
            raise ValueError("Narrow period outside layday requires exception reason")
        
        try:
            updated_vld = self.vld_repo.set_narrow_period(
                vld_id, narrow_start, narrow_end, exception_reason
            )
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'narrow_period': {
                    'start': narrow_start.isoformat(),
                    'end': narrow_end.isoformat(),
                    'duration_days': 7,
                    'within_layday': narrow_within_layday,
                    'exception_approved': bool(exception_reason)
                },
                'message': f'Narrow period set for VLD {vld_id}'
            }
            
        except ValueError as e:
            raise e
    
    def nominate_vessel(self, vld_id: int, vessel_name: str,
                       imo: Optional[str] = None) -> Dict[str, Any]:
        """Nominate vessel for a VLD."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status not in [VLDStatus.PLANNED, VLDStatus.NARROWED]:
            raise ValueError("VLD must be planned or narrowed to nominate vessel")
        
        # Validate vessel name
        if not vessel_name or len(vessel_name.strip()) < 3:
            raise ValueError("Valid vessel name is required")
        
        try:
            updated_vld = self.vld_repo.update_status(
                vld_id, VLDStatus.NOMINATED, vessel_name=vessel_name.strip()
            )
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'vessel': {
                    'name': vessel_name.strip(),
                    'imo': imo
                },
                'message': f'Vessel {vessel_name} nominated for VLD {vld_id}'
            }
            
        except ValueError as e:
            raise e
    
    def defer_vld(self, vld_id: int, new_date: date, reason: str) -> Dict[str, Any]:
        """Defer VLD to a new date."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status in [VLDStatus.COMPLETED, VLDStatus.CANCELLED]:
            raise ValueError("Cannot defer completed or cancelled VLD")
        
        if new_date <= vld.vld_date:
            raise ValueError("New VLD date must be after current date")
        
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Detailed reason is required for deferral")
        
        # Check for conflicts with new date
        conflicts = self._check_vld_conflicts(vld.production_id, vld.current_partner_id, new_date)
        if conflicts:
            return {
                'success': False,
                'message': f'Conflict detected on new date: {conflicts}',
                'conflicts': conflicts
            }
        
        try:
            old_date = vld.vld_date
            updated_vld = self.vld_repo.defer_vld(vld_id, new_date, reason)
            
            days_deferred = (new_date - old_date).days
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'deferral': {
                    'old_date': old_date.isoformat(),
                    'new_date': new_date.isoformat(),
                    'days_deferred': days_deferred,
                    'reason': reason,
                    'total_deferrals': updated_vld.deferral_count
                },
                'message': f'VLD deferred by {days_deferred} days'
            }
            
        except ValueError as e:
            raise e
    
    def reassign_vld(self, vld_id: int, new_partner_id: int, reason: str) -> Dict[str, Any]:
        """Reassign VLD to a different partner."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status in [VLDStatus.COMPLETED, VLDStatus.CANCELLED]:
            raise ValueError("Cannot reassign completed or cancelled VLD")
        
        new_partner = self.partner_repo.get_by_id(new_partner_id)
        if not new_partner:
            raise ValueError(f"Partner {new_partner_id} not found")
        
        if vld.current_partner_id == new_partner_id:
            raise ValueError("VLD is already assigned to this partner")
        
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Detailed reason is required for reassignment")
        
        # Check for conflicts with new partner
        conflicts = self._check_vld_conflicts(vld.production_id, new_partner_id, vld.vld_date)
        if conflicts:
            return {
                'success': False,
                'message': f'Conflict detected for new partner: {conflicts}',
                'conflicts': conflicts
            }
        
        try:
            old_partner_id = vld.current_partner_id
            updated_vld = self.vld_repo.reassign_vld(vld_id, new_partner_id, reason)
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'reassignment': {
                    'old_partner_id': old_partner_id,
                    'new_partner_id': new_partner_id,
                    'new_partner_name': new_partner.name,
                    'reason': reason,
                    'total_reassignments': updated_vld.reassignment_count
                },
                'message': f'VLD reassigned to {new_partner.name}'
            }
            
        except ValueError as e:
            raise e
    
    def cancel_vld(self, vld_id: int, reason: str) -> Dict[str, Any]:
        """Cancel a VLD."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status == VLDStatus.CANCELLED:
            raise ValueError("VLD is already cancelled")
        
        if vld.status == VLDStatus.COMPLETED:
            raise ValueError("Cannot cancel completed VLD")
        
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Detailed reason is required for cancellation")
        
        try:
            updated_vld = self.vld_repo.cancel_vld(vld_id, reason)
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'cancellation': {
                    'reason': reason,
                    'cancelled_at': updated_vld.cancelled_date.isoformat() if updated_vld.cancelled_date else None,
                    'previous_status': updated_vld.status_before_cancellation.value if updated_vld.status_before_cancellation else None
                },
                'message': f'VLD {vld_id} cancelled'
            }
            
        except ValueError as e:
            raise e
    
    def restore_cancelled_vld(self, vld_id: int, reason: str) -> Dict[str, Any]:
        """Restore a cancelled VLD."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status != VLDStatus.CANCELLED:
            raise ValueError("VLD is not cancelled")
        
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Detailed reason is required for restoration")
        
        # Check for conflicts when restoring
        conflicts = self._check_vld_conflicts(vld.production_id, vld.current_partner_id, vld.vld_date)
        if conflicts:
            return {
                'success': False,
                'message': f'Cannot restore VLD due to conflicts: {conflicts}',
                'conflicts': conflicts
            }
        
        try:
            updated_vld = self.vld_repo.uncancel_vld(vld_id, reason)
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'restoration': {
                    'reason': reason,
                    'restored_at': updated_vld.uncancelled_date.isoformat() if updated_vld.uncancelled_date else None,
                    'restored_status': updated_vld.status.value
                },
                'message': f'VLD {vld_id} restored'
            }
            
        except ValueError as e:
            raise e
    
    def complete_vld_loading(self, vld_id: int, actual_tonnage: int,
                            moisture_content: Optional[float] = None,
                            loader_number: Optional[str] = None) -> Dict[str, Any]:
        """Complete VLD loading with actual results."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status != VLDStatus.LOADING:
            raise ValueError("VLD must be in loading status to complete")
        
        if actual_tonnage <= 0:
            raise ValueError("Actual tonnage must be positive")
        
        if moisture_content is not None and not (0 <= moisture_content <= 100):
            raise ValueError("Moisture content must be between 0 and 100")
        
        try:
            updated_vld = self.vld_repo.update_status(
                vld_id, VLDStatus.COMPLETED,
                actual_tonnage=actual_tonnage,
                moisture_content=Decimal(str(moisture_content)) if moisture_content else None,
                loader_number=loader_number
            )
            
            # Calculate performance metrics
            variance = actual_tonnage - vld.planned_tonnage
            variance_pct = (variance / vld.planned_tonnage * 100) if vld.planned_tonnage > 0 else 0
            
            return {
                'success': True,
                'vld': updated_vld.to_dict(),
                'completion': {
                    'actual_tonnage': actual_tonnage,
                    'planned_tonnage': vld.planned_tonnage,
                    'variance': variance,
                    'variance_percentage': round(variance_pct, 2),
                    'moisture_content': float(moisture_content) if moisture_content else None,
                    'loader_number': loader_number,
                    'completion_time': updated_vld.loading_completion_time.isoformat() if updated_vld.loading_completion_time else None
                },
                'message': f'VLD {vld_id} completed with {actual_tonnage}t'
            }
            
        except ValueError as e:
            raise e
    
    def get_vld_schedule_optimization(self, production_id: int,
                                     start_date: Optional[date] = None,
                                     end_date: Optional[date] = None) -> Dict[str, Any]:
        """Optimize VLD schedule for better efficiency."""
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=90)
        
        vlds = self.vld_repo.get_by_date_range(start_date, end_date, production_id)
        active_vlds = [v for v in vlds if v.status not in [VLDStatus.COMPLETED, VLDStatus.CANCELLED]]
        
        # Analyze current schedule
        issues = []
        optimizations = []
        
        # Check for clustering (too many VLDs on same date)
        date_counts = {}
        for vld in active_vlds:
            date_str = vld.vld_date.isoformat()
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
        
        for date_str, count in date_counts.items():
            if count > 2:  # More than 2 VLDs per day
                issues.append({
                    'type': 'clustering',
                    'date': date_str,
                    'vld_count': count,
                    'severity': 'high' if count > 3 else 'medium'
                })
                
                optimizations.append({
                    'type': 'redistribute',
                    'description': f'Redistribute {count} VLDs from {date_str}',
                    'impact': 'Reduce port congestion and improve efficiency'
                })
        
        # Check for gaps (long periods without VLDs)
        sorted_dates = sorted([v.vld_date for v in active_vlds])
        for i in range(len(sorted_dates) - 1):
            gap_days = (sorted_dates[i + 1] - sorted_dates[i]).days
            if gap_days > 7:
                issues.append({
                    'type': 'gap',
                    'start_date': sorted_dates[i].isoformat(),
                    'end_date': sorted_dates[i + 1].isoformat(),
                    'gap_days': gap_days,
                    'severity': 'medium'
                })
                
                optimizations.append({
                    'type': 'fill_gap',
                    'description': f'Consider filling {gap_days}-day gap',
                    'impact': 'Better resource utilization'
                })
        
        # Partner distribution analysis
        partner_counts = {}
        for vld in active_vlds:
            partner_counts[vld.current_partner_id] = partner_counts.get(vld.current_partner_id, 0) + 1
        
        # Calculate efficiency score
        efficiency_score = self._calculate_schedule_efficiency(active_vlds, issues)
        
        return {
            'success': True,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'analysis': {
                'total_vlds': len(active_vlds),
                'issues_found': len(issues),
                'efficiency_score': efficiency_score,
                'partner_distribution': partner_counts
            },
            'issues': issues,
            'optimizations': optimizations,
            'recommendations': self._generate_schedule_recommendations(active_vlds, issues)
        }
    
    def get_monthly_vld_calendar(self, year: int, month: int,
                                production_id: Optional[int] = None) -> Dict[str, Any]:
        """Get VLD calendar for a specific month."""
        calendar_data = self.vld_repo.get_monthly_vld_schedule(year, month, production_id)
        
        # Enhance with additional insights
        vlds = []
        for date_str, date_vlds in calendar_data['schedule'].items():
            vlds.extend(date_vlds)
        
        # Add capacity analysis
        daily_capacity = {}
        for date_str, date_vlds in calendar_data['schedule'].items():
            total_tonnage = sum(v['planned_tonnage'] for v in date_vlds)
            daily_capacity[date_str] = {
                'vld_count': len(date_vlds),
                'total_tonnage': total_tonnage,
                'capacity_utilization': min(100, (total_tonnage / 200000) * 100)  # Assuming 200k daily capacity
            }
        
        calendar_data['daily_capacity'] = daily_capacity
        calendar_data['insights'] = {
            'peak_day': max(daily_capacity.items(), key=lambda x: x[1]['total_tonnage'])[0] if daily_capacity else None,
            'busiest_day': max(daily_capacity.items(), key=lambda x: x[1]['vld_count'])[0] if daily_capacity else None,
            'average_daily_tonnage': sum(d['total_tonnage'] for d in daily_capacity.values()) / len(daily_capacity) if daily_capacity else 0
        }
        
        return calendar_data
    
    def _generate_vlds_for_period(self, production_id: int, partner_id: int,
                                 total_tonnage: int, vessel_size: int,
                                 start_date: date, end_date: date) -> List[VLD]:
        """Generate VLDs for a partner allocation period."""
        # Standard VLD size (58-60k tons)
        standard_vld_size = 59000
        
        # Calculate number of VLDs needed
        vld_count = max(1, round(total_tonnage / standard_vld_size))
        tonnage_per_vld = total_tonnage // vld_count
        
        # Distribute VLDs evenly across the period
        period_days = (end_date - start_date).days
        interval_days = max(1, period_days // vld_count)
        
        created_vlds = []
        current_date = start_date
        
        for i in range(vld_count):
            # Last VLD gets remaining tonnage
            vld_tonnage = tonnage_per_vld
            if i == vld_count - 1:
                vld_tonnage = total_tonnage - (tonnage_per_vld * (vld_count - 1))
            
            # Check for conflicts
            conflicts = self._check_vld_conflicts(production_id, partner_id, current_date)
            if conflicts:
                # Try next day
                current_date += timedelta(days=1)
            
            vld = self.vld_repo.create_vld(
                production_id=production_id,
                partner_id=partner_id,
                vld_date=current_date,
                planned_tonnage=vld_tonnage,
                vessel_size_t=vessel_size
            )
            
            created_vlds.append(vld)
            current_date += timedelta(days=interval_days)
            
            # Don't exceed end date
            if current_date > end_date:
                break
        
        return created_vlds
    
    def _check_vld_conflicts(self, production_id: int, partner_id: int, vld_date: date) -> List[str]:
        """Check for VLD conflicts on a specific date."""
        conflicts = []
        
        # Check for existing VLDs on the same date for the same partner
        existing_vlds = self.vld_repo.get_by_date_range(vld_date, vld_date, production_id)
        partner_vlds = [v for v in existing_vlds if v.current_partner_id == partner_id]
        
        if partner_vlds:
            conflicts.append(f"Partner already has VLD on {vld_date}")
        
        # Check for capacity constraints (max 3 VLDs per day)
        if len(existing_vlds) >= 3:
            conflicts.append(f"Daily capacity exceeded on {vld_date}")
        
        return conflicts
    
    def _calculate_schedule_efficiency(self, vlds: List[VLD], issues: List[Dict[str, Any]]) -> float:
        """Calculate schedule efficiency score (0-100)."""
        if not vlds:
            return 0
        
        base_score = 100
        
        # Deduct points for issues
        for issue in issues:
            if issue['severity'] == 'high':
                base_score -= 20
            elif issue['severity'] == 'medium':
                base_score -= 10
            else:
                base_score -= 5
        
        # Bonus for good distribution
        if len(vlds) > 0:
            # Check date distribution
            dates = [v.vld_date for v in vlds]
            date_range = (max(dates) - min(dates)).days
            if date_range > 0:
                avg_interval = date_range / len(vlds)
                if 3 <= avg_interval <= 7:  # Good spacing
                    base_score += 10
        
        return max(0, min(100, base_score))
    
    def _generate_schedule_recommendations(self, vlds: List[VLD], issues: List[Dict[str, Any]]) -> List[str]:
        """Generate schedule optimization recommendations."""
        recommendations = []
        
        if not vlds:
            return ['No active VLDs to optimize']
        
        # Based on issues found
        clustering_issues = [i for i in issues if i['type'] == 'clustering']
        gap_issues = [i for i in issues if i['type'] == 'gap']
        
        if clustering_issues:
            recommendations.append('Consider redistributing clustered VLDs to reduce port congestion')
        
        if gap_issues:
            recommendations.append('Fill scheduling gaps to improve resource utilization')
        
        # General recommendations
        if len(vlds) > 20:
            recommendations.append('Consider implementing automated scheduling optimization')
        
        recommendations.append('Regular schedule reviews recommended every 2 weeks')
        
        return recommendations

