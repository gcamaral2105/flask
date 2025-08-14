"""
Lineup Service
=============

Business logic service for Lineup management with CBG-specific operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError

from app.repository.lineup_repository import LineupRepository
from app.repository.vld_repository import VLDRepository
from app.repository.partner_repository import PartnerRepository
from app.repository.vessel_repository import VesselRepository
from app.models.lineup import Lineup, LineupStatus
from app.models.vld import VLD, VLDStatus
from app.models.partner import Partner
from app.models.vessel import Vessel


class LineupService:
    """Service for Lineup business logic."""
    
    def __init__(self):
        self.lineup_repo = LineupRepository()
        self.vld_repo = VLDRepository()
        self.partner_repo = PartnerRepository()
        self.vessel_repo = VesselRepository()
    
    def get_current_lineup(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get current lineup with enhanced information."""
        lineups = self.lineup_repo.get_current_lineup(limit)
        
        result = []
        for lineup in lineups:
            lineup_data = lineup.to_dict(
                expand=['partner', 'product', 'berth', 'vld'],
                with_metrics=True
            )
            
            # Add business-specific enhancements
            lineup_data['priority_score'] = self._calculate_priority_score(lineup)
            lineup_data['delay_risk'] = self._assess_delay_risk(lineup)
            lineup_data['berth_readiness'] = self._check_berth_readiness(lineup)
            
            result.append(lineup_data)
        
        return result
    
    def create_lineup_from_vld(self, vld_id: int, berth_id: int,
                              eta: Optional[datetime] = None,
                              vessel_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a lineup entry from a VLD."""
        vld = self.vld_repo.get_by_id(vld_id)
        if not vld:
            raise ValueError(f"VLD {vld_id} not found")
        
        if vld.status not in [VLDStatus.NARROWED, VLDStatus.NOMINATED]:
            raise ValueError(f"VLD must be narrowed or nominated to create lineup")
        
        # Validate berth availability
        conflicts = self._check_berth_conflicts(berth_id, eta)
        if conflicts:
            raise ValueError(f"Berth conflict detected: {conflicts}")
        
        # Create lineup
        lineup_data = {
            'vessel_name': vld.vessel_name or 'TBN',
            'vld_id': vld_id,
            'partner_id': vld.current_partner_id,
            'product_id': 1,  # Default product - should be configurable
            'berth_id': berth_id,
            'vessel_id': vessel_id,
            'eta': eta,
            'planned_tonnage': vld.planned_tonnage,
            'status': LineupStatus.SCHEDULED
        }
        
        try:
            lineup = Lineup(**lineup_data)
            lineup = self.lineup_repo.create(lineup)
            
            # Update VLD status if needed
            if vld.status == VLDStatus.NARROWED:
                self.vld_repo.update_status(vld_id, VLDStatus.NOMINATED, vessel_name=lineup.vessel_name)
            
            return {
                'success': True,
                'lineup': lineup.to_dict(expand=['partner', 'vld'], with_metrics=True),
                'message': f'Lineup created for {lineup.vessel_name}'
            }
            
        except IntegrityError as e:
            raise ValueError(f"Failed to create lineup: {str(e)}")
    
    def update_vessel_arrival(self, lineup_id: int, ata: datetime,
                             vessel_name: Optional[str] = None) -> Dict[str, Any]:
        """Update vessel arrival information."""
        lineup = self.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            raise ValueError(f"Lineup {lineup_id} not found")
        
        # Update vessel name if provided
        if vessel_name and vessel_name != lineup.vessel_name:
            lineup.vessel_name = vessel_name
            
            # Update associated VLD
            if lineup.vld:
                self.vld_repo.update_status(lineup.vld_id, lineup.vld.status, vessel_name=vessel_name)
        
        # Update arrival time and status
        lineup.ata = ata
        lineup.status = LineupStatus.ARRIVED
        
        lineup = self.lineup_repo.update(lineup)
        
        # Calculate delay metrics
        delay_hours = None
        if lineup.eta:
            delay_hours = (ata - lineup.eta).total_seconds() / 3600
        
        return {
            'success': True,
            'lineup': lineup.to_dict(with_metrics=True),
            'delay_hours': round(delay_hours, 2) if delay_hours else None,
            'message': f'{lineup.vessel_name} arrived'
        }
    
    def tender_nor(self, lineup_id: int, nor_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Tender Notice of Readiness."""
        lineup = self.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            raise ValueError(f"Lineup {lineup_id} not found")
        
        if lineup.status != LineupStatus.ARRIVED:
            raise ValueError("Vessel must be arrived to tender NOR")
        
        lineup.nor_time = nor_time or datetime.utcnow()
        lineup.status = LineupStatus.NOR_TENDERED
        
        lineup = self.lineup_repo.update(lineup)
        
        # Calculate waiting time
        waiting_hours = None
        if lineup.ata:
            waiting_hours = (lineup.nor_time - lineup.ata).total_seconds() / 3600
        
        return {
            'success': True,
            'lineup': lineup.to_dict(with_metrics=True),
            'waiting_hours': round(waiting_hours, 2) if waiting_hours else None,
            'message': f'NOR tendered for {lineup.vessel_name}'
        }
    
    def berth_vessel(self, lineup_id: int, atb: Optional[datetime] = None,
                    etb: Optional[datetime] = None) -> Dict[str, Any]:
        """Berth a vessel."""
        lineup = self.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            raise ValueError(f"Lineup {lineup_id} not found")
        
        if lineup.status not in [LineupStatus.NOR_TENDERED, LineupStatus.ARRIVED]:
            raise ValueError("Vessel must have tendered NOR to berth")
        
        # Check berth availability
        if not self._is_berth_available(lineup.berth_id, atb or datetime.utcnow()):
            raise ValueError("Berth is not available")
        
        lineup.atb = atb or datetime.utcnow()
        if etb:
            lineup.etb = etb
        lineup.status = LineupStatus.BERTHED
        
        lineup = self.lineup_repo.update(lineup)
        
        return {
            'success': True,
            'lineup': lineup.to_dict(with_metrics=True),
            'message': f'{lineup.vessel_name} berthed'
        }
    
    def start_loading(self, lineup_id: int, loading_start: Optional[datetime] = None) -> Dict[str, Any]:
        """Start loading operations."""
        lineup = self.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            raise ValueError(f"Lineup {lineup_id} not found")
        
        if lineup.status != LineupStatus.BERTHED:
            raise ValueError("Vessel must be berthed to start loading")
        
        lineup.loading_start = loading_start or datetime.utcnow()
        lineup.status = LineupStatus.LOADING
        
        # Update associated VLD
        if lineup.vld and lineup.vld.status != VLDStatus.LOADING:
            self.vld_repo.update_status(lineup.vld_id, VLDStatus.LOADING)
        
        lineup = self.lineup_repo.update(lineup)
        
        return {
            'success': True,
            'lineup': lineup.to_dict(with_metrics=True),
            'message': f'Loading started for {lineup.vessel_name}'
        }
    
    def complete_loading(self, lineup_id: int, actual_tonnage: int,
                        loading_completion: Optional[datetime] = None,
                        moisture_content: Optional[float] = None) -> Dict[str, Any]:
        """Complete loading operations."""
        lineup = self.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            raise ValueError(f"Lineup {lineup_id} not found")
        
        if lineup.status != LineupStatus.LOADING:
            raise ValueError("Vessel must be loading to complete")
        
        if actual_tonnage <= 0:
            raise ValueError("Actual tonnage must be positive")
        
        lineup.loading_completion = loading_completion or datetime.utcnow()
        lineup.actual_tonnage = actual_tonnage
        lineup.status = LineupStatus.COMPLETED
        
        # Update associated VLD
        if lineup.vld:
            self.vld_repo.update_status(
                lineup.vld_id, 
                VLDStatus.COMPLETED,
                actual_tonnage=actual_tonnage,
                moisture_content=moisture_content
            )
        
        lineup = self.lineup_repo.update(lineup)
        
        # Calculate performance metrics
        metrics = self._calculate_loading_metrics(lineup)
        
        return {
            'success': True,
            'lineup': lineup.to_dict(with_metrics=True),
            'performance_metrics': metrics,
            'message': f'Loading completed for {lineup.vessel_name}'
        }
    
    def vessel_departure(self, lineup_id: int, ats: Optional[datetime] = None) -> Dict[str, Any]:
        """Record vessel departure."""
        lineup = self.lineup_repo.get_by_id(lineup_id)
        if not lineup:
            raise ValueError(f"Lineup {lineup_id} not found")
        
        if lineup.status != LineupStatus.COMPLETED:
            raise ValueError("Loading must be completed before departure")
        
        lineup.ats = ats or datetime.utcnow()
        lineup.status = LineupStatus.DEPARTED
        
        lineup = self.lineup_repo.update(lineup)
        
        # Calculate total port stay
        port_stay_hours = None
        if lineup.ata:
            port_stay_hours = (lineup.ats - lineup.ata).total_seconds() / 3600
        
        return {
            'success': True,
            'lineup': lineup.to_dict(with_metrics=True),
            'port_stay_hours': round(port_stay_hours, 2) if port_stay_hours else None,
            'message': f'{lineup.vessel_name} departed'
        }
    
    def optimize_lineup_sequence(self, berth_id: Optional[int] = None) -> Dict[str, Any]:
        """Optimize lineup sequence based on priorities and constraints."""
        if berth_id:
            lineups = self.lineup_repo.get_by_berth(berth_id)
        else:
            lineups = self.lineup_repo.get_current_lineup()
        
        # Filter active lineups
        active_lineups = [
            l for l in lineups 
            if l.status in [LineupStatus.SCHEDULED, LineupStatus.ETA_RECEIVED, LineupStatus.ARRIVED]
        ]
        
        # Calculate optimization scores
        optimized_sequence = []
        for lineup in active_lineups:
            score = self._calculate_optimization_score(lineup)
            optimized_sequence.append({
                'lineup_id': lineup.id,
                'vessel_name': lineup.vessel_name,
                'partner': lineup.partner.name if lineup.partner else None,
                'eta': lineup.eta.isoformat() if lineup.eta else None,
                'priority_score': score,
                'current_position': len(optimized_sequence) + 1
            })
        
        # Sort by optimization score (higher is better)
        optimized_sequence.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # Add recommended position
        for i, item in enumerate(optimized_sequence):
            item['recommended_position'] = i + 1
            item['position_change'] = item['current_position'] - item['recommended_position']
        
        return {
            'success': True,
            'optimized_sequence': optimized_sequence,
            'total_vessels': len(optimized_sequence),
            'optimization_criteria': [
                'VLD urgency',
                'Partner priority',
                'Vessel size efficiency',
                'Delay risk assessment'
            ]
        }
    
    def get_lineup_conflicts(self) -> Dict[str, Any]:
        """Identify and analyze lineup conflicts."""
        conflicts = self.lineup_repo.get_lineup_conflicts()
        
        # Enhance conflicts with resolution suggestions
        enhanced_conflicts = []
        for conflict in conflicts:
            suggestions = self._generate_conflict_resolution(conflict)
            conflict['resolution_suggestions'] = suggestions
            enhanced_conflicts.append(conflict)
        
        return {
            'success': True,
            'conflicts': enhanced_conflicts,
            'total_conflicts': len(enhanced_conflicts),
            'severity_levels': self._categorize_conflicts(enhanced_conflicts)
        }
    
    def get_berth_utilization_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate comprehensive berth utilization report."""
        # Get all berths (this would need to be implemented)
        berth_reports = []
        
        # For now, analyze berths from existing lineups
        lineups = self.lineup_repo.get_by_date_range(start_date, end_date)
        berth_ids = list(set(l.berth_id for l in lineups))
        
        for berth_id in berth_ids:
            utilization = self.lineup_repo.get_berth_utilization(berth_id, start_date, end_date)
            
            # Add efficiency metrics
            berth_lineups = [l for l in lineups if l.berth_id == berth_id]
            efficiency_metrics = self._calculate_berth_efficiency(berth_lineups)
            
            utilization.update(efficiency_metrics)
            berth_reports.append(utilization)
        
        # Sort by utilization percentage
        berth_reports.sort(key=lambda x: x['utilization_percentage'], reverse=True)
        
        return {
            'success': True,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'berth_reports': berth_reports,
            'fleet_summary': {
                'total_berths': len(berth_reports),
                'average_utilization': sum(b['utilization_percentage'] for b in berth_reports) / len(berth_reports) if berth_reports else 0,
                'total_vessels_served': sum(b['vessels_served'] for b in berth_reports)
            }
        }
    
    def _calculate_priority_score(self, lineup: Lineup) -> float:
        """Calculate priority score for lineup optimization."""
        score = 0.0
        
        # VLD urgency (higher score for closer to VLD date)
        if lineup.vld and lineup.vld.vld_date:
            days_to_vld = (lineup.vld.vld_date - date.today()).days
            if days_to_vld <= 0:
                score += 100  # Overdue VLD
            elif days_to_vld <= 3:
                score += 50   # Very urgent
            elif days_to_vld <= 7:
                score += 25   # Urgent
        
        # Partner priority (could be based on contract terms)
        if lineup.partner:
            # This would be based on partner priority levels
            score += 10
        
        # Vessel size efficiency (larger vessels get priority)
        if lineup.planned_tonnage:
            score += min(lineup.planned_tonnage / 1000, 50)  # Max 50 points
        
        # ETA adherence (vessels arriving on time get priority)
        if lineup.eta and lineup.ata:
            delay_hours = (lineup.ata - lineup.eta).total_seconds() / 3600
            if delay_hours <= 0:
                score += 20  # Early arrival
            elif delay_hours <= 6:
                score += 10  # On time
        
        return round(score, 2)
    
    def _assess_delay_risk(self, lineup: Lineup) -> str:
        """Assess delay risk for a lineup."""
        if not lineup.eta:
            return 'unknown'
        
        now = datetime.utcnow()
        
        # Already delayed
        if lineup.eta < now and not lineup.ata:
            return 'high'
        
        # Close to ETA without arrival
        hours_to_eta = (lineup.eta - now).total_seconds() / 3600
        if 0 <= hours_to_eta <= 6:
            return 'medium'
        
        return 'low'
    
    def _check_berth_readiness(self, lineup: Lineup) -> Dict[str, Any]:
        """Check berth readiness for a lineup."""
        # This would check berth status, equipment availability, etc.
        return {
            'ready': True,
            'issues': [],
            'estimated_ready_time': None
        }
    
    def _check_berth_conflicts(self, berth_id: int, eta: Optional[datetime]) -> List[str]:
        """Check for berth conflicts."""
        if not eta:
            return []
        
        # Check for overlapping lineups
        conflicts = []
        window_start = eta - timedelta(hours=12)
        window_end = eta + timedelta(hours=24)
        
        overlapping = self.lineup_repo.get_by_berth(
            berth_id, 
            window_start.date(), 
            window_end.date()
        )
        
        for lineup in overlapping:
            if lineup.etb and lineup.ets:
                if not (lineup.ets <= eta or lineup.etb >= eta + timedelta(hours=24)):
                    conflicts.append(f"Overlap with {lineup.vessel_name}")
        
        return conflicts
    
    def _is_berth_available(self, berth_id: int, time: datetime) -> bool:
        """Check if berth is available at a specific time."""
        # Check for active lineups at the berth
        active_lineups = self.lineup_repo.get_by_berth(berth_id, time.date(), time.date())
        
        for lineup in active_lineups:
            if (lineup.atb and not lineup.ats and 
                lineup.status in [LineupStatus.BERTHED, LineupStatus.LOADING]):
                return False
        
        return True
    
    def _calculate_loading_metrics(self, lineup: Lineup) -> Dict[str, Any]:
        """Calculate loading performance metrics."""
        metrics = {}
        
        if lineup.loading_start and lineup.loading_completion:
            loading_hours = (lineup.loading_completion - lineup.loading_start).total_seconds() / 3600
            metrics['loading_hours'] = round(loading_hours, 2)
            
            if lineup.actual_tonnage:
                metrics['loading_rate_tph'] = round(lineup.actual_tonnage / loading_hours, 1)
        
        if lineup.planned_tonnage and lineup.actual_tonnage:
            metrics['tonnage_variance'] = lineup.actual_tonnage - lineup.planned_tonnage
            metrics['tonnage_variance_pct'] = round(
                (lineup.actual_tonnage - lineup.planned_tonnage) / lineup.planned_tonnage * 100, 2
            )
        
        return metrics
    
    def _calculate_optimization_score(self, lineup: Lineup) -> float:
        """Calculate optimization score for lineup sequencing."""
        return self._calculate_priority_score(lineup)
    
    def _generate_conflict_resolution(self, conflict: Dict[str, Any]) -> List[str]:
        """Generate resolution suggestions for conflicts."""
        suggestions = []
        
        if conflict['conflict_type'] == 'overlap':
            suggestions.extend([
                f"Defer {conflict['second_lineup']['vessel_name']} by {conflict['overlap_hours']:.1f} hours",
                f"Expedite {conflict['first_lineup']['vessel_name']} loading operations",
                "Consider alternative berth assignment"
            ])
        
        return suggestions
    
    def _categorize_conflicts(self, conflicts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize conflicts by severity."""
        severity = {'high': 0, 'medium': 0, 'low': 0}
        
        for conflict in conflicts:
            overlap_hours = conflict.get('overlap_hours', 0)
            if overlap_hours > 12:
                severity['high'] += 1
            elif overlap_hours > 6:
                severity['medium'] += 1
            else:
                severity['low'] += 1
        
        return severity
    
    def _calculate_berth_efficiency(self, lineups: List[Lineup]) -> Dict[str, Any]:
        """Calculate berth efficiency metrics."""
        if not lineups:
            return {'efficiency_score': 0, 'average_loading_rate': 0}
        
        completed_lineups = [l for l in lineups if l.status == LineupStatus.COMPLETED]
        
        if not completed_lineups:
            return {'efficiency_score': 0, 'average_loading_rate': 0}
        
        # Calculate average loading rate
        loading_rates = []
        for lineup in completed_lineups:
            if (lineup.loading_start and lineup.loading_completion and 
                lineup.actual_tonnage):
                hours = (lineup.loading_completion - lineup.loading_start).total_seconds() / 3600
                if hours > 0:
                    loading_rates.append(lineup.actual_tonnage / hours)
        
        avg_loading_rate = sum(loading_rates) / len(loading_rates) if loading_rates else 0
        
        # Calculate efficiency score (0-100)
        efficiency_score = min(avg_loading_rate / 1000 * 100, 100)  # Assuming 1000 tph is 100% efficient
        
        return {
            'efficiency_score': round(efficiency_score, 2),
            'average_loading_rate': round(avg_loading_rate, 1),
            'completed_operations': len(completed_lineups)
        }

