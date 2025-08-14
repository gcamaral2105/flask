"""
Capesize Service
===============

Business logic service for Capesize vessel operations management.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError

from app.repository.capesize_repository import CapesizeRepository
from app.repository.shuttle_repository import ShuttleOperationRepository
from app.repository.vld_repository import VLDRepository
from app.models.capesize import CapesizeVessel, CapesizeStatus
from app.models.shuttle import ShuttleOperation


class CapesizeService:
    """Service for Capesize vessel business logic."""
    
    def __init__(self):
        self.capesize_repo = CapesizeRepository()
        self.shuttle_operation_repo = ShuttleOperationRepository()
        self.vld_repo = VLDRepository()
    
    def create_capesize_operation(self, cape_vessel_id: int, target_tonnage: int,
                                 anchorage_location: str, eta: Optional[datetime] = None) -> Dict[str, Any]:
        """Create a new capesize operation."""
        try:
            capesize_operation = self.capesize_repo.create_operation(
                cape_vessel_id=cape_vessel_id,
                target_tonnage=target_tonnage,
                anchorage_location=anchorage_location,
                eta=eta
            )
            
            return {
                'success': True,
                'operation': {
                    'id': capesize_operation.id,
                    'cape_vessel_name': capesize_operation.cape_vessel.name if capesize_operation.cape_vessel else None,
                    'target_tonnage': target_tonnage,
                    'anchorage_location': anchorage_location,
                    'eta': eta.isoformat() if eta else None,
                    'status': capesize_operation.status.value
                },
                'message': f'Capesize operation created for {target_tonnage}t'
            }
            
        except IntegrityError as e:
            raise ValueError(f"Failed to create capesize operation: {str(e)}")
    
    def update_arrival(self, operation_id: int, ata: datetime) -> Dict[str, Any]:
        """Update capesize vessel arrival at anchorage."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        if operation.status != CapesizeStatus.SCHEDULED:
            raise ValueError("Operation must be scheduled to update arrival")
        
        operation = self.capesize_repo.update_arrival(operation_id, ata)
        
        # Calculate delay if ETA was provided
        delay_hours = None
        if operation.eta:
            delay_hours = (ata - operation.eta).total_seconds() / 3600
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'delay_hours': round(delay_hours, 2) if delay_hours else None,
            'message': f'Capesize vessel arrived at anchorage'
        }
    
    def start_loading_operations(self, operation_id: int) -> Dict[str, Any]:
        """Start loading operations for capesize vessel."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        if operation.status != CapesizeStatus.ARRIVED:
            raise ValueError("Vessel must be arrived to start loading")
        
        operation = self.capesize_repo.start_loading(operation_id)
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'message': f'Loading operations started for capesize vessel'
        }
    
    def complete_loading_operations(self, operation_id: int, final_tonnage: int) -> Dict[str, Any]:
        """Complete loading operations for capesize vessel."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        if operation.status != CapesizeStatus.LOADING:
            raise ValueError("Operation must be in loading status to complete")
        
        if final_tonnage <= 0:
            raise ValueError("Final tonnage must be positive")
        
        operation = self.capesize_repo.complete_loading(operation_id, final_tonnage)
        
        # Calculate performance metrics
        variance = final_tonnage - operation.target_tonnage
        variance_pct = (variance / operation.target_tonnage * 100) if operation.target_tonnage > 0 else 0
        
        # Calculate loading duration
        loading_hours = None
        if operation.loading_start and operation.loading_completion:
            loading_hours = (operation.loading_completion - operation.loading_start).total_seconds() / 3600
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'performance': {
                'target_tonnage': operation.target_tonnage,
                'final_tonnage': final_tonnage,
                'variance': variance,
                'variance_percentage': round(variance_pct, 2),
                'loading_hours': round(loading_hours, 2) if loading_hours else None
            },
            'message': f'Loading completed: {final_tonnage}t loaded'
        }
    
    def vessel_departure(self, operation_id: int, ats: Optional[datetime] = None) -> Dict[str, Any]:
        """Record capesize vessel departure."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        if operation.status != CapesizeStatus.COMPLETED:
            raise ValueError("Loading must be completed before departure")
        
        operation = self.capesize_repo.vessel_departure(operation_id, ats or datetime.utcnow())
        
        # Calculate total anchorage time
        anchorage_hours = None
        if operation.ata and operation.ats:
            anchorage_hours = (operation.ats - operation.ata).total_seconds() / 3600
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'anchorage_hours': round(anchorage_hours, 2) if anchorage_hours else None,
            'message': f'Capesize vessel departed'
        }
    
    def get_active_operations(self) -> Dict[str, Any]:
        """Get all active capesize operations."""
        active_operations = self.capesize_repo.get_active_operations()
        
        operations_data = []
        for operation in active_operations:
            op_data = self._format_operation_response(operation)
            
            # Add shuttle operations count
            shuttle_ops = self.shuttle_operation_repo.get_by_capesize_operation(operation.id)
            op_data['shuttle_operations'] = len(shuttle_ops)
            op_data['shuttle_progress'] = self._calculate_shuttle_progress(shuttle_ops)
            
            operations_data.append(op_data)
        
        return {
            'success': True,
            'active_operations': operations_data,
            'total': len(operations_data)
        }
    
    def get_operation_details(self, operation_id: int) -> Dict[str, Any]:
        """Get detailed information about a capesize operation."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        # Get associated shuttle operations
        shuttle_operations = self.shuttle_operation_repo.get_by_capesize_operation(operation_id)
        
        shuttle_ops_data = []
        for shuttle_op in shuttle_operations:
            shuttle_data = {
                'id': shuttle_op.id,
                'shuttle_name': shuttle_op.shuttle.vessel.name if shuttle_op.shuttle and shuttle_op.shuttle.vessel else None,
                'volume': shuttle_op.volume,
                'status': self._determine_shuttle_status(shuttle_op),
                'progress': self._calculate_single_shuttle_progress(shuttle_op),
                'timestamps': {
                    'load_start': shuttle_op.load_start_at.isoformat() if shuttle_op.load_start_at else None,
                    'load_end': shuttle_op.load_end_at.isoformat() if shuttle_op.load_end_at else None,
                    'discharge_start': shuttle_op.discharge_start_at.isoformat() if shuttle_op.discharge_start_at else None,
                    'discharge_end': shuttle_op.discharge_end_at.isoformat() if shuttle_op.discharge_end_at else None
                }
            }
            shuttle_ops_data.append(shuttle_data)
        
        # Calculate overall progress
        total_loaded = sum(op.volume for op in shuttle_operations if op.volume and op.discharge_end_at)
        progress_percentage = (total_loaded / operation.target_tonnage * 100) if operation.target_tonnage > 0 else 0
        
        return {
            'success': True,
            'operation': self._format_operation_response(operation),
            'shuttle_operations': shuttle_ops_data,
            'progress': {
                'total_loaded': total_loaded,
                'target_tonnage': operation.target_tonnage,
                'remaining_tonnage': operation.target_tonnage - total_loaded,
                'progress_percentage': round(progress_percentage, 2),
                'shuttles_completed': len([op for op in shuttle_operations if op.return_at]),
                'shuttles_active': len([op for op in shuttle_operations if not op.return_at])
            }
        }
    
    def get_anchorage_status(self, anchorage_location: str) -> Dict[str, Any]:
        """Get status of vessels at a specific anchorage."""
        operations = self.capesize_repo.get_by_anchorage(anchorage_location)
        
        # Filter active operations
        active_operations = [op for op in operations if op.status in [
            CapesizeStatus.ARRIVED, CapesizeStatus.LOADING
        ]]
        
        operations_data = []
        for operation in active_operations:
            op_data = self._format_operation_response(operation)
            
            # Add progress information
            shuttle_ops = self.shuttle_operation_repo.get_by_capesize_operation(operation.id)
            total_loaded = sum(op.volume for op in shuttle_ops if op.volume and op.discharge_end_at)
            
            op_data['progress'] = {
                'loaded_tonnage': total_loaded,
                'remaining_tonnage': operation.target_tonnage - total_loaded,
                'progress_percentage': (total_loaded / operation.target_tonnage * 100) if operation.target_tonnage > 0 else 0
            }
            
            operations_data.append(op_data)
        
        return {
            'success': True,
            'anchorage_location': anchorage_location,
            'active_operations': operations_data,
            'total_vessels': len(operations_data),
            'total_capacity': sum(op['target_tonnage'] for op in operations_data)
        }
    
    def get_completion_forecast(self, operation_id: int) -> Dict[str, Any]:
        """Get completion forecast for a capesize operation."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        if operation.status == CapesizeStatus.DEPARTED:
            return {
                'success': True,
                'message': 'Operation already completed',
                'forecast': None
            }
        
        # Get shuttle operations
        shuttle_operations = self.shuttle_operation_repo.get_by_capesize_operation(operation_id)
        
        # Calculate current progress
        total_loaded = sum(op.volume for op in shuttle_operations if op.volume and op.discharge_end_at)
        remaining_tonnage = operation.target_tonnage - total_loaded
        
        if remaining_tonnage <= 0:
            return {
                'success': True,
                'message': 'Target tonnage already achieved',
                'forecast': {
                    'completion_status': 'ready_for_departure',
                    'estimated_completion': 'now'
                }
            }
        
        # Estimate remaining shuttles needed
        avg_shuttle_capacity = 15000  # Typical shuttle capacity
        shuttles_needed = max(1, round(remaining_tonnage / avg_shuttle_capacity))
        
        # Estimate completion time based on shuttle cycle time
        avg_cycle_hours = 24  # Typical shuttle cycle time
        estimated_hours = shuttles_needed * avg_cycle_hours
        
        estimated_completion = datetime.utcnow() + timedelta(hours=estimated_hours)
        
        return {
            'success': True,
            'forecast': {
                'current_tonnage': total_loaded,
                'target_tonnage': operation.target_tonnage,
                'remaining_tonnage': remaining_tonnage,
                'shuttles_needed': shuttles_needed,
                'estimated_completion_hours': estimated_hours,
                'estimated_completion': estimated_completion.isoformat(),
                'confidence': 'medium'  # Based on historical data
            }
        }
    
    def get_efficiency_analysis(self, operation_id: int) -> Dict[str, Any]:
        """Analyze efficiency of a capesize operation."""
        operation = self.capesize_repo.get_by_id(operation_id)
        if not operation:
            raise ValueError(f"Capesize operation {operation_id} not found")
        
        shuttle_operations = self.shuttle_operation_repo.get_by_capesize_operation(operation_id)
        
        if not shuttle_operations:
            return {
                'success': True,
                'message': 'No shuttle operations found',
                'analysis': None
            }
        
        # Calculate efficiency metrics
        completed_shuttles = [op for op in shuttle_operations if op.return_at]
        
        if not completed_shuttles:
            return {
                'success': True,
                'message': 'No completed shuttle operations yet',
                'analysis': None
            }
        
        # Average cycle time
        cycle_times = []
        for shuttle_op in completed_shuttles:
            if shuttle_op.load_start_at and shuttle_op.return_at:
                cycle_time = (shuttle_op.return_at - shuttle_op.load_start_at).total_seconds() / 3600
                cycle_times.append(cycle_time)
        
        avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else 0
        
        # Loading rates
        loading_rates = []
        for shuttle_op in completed_shuttles:
            if (shuttle_op.load_start_at and shuttle_op.load_end_at and 
                shuttle_op.volume and shuttle_op.volume > 0):
                loading_hours = (shuttle_op.load_end_at - shuttle_op.load_start_at).total_seconds() / 3600
                if loading_hours > 0:
                    loading_rates.append(shuttle_op.volume / loading_hours)
        
        avg_loading_rate = sum(loading_rates) / len(loading_rates) if loading_rates else 0
        
        # Discharge rates
        discharge_rates = []
        for shuttle_op in completed_shuttles:
            if (shuttle_op.discharge_start_at and shuttle_op.discharge_end_at and 
                shuttle_op.volume and shuttle_op.volume > 0):
                discharge_hours = (shuttle_op.discharge_end_at - shuttle_op.discharge_start_at).total_seconds() / 3600
                if discharge_hours > 0:
                    discharge_rates.append(shuttle_op.volume / discharge_hours)
        
        avg_discharge_rate = sum(discharge_rates) / len(discharge_rates) if discharge_rates else 0
        
        # Efficiency score (0-100)
        benchmark_cycle_time = 24  # hours
        benchmark_loading_rate = 2500  # tph
        benchmark_discharge_rate = 2500  # tph
        
        cycle_efficiency = min(100, (benchmark_cycle_time / avg_cycle_time * 100)) if avg_cycle_time > 0 else 0
        loading_efficiency = min(100, (avg_loading_rate / benchmark_loading_rate * 100)) if avg_loading_rate > 0 else 0
        discharge_efficiency = min(100, (avg_discharge_rate / benchmark_discharge_rate * 100)) if avg_discharge_rate > 0 else 0
        
        overall_efficiency = (cycle_efficiency + loading_efficiency + discharge_efficiency) / 3
        
        return {
            'success': True,
            'analysis': {
                'completed_shuttles': len(completed_shuttles),
                'average_cycle_time_hours': round(avg_cycle_time, 2),
                'average_loading_rate_tph': round(avg_loading_rate, 1),
                'average_discharge_rate_tph': round(avg_discharge_rate, 1),
                'efficiency_scores': {
                    'cycle_efficiency': round(cycle_efficiency, 1),
                    'loading_efficiency': round(loading_efficiency, 1),
                    'discharge_efficiency': round(discharge_efficiency, 1),
                    'overall_efficiency': round(overall_efficiency, 1)
                },
                'benchmarks': {
                    'target_cycle_time_hours': benchmark_cycle_time,
                    'target_loading_rate_tph': benchmark_loading_rate,
                    'target_discharge_rate_tph': benchmark_discharge_rate
                }
            }
        }
    
    def get_capesize_statistics(self, start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get capesize operations statistics."""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        stats = self.capesize_repo.get_capesize_statistics(start_date, end_date)
        
        return {
            'success': True,
            'statistics': stats,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            }
        }
    
    def _format_operation_response(self, operation) -> Dict[str, Any]:
        """Format capesize operation for API response."""
        return {
            'id': operation.id,
            'cape_vessel_name': operation.cape_vessel.name if operation.cape_vessel else None,
            'target_tonnage': operation.target_tonnage,
            'current_tonnage': operation.current_tonnage,
            'anchorage_location': operation.anchorage_location,
            'status': operation.status.value,
            'eta': operation.eta.isoformat() if operation.eta else None,
            'ata': operation.ata.isoformat() if operation.ata else None,
            'loading_start': operation.loading_start.isoformat() if operation.loading_start else None,
            'loading_completion': operation.loading_completion.isoformat() if operation.loading_completion else None,
            'ats': operation.ats.isoformat() if operation.ats else None
        }
    
    def _determine_shuttle_status(self, shuttle_op: ShuttleOperation) -> str:
        """Determine current status of shuttle operation."""
        if shuttle_op.return_at:
            return 'completed'
        elif shuttle_op.discharge_end_at:
            return 'returning'
        elif shuttle_op.discharge_start_at:
            return 'discharging'
        elif shuttle_op.sail_out_at:
            return 'transit'
        elif shuttle_op.load_end_at:
            return 'loaded'
        elif shuttle_op.load_start_at:
            return 'loading'
        else:
            return 'planned'
    
    def _calculate_single_shuttle_progress(self, shuttle_op: ShuttleOperation) -> float:
        """Calculate progress percentage for a single shuttle operation."""
        stages = [
            shuttle_op.load_start_at,
            shuttle_op.load_end_at,
            shuttle_op.sail_out_at,
            shuttle_op.discharge_start_at,
            shuttle_op.discharge_end_at,
            shuttle_op.return_at
        ]
        
        completed_stages = sum(1 for stage in stages if stage is not None)
        return (completed_stages / len(stages)) * 100
    
    def _calculate_shuttle_progress(self, shuttle_operations: List[ShuttleOperation]) -> Dict[str, Any]:
        """Calculate overall shuttle progress for capesize operation."""
        if not shuttle_operations:
            return {'total_progress': 0, 'completed_shuttles': 0, 'active_shuttles': 0}
        
        completed_shuttles = len([op for op in shuttle_operations if op.return_at])
        active_shuttles = len(shuttle_operations) - completed_shuttles
        
        total_progress = sum(self._calculate_single_shuttle_progress(op) for op in shuttle_operations)
        avg_progress = total_progress / len(shuttle_operations)
        
        return {
            'total_progress': round(avg_progress, 2),
            'completed_shuttles': completed_shuttles,
            'active_shuttles': active_shuttles,
            'total_shuttles': len(shuttle_operations)
        }

