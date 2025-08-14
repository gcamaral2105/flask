"""
Shuttle Service
==============

Business logic service for Shuttle and transloader operations management.
Handles ship-to-ship operations between CBG and Capesize vessels.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError

from app.repository.shuttle_repository import ShuttleRepository, ShuttleOperationRepository
from app.repository.capesize_repository import CapesizeRepository
from app.repository.lineup_repository import LineupRepository
from app.repository.vld_repository import VLDRepository
from app.models.shuttle import Shuttle, ShuttleStatus, ShuttleOperation, ShuttleOperationStatus
from app.models.capesize import CapesizeVessel, CapesizeStatus
from app.models.lineup import Lineup, LineupStatus


class ShuttleService:
    """Service for Shuttle business logic."""
    
    def __init__(self):
        self.shuttle_repo = ShuttleRepository()
        self.operation_repo = ShuttleOperationRepository()
        self.capesize_repo = CapesizeRepository()
        self.lineup_repo = LineupRepository()
        self.vld_repo = VLDRepository()
    
    def get_fleet_status(self) -> Dict[str, Any]:
        """Get comprehensive shuttle fleet status."""
        shuttles = self.shuttle_repo.get_active_shuttles()
        active_operations = self.operation_repo.get_active_operations()
        
        fleet_status = []
        for shuttle in shuttles:
            # Find current operation
            current_op = next(
                (op for op in active_operations if op.shuttle_id == shuttle.id),
                None
            )
            
            status_info = {
                'shuttle_id': shuttle.id,
                'vessel_name': shuttle.vessel.name if shuttle.vessel else None,
                'status': shuttle.status.value,
                'current_operation': None,
                'availability': 'available'
            }
            
            if current_op:
                status_info['current_operation'] = {
                    'operation_id': current_op.id,
                    'cape_vessel_name': current_op.cape_vessel_name,
                    'status': self._determine_operation_status(current_op),
                    'progress': self._calculate_operation_progress(current_op),
                    'estimated_completion': self._estimate_operation_completion(current_op)
                }
                status_info['availability'] = 'busy'
            
            fleet_status.append(status_info)
        
        # Fleet summary
        total_shuttles = len(shuttles)
        busy_shuttles = len([s for s in fleet_status if s['availability'] == 'busy'])
        
        return {
            'success': True,
            'fleet_status': fleet_status,
            'summary': {
                'total_shuttles': total_shuttles,
                'available_shuttles': total_shuttles - busy_shuttles,
                'busy_shuttles': busy_shuttles,
                'utilization_rate': (busy_shuttles / total_shuttles * 100) if total_shuttles > 0 else 0
            }
        }
    
    def plan_capesize_loading(self, capesize_id: int) -> Dict[str, Any]:
        """Plan shuttle operations for a capesize vessel loading."""
        capesize = self.capesize_repo.get_by_id(capesize_id)
        if not capesize:
            raise ValueError(f"Capesize vessel {capesize_id} not found")
        
        if capesize.status not in [CapesizeStatus.SCHEDULED, CapesizeStatus.ARRIVED]:
            raise ValueError("Capesize vessel must be scheduled or arrived for planning")
        
        remaining_tonnage = capesize.target_tonnage - capesize.current_tonnage
        if remaining_tonnage <= 0:
            return {
                'success': True,
                'message': 'Capesize vessel already completed',
                'plan': []
            }
        
        # Calculate shuttle requirements
        avg_shuttle_capacity = 15000  # Typical shuttle capacity
        shuttles_needed = max(1, round(remaining_tonnage / avg_shuttle_capacity))
        
        # Find available shuttles
        available_shuttles = self.shuttle_repo.get_available_shuttles()
        
        if len(available_shuttles) < shuttles_needed:
            return {
                'success': False,
                'message': f'Insufficient shuttles available. Need {shuttles_needed}, have {len(available_shuttles)}',
                'plan': []
            }
        
        # Create loading plan
        loading_plan = []
        tonnage_per_shuttle = remaining_tonnage // shuttles_needed
        
        for i in range(shuttles_needed):
            shuttle = available_shuttles[i]
            planned_tonnage = tonnage_per_shuttle
            
            # Last shuttle takes remaining tonnage
            if i == shuttles_needed - 1:
                planned_tonnage = remaining_tonnage - (tonnage_per_shuttle * (shuttles_needed - 1))
            
            # Estimate timing
            start_time = datetime.utcnow() + timedelta(hours=i * 6)  # 6-hour intervals
            
            plan_item = {
                'sequence': i + 1,
                'shuttle_id': shuttle.id,
                'shuttle_name': shuttle.vessel.name if shuttle.vessel else None,
                'planned_tonnage': planned_tonnage,
                'estimated_start': start_time.isoformat(),
                'estimated_duration_hours': 24,  # Typical cycle time
                'estimated_completion': (start_time + timedelta(hours=24)).isoformat()
            }
            
            loading_plan.append(plan_item)
        
        return {
            'success': True,
            'capesize_vessel': {
                'id': capesize.id,
                'name': capesize.cape_vessel.name if capesize.cape_vessel else 'TBN',
                'target_tonnage': capesize.target_tonnage,
                'current_tonnage': capesize.current_tonnage,
                'remaining_tonnage': remaining_tonnage
            },
            'plan': loading_plan,
            'summary': {
                'shuttles_required': shuttles_needed,
                'total_planned_tonnage': remaining_tonnage,
                'estimated_total_duration_hours': shuttles_needed * 24,
                'estimated_completion': loading_plan[-1]['estimated_completion'] if loading_plan else None
            }
        }
    
    def create_shuttle_operation(self, shuttle_id: int, cape_vessel_name: str,
                                loading_lineup_id: Optional[int] = None,
                                cape_operation_id: Optional[int] = None,
                                planned_volume: Optional[int] = None) -> Dict[str, Any]:
        """Create a new shuttle operation."""
        shuttle = self.shuttle_repo.get_by_id(shuttle_id)
        if not shuttle:
            raise ValueError(f"Shuttle {shuttle_id} not found")
        
        if shuttle.status != ShuttleStatus.ACTIVE:
            raise ValueError("Shuttle must be active to create operation")
        
        # Check shuttle availability
        available_shuttles = self.shuttle_repo.get_available_shuttles()
        if shuttle not in available_shuttles:
            raise ValueError("Shuttle is not available for new operation")
        
        # Validate lineup if provided
        if loading_lineup_id:
            lineup = self.lineup_repo.get_by_id(loading_lineup_id)
            if not lineup or lineup.status not in [LineupStatus.LOADING, LineupStatus.BERTHED]:
                raise ValueError("Invalid lineup for shuttle operation")
        
        try:
            operation = self.operation_repo.create_operation(
                shuttle_id=shuttle_id,
                cape_vessel_name=cape_vessel_name,
                loading_lineup_id=loading_lineup_id,
                cape_operation_id=cape_operation_id,
                volume=planned_volume
            )
            
            return {
                'success': True,
                'operation': {
                    'id': operation.id,
                    'shuttle_name': shuttle.vessel.name if shuttle.vessel else None,
                    'cape_vessel_name': cape_vessel_name,
                    'planned_volume': planned_volume,
                    'status': 'planned'
                },
                'message': f'Shuttle operation created for {cape_vessel_name}'
            }
            
        except IntegrityError as e:
            raise ValueError(f"Failed to create shuttle operation: {str(e)}")
    
    def start_loading_operation(self, operation_id: int) -> Dict[str, Any]:
        """Start shuttle loading at CBG."""
        operation = self.operation_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if operation.load_start_at:
            raise ValueError("Operation already started")
        
        # Validate lineup readiness
        if operation.loading_lineup_id:
            lineup = self.lineup_repo.get_by_id(operation.loading_lineup_id)
            if lineup and lineup.status != LineupStatus.LOADING:
                raise ValueError("Lineup must be in loading status")
        
        operation = self.operation_repo.start_loading(operation_id)
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'message': f'Loading started for shuttle operation {operation_id}'
        }
    
    def complete_loading_operation(self, operation_id: int, actual_volume: int) -> Dict[str, Any]:
        """Complete shuttle loading at CBG."""
        operation = self.operation_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if not operation.load_start_at:
            raise ValueError("Operation must be started before completion")
        
        if operation.load_end_at:
            raise ValueError("Operation already completed")
        
        if actual_volume <= 0:
            raise ValueError("Actual volume must be positive")
        
        operation = self.operation_repo.complete_loading(operation_id, actual_volume)
        
        # Calculate loading performance
        loading_hours = (operation.load_end_at - operation.load_start_at).total_seconds() / 3600
        loading_rate = actual_volume / loading_hours if loading_hours > 0 else 0
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'performance': {
                'loading_hours': round(loading_hours, 2),
                'loading_rate_tph': round(loading_rate, 1),
                'actual_volume': actual_volume
            },
            'message': f'Loading completed: {actual_volume}t in {loading_hours:.1f}h'
        }
    
    def start_transit(self, operation_id: int) -> Dict[str, Any]:
        """Start shuttle transit to anchorage."""
        operation = self.operation_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if not operation.load_end_at:
            raise ValueError("Loading must be completed before transit")
        
        if operation.sail_out_at:
            raise ValueError("Transit already started")
        
        operation = self.operation_repo.start_transit(operation_id)
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'message': f'Transit started for operation {operation_id}'
        }
    
    def start_discharge_operation(self, operation_id: int) -> Dict[str, Any]:
        """Start shuttle discharge to capesize vessel."""
        operation = self.operation_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if not operation.sail_out_at:
            raise ValueError("Transit must be completed before discharge")
        
        if operation.discharge_start_at:
            raise ValueError("Discharge already started")
        
        operation = self.operation_repo.start_discharge(operation_id)
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'message': f'Discharge started for operation {operation_id}'
        }
    
    def complete_discharge_operation(self, operation_id: int) -> Dict[str, Any]:
        """Complete shuttle discharge to capesize vessel."""
        operation = self.operation_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if not operation.discharge_start_at:
            raise ValueError("Discharge must be started before completion")
        
        if operation.discharge_end_at:
            raise ValueError("Discharge already completed")
        
        operation = self.operation_repo.complete_discharge(operation_id)
        
        # Update capesize vessel tonnage
        if operation.cape_operation_id and operation.volume:
            self.capesize_repo.add_tonnage(operation.cape_operation_id, operation.volume)
        
        # Calculate discharge performance
        discharge_hours = (operation.discharge_end_at - operation.discharge_start_at).total_seconds() / 3600
        discharge_rate = operation.volume / discharge_hours if discharge_hours > 0 and operation.volume else 0
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'performance': {
                'discharge_hours': round(discharge_hours, 2),
                'discharge_rate_tph': round(discharge_rate, 1)
            },
            'message': f'Discharge completed in {discharge_hours:.1f}h'
        }
    
    def complete_shuttle_cycle(self, operation_id: int) -> Dict[str, Any]:
        """Complete entire shuttle cycle (return to CBG)."""
        operation = self.operation_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if not operation.discharge_end_at:
            raise ValueError("Discharge must be completed before cycle completion")
        
        if operation.return_at:
            raise ValueError("Cycle already completed")
        
        operation = self.operation_repo.complete_operation(operation_id)
        
        # Calculate full cycle metrics
        cycle_metrics = self.operation_repo.get_operation_performance(operation_id)
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'cycle_metrics': cycle_metrics,
            'message': f'Shuttle cycle completed for operation {operation_id}'
        }
    
    def create_sublet_operation(self, shuttle_id: int, cape_vessel_name: str,
                               sublet_partner_id: int, sublet_vld_id: int,
                               planned_volume: Optional[int] = None) -> Dict[str, Any]:
        """Create a sublet shuttle operation."""
        shuttle = self.shuttle_repo.get_by_id(shuttle_id)
        if not shuttle:
            raise ValueError(f"Shuttle {shuttle_id} not found")
        
        # Validate VLD
        vld = self.vld_repo.get_by_id(sublet_vld_id)
        if not vld:
            raise ValueError(f"VLD {sublet_vld_id} not found")
        
        # Check if VLD can be sublet
        if vld.status not in [VLDStatus.PLANNED, VLDStatus.NARROWED]:
            raise ValueError("VLD must be planned or narrowed for subletting")
        
        try:
            operation = self.operation_repo.create_sublet_operation(
                shuttle_id=shuttle_id,
                cape_vessel_name=cape_vessel_name,
                sublet_partner_id=sublet_partner_id,
                sublet_vld_id=sublet_vld_id,
                volume=planned_volume
            )
            
            return {
                'success': True,
                'operation': {
                    'id': operation.id,
                    'shuttle_name': shuttle.vessel.name if shuttle.vessel else None,
                    'cape_vessel_name': cape_vessel_name,
                    'sublet_partner_id': sublet_partner_id,
                    'sublet_vld_id': sublet_vld_id,
                    'is_sublet': True,
                    'planned_volume': planned_volume
                },
                'message': f'Sublet operation created for {cape_vessel_name}'
            }
            
        except IntegrityError as e:
            raise ValueError(f"Failed to create sublet operation: {str(e)}")
    
    def get_shuttle_utilization_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate shuttle utilization report."""
        shuttles = self.shuttle_repo.get_active_shuttles()
        
        utilization_reports = []
        for shuttle in shuttles:
            utilization = self.operation_repo.get_shuttle_utilization(
                shuttle.id, start_date, end_date
            )
            
            # Add shuttle details
            utilization['shuttle_name'] = shuttle.vessel.name if shuttle.vessel else None
            utilization['target_rates'] = {
                'loading_tph': shuttle.target_loading_rate_tph,
                'discharge_tph': shuttle.target_discharge_rate_tph
            }
            
            utilization_reports.append(utilization)
        
        # Fleet summary
        total_operations = sum(r['total_operations'] for r in utilization_reports)
        avg_utilization = sum(r['utilization_percentage'] for r in utilization_reports) / len(utilization_reports) if utilization_reports else 0
        total_volume = sum(r['total_volume'] for r in utilization_reports)
        
        return {
            'success': True,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'shuttle_reports': utilization_reports,
            'fleet_summary': {
                'total_shuttles': len(shuttles),
                'total_operations': total_operations,
                'average_utilization': round(avg_utilization, 2),
                'total_volume_transported': total_volume
            }
        }
    
    def get_capesize_completion_analysis(self, cape_vessel_name: str) -> Dict[str, Any]:
        """Analyze shuttle operations for capesize completion."""
        analysis = self.operation_repo.get_capesize_completion_analysis(cape_vessel_name)
        
        if not analysis:
            return {
                'success': False,
                'message': f'No operations found for {cape_vessel_name}'
            }
        
        # Add efficiency analysis
        if analysis['loading_sessions'] > 0:
            efficiency_score = min(100, (3 / analysis['average_shuttles_per_session']) * 100)
            analysis['efficiency'] = {
                'score': round(efficiency_score, 1),
                'rating': self._get_efficiency_rating(efficiency_score),
                'benchmark': 'Typical: 3 shuttles per capesize vessel'
            }
        
        return {
            'success': True,
            'analysis': analysis
        }
    
    def optimize_shuttle_allocation(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize shuttle allocation based on requirements."""
        total_capacity = requirements.get('total_capacity', 0)
        time_window = requirements.get('time_window', '2025-Q1')
        
        available_shuttles = self.shuttle_repo.get_available_shuttles()
        
        if not available_shuttles:
            return {
                'success': False,
                'message': 'No shuttles available for allocation'
            }
        
        # Calculate optimal allocation
        avg_shuttle_capacity = 15000
        shuttles_needed = max(1, round(total_capacity / avg_shuttle_capacity))
        
        if len(available_shuttles) < shuttles_needed:
            return {
                'success': False,
                'message': f'Insufficient shuttles. Need {shuttles_needed}, have {len(available_shuttles)}',
                'allocation': []
            }
        
        # Create allocation plan
        allocation = []
        capacity_per_shuttle = total_capacity // shuttles_needed
        
        for i in range(shuttles_needed):
            shuttle = available_shuttles[i]
            allocated_capacity = capacity_per_shuttle
            
            # Last shuttle gets remaining capacity
            if i == shuttles_needed - 1:
                allocated_capacity = total_capacity - (capacity_per_shuttle * (shuttles_needed - 1))
            
            allocation.append({
                'shuttle_id': shuttle.id,
                'shuttle_name': shuttle.vessel.name if shuttle.vessel else None,
                'allocated_capacity': allocated_capacity,
                'estimated_cycles': max(1, round(allocated_capacity / avg_shuttle_capacity)),
                'utilization_percentage': min(100, (allocated_capacity / avg_shuttle_capacity) * 100)
            })
        
        return {
            'success': True,
            'requirements': requirements,
            'allocation': allocation,
            'summary': {
                'shuttles_allocated': shuttles_needed,
                'total_capacity_covered': sum(a['allocated_capacity'] for a in allocation),
                'average_utilization': sum(a['utilization_percentage'] for a in allocation) / len(allocation)
            }
        }
    
    def _determine_operation_status(self, operation: ShuttleOperation) -> str:
        """Determine current status of shuttle operation."""
        if operation.return_at:
            return 'completed'
        elif operation.discharge_end_at:
            return 'returning'
        elif operation.discharge_start_at:
            return 'discharging'
        elif operation.sail_out_at:
            return 'transit'
        elif operation.load_end_at:
            return 'loaded'
        elif operation.load_start_at:
            return 'loading'
        else:
            return 'planned'
    
    def _calculate_operation_progress(self, operation: ShuttleOperation) -> float:
        """Calculate operation progress percentage."""
        stages = [
            operation.load_start_at,
            operation.load_end_at,
            operation.sail_out_at,
            operation.discharge_start_at,
            operation.discharge_end_at,
            operation.return_at
        ]
        
        completed_stages = sum(1 for stage in stages if stage is not None)
        return (completed_stages / len(stages)) * 100
    
    def _estimate_operation_completion(self, operation: ShuttleOperation) -> Optional[str]:
        """Estimate operation completion time."""
        if operation.return_at:
            return None  # Already completed
        
        # Estimate based on current stage and typical durations
        now = datetime.utcnow()
        
        if operation.load_start_at and not operation.load_end_at:
            # Loading stage: typically 6 hours
            estimated = operation.load_start_at + timedelta(hours=6)
            remaining_hours = 18  # 6 + 4 + 6 + 2 (load + transit + discharge + return)
        elif operation.load_end_at and not operation.sail_out_at:
            estimated = operation.load_end_at + timedelta(hours=18)
            remaining_hours = 18
        elif operation.sail_out_at and not operation.discharge_start_at:
            # Transit: typically 4 hours
            estimated = operation.sail_out_at + timedelta(hours=4)
            remaining_hours = 14
        elif operation.discharge_start_at and not operation.discharge_end_at:
            # Discharge: typically 6 hours
            estimated = operation.discharge_start_at + timedelta(hours=6)
            remaining_hours = 8
        elif operation.discharge_end_at and not operation.return_at:
            # Return: typically 2 hours
            estimated = operation.discharge_end_at + timedelta(hours=2)
            remaining_hours = 2
        else:
            return None
        
        return estimated.isoformat()
    
    def _format_operation_response(self, operation: ShuttleOperation) -> Dict[str, Any]:
        """Format operation for API response."""
        return {
            'id': operation.id,
            'shuttle_name': operation.shuttle.vessel.name if operation.shuttle and operation.shuttle.vessel else None,
            'cape_vessel_name': operation.cape_vessel_name,
            'volume': operation.volume,
            'is_sublet': operation.is_sublet,
            'status': self._determine_operation_status(operation),
            'progress': self._calculate_operation_progress(operation),
            'timestamps': {
                'load_start': operation.load_start_at.isoformat() if operation.load_start_at else None,
                'load_end': operation.load_end_at.isoformat() if operation.load_end_at else None,
                'sail_out': operation.sail_out_at.isoformat() if operation.sail_out_at else None,
                'discharge_start': operation.discharge_start_at.isoformat() if operation.discharge_start_at else None,
                'discharge_end': operation.discharge_end_at.isoformat() if operation.discharge_end_at else None,
                'return': operation.return_at.isoformat() if operation.return_at else None
            }
        }
    
    def _get_efficiency_rating(self, score: float) -> str:
        """Get efficiency rating based on score."""
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 60:
            return 'average'
        else:
            return 'below_average'

