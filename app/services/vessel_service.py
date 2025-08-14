"""
Vessel Service
=============

Business logic service for Vessel management in the ERP Bauxita system.
Handles vessel operations, maintenance scheduling, and fleet management.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from decimal import Decimal

from app.repository.vessel_repository import VesselRepository
from app.repository.partner_repository import PartnerRepository
from app.models.vessel import Vessel, VesselStatus, VesselType
from app.models.partner import Partner
from app.extensions import db


class VesselService:
    """Service class for vessel management business logic."""
    
    def __init__(self):
        self.vessel_repo = VesselRepository()
        self.partner_repo = PartnerRepository()
    
    def create_vessel(self, vessel_data: Dict[str, Any]) -> Vessel:
        """
        Create a new vessel with business validation.
        
        Args:
            vessel_data: Dictionary containing vessel information
            
        Returns:
            Created Vessel instance
            
        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        required_fields = ['name', 'vtype']
        for field in required_fields:
            if field not in vessel_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate vessel name uniqueness
        existing_vessel = self.vessel_repo.get_by_name(vessel_data['name'])
        if existing_vessel:
            raise ValueError(f"Vessel with name '{vessel_data['name']}' already exists")
        
        # Validate IMO if provided
        if 'imo' in vessel_data and vessel_data['imo']:
            self._validate_imo(vessel_data['imo'])
            existing_imo = self.vessel_repo.get_by_imo(vessel_data['imo'])
            if existing_imo:
                raise ValueError(f"Vessel with IMO '{vessel_data['imo']}' already exists")
        
        # Validate specifications
        if 'dwt' in vessel_data:
            self._validate_dwt(vessel_data['dwt'])
        
        if 'loa' in vessel_data:
            self._validate_dimension(vessel_data['loa'], 'Length Overall')
        
        if 'beam' in vessel_data:
            self._validate_dimension(vessel_data['beam'], 'Beam')
        
        # Validate owner if provided
        if 'owner_partner_id' in vessel_data and vessel_data['owner_partner_id']:
            owner = self.partner_repo.get_by_id(vessel_data['owner_partner_id'])
            if not owner:
                raise ValueError(f"Owner partner with ID {vessel_data['owner_partner_id']} not found")
        
        # Set default status if not provided
        vessel_data.setdefault('status', VesselStatus.ACTIVE)
        
        vessel = self.vessel_repo.create(**vessel_data)
        
        # Log vessel creation
        self._log_vessel_event(vessel, "CREATED")
        
        return vessel
    
    def update_vessel_specifications(self, vessel_id: Union[int, str], 
                                   specifications: Dict[str, Any]) -> Vessel:
        """
        Update vessel specifications with validation.
        
        Args:
            vessel_id: ID of the vessel to update
            specifications: Dictionary of specifications to update
            
        Returns:
            Updated Vessel instance
        """
        vessel = self.vessel_repo.get_by_id(vessel_id)
        if not vessel:
            raise ValueError(f"Vessel with ID {vessel_id} not found")
        
        # Validate specifications
        if 'dwt' in specifications:
            self._validate_dwt(specifications['dwt'])
        
        if 'loa' in specifications:
            self._validate_dimension(specifications['loa'], 'Length Overall')
        
        if 'beam' in specifications:
            self._validate_dimension(specifications['beam'], 'Beam')
        
        if 'imo' in specifications and specifications['imo'] != vessel.imo:
            self._validate_imo(specifications['imo'])
            existing_imo = self.vessel_repo.get_by_imo(specifications['imo'])
            if existing_imo and existing_imo.id != vessel.id:
                raise ValueError(f"IMO '{specifications['imo']}' is already assigned to another vessel")
        
        # Update vessel
        updated_vessel = self.vessel_repo.update(vessel_id, **specifications)
        
        # Log specification update
        self._log_vessel_event(updated_vessel, "SPECIFICATIONS_UPDATED", 
                             updated_fields=list(specifications.keys()))
        
        return updated_vessel
    
    def change_vessel_status(self, vessel_id: Union[int, str], 
                           new_status: VesselStatus, 
                           reason: Optional[str] = None) -> Vessel:
        """
        Change vessel status with business logic validation.
        
        Args:
            vessel_id: ID of the vessel
            new_status: New status to set
            reason: Optional reason for status change
            
        Returns:
            Updated Vessel instance
        """
        vessel = self.vessel_repo.get_by_id(vessel_id)
        if not vessel:
            raise ValueError(f"Vessel with ID {vessel_id} not found")
        
        old_status = vessel.status
        
        # Validate status transition
        self._validate_status_transition(old_status, new_status)
        
        # Perform status-specific validations
        if new_status == VesselStatus.MAINTENANCE:
            self._validate_maintenance_requirements(vessel)
        elif new_status == VesselStatus.RETIRED:
            self._validate_retirement_requirements(vessel)
        
        # Update status
        updated_vessel = self.vessel_repo.update_vessel_status(vessel_id, new_status)
        
        # Log status change
        self._log_vessel_event(updated_vessel, "STATUS_CHANGED",
                             old_status=old_status.value,
                             new_status=new_status.value,
                             reason=reason)
        
        return updated_vessel
    
    def assign_vessel_owner(self, vessel_id: Union[int, str], 
                          partner_id: Union[int, str]) -> Vessel:
        """
        Assign an owner to a vessel with validation.
        
        Args:
            vessel_id: ID of the vessel
            partner_id: ID of the partner to assign as owner
            
        Returns:
            Updated Vessel instance
        """
        vessel = self.vessel_repo.get_by_id(vessel_id)
        if not vessel:
            raise ValueError(f"Vessel with ID {vessel_id} not found")
        
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        # Business validation: check if partner can own vessels
        # This could check partner type, status, etc.
        
        old_owner_id = vessel.owner_partner_id
        updated_vessel = self.vessel_repo.assign_owner(vessel_id, partner_id)
        
        # Log ownership change
        self._log_vessel_event(updated_vessel, "OWNER_ASSIGNED",
                             old_owner_id=old_owner_id,
                             new_owner_id=partner_id,
                             new_owner_name=partner.name)
        
        return updated_vessel
    
    def schedule_maintenance(self, vessel_id: Union[int, str], 
                           maintenance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule maintenance for a vessel.
        
        Args:
            vessel_id: ID of the vessel
            maintenance_data: Maintenance scheduling information
            
        Returns:
            Maintenance schedule information
        """
        vessel = self.vessel_repo.get_by_id(vessel_id)
        if not vessel:
            raise ValueError(f"Vessel with ID {vessel_id} not found")
        
        # Validate maintenance data
        required_fields = ['scheduled_start', 'estimated_duration_days', 'maintenance_type']
        for field in required_fields:
            if field not in maintenance_data:
                raise ValueError(f"Missing required maintenance field: {field}")
        
        # Business validations
        scheduled_start = maintenance_data['scheduled_start']
        if isinstance(scheduled_start, str):
            scheduled_start = datetime.fromisoformat(scheduled_start)
        
        if scheduled_start < datetime.now():
            raise ValueError("Maintenance cannot be scheduled in the past")
        
        duration = maintenance_data['estimated_duration_days']
        if duration <= 0 or duration > 365:
            raise ValueError("Maintenance duration must be between 1 and 365 days")
        
        # Check for scheduling conflicts
        conflicts = self._check_maintenance_conflicts(vessel_id, scheduled_start, duration)
        if conflicts:
            raise ValueError(f"Maintenance scheduling conflict detected: {conflicts}")
        
        # Create maintenance schedule
        maintenance_schedule = {
            'vessel_id': vessel_id,
            'vessel_name': vessel.name,
            'scheduled_start': scheduled_start.isoformat(),
            'scheduled_end': (scheduled_start + timedelta(days=duration)).isoformat(),
            'maintenance_type': maintenance_data['maintenance_type'],
            'estimated_cost': maintenance_data.get('estimated_cost'),
            'description': maintenance_data.get('description'),
            'status': 'SCHEDULED'
        }
        
        # In a real implementation, this would be saved to a maintenance table
        # For now, we'll just return the schedule data
        
        # Log maintenance scheduling
        self._log_vessel_event(vessel, "MAINTENANCE_SCHEDULED",
                             maintenance_type=maintenance_data['maintenance_type'],
                             scheduled_start=scheduled_start.isoformat())
        
        return maintenance_schedule
    
    def get_fleet_overview(self, owner_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Get comprehensive fleet overview.
        
        Args:
            owner_id: Optional filter by owner partner ID
            
        Returns:
            Fleet overview data
        """
        if owner_id:
            vessels = self.vessel_repo.get_by_owner(owner_id)
            fleet_info = self.vessel_repo.get_fleet_by_owner(owner_id)
        else:
            vessels = self.vessel_repo.get_active()
            fleet_info = self.vessel_repo.get_vessel_statistics()
        
        # Calculate additional metrics
        overview = {
            'total_vessels': len(vessels),
            'fleet_statistics': fleet_info,
            'operational_status': self._calculate_operational_metrics(vessels),
            'capacity_analysis': self._calculate_capacity_metrics(vessels),
            'maintenance_overview': self._get_maintenance_overview(vessels),
            'vessel_list': []
        }
        
        # Add vessel details
        for vessel in vessels:
            vessel_info = {
                'id': vessel.id,
                'name': vessel.name,
                'type': vessel.vtype.value if vessel.vtype else None,
                'status': vessel.status.value if vessel.status else None,
                'dwt': vessel.dwt,
                'owner': vessel.owner_partner.name if vessel.owner_partner else None,
                'utilization_status': self._get_vessel_utilization_status(vessel)
            }
            overview['vessel_list'].append(vessel_info)
        
        return overview
    
    def get_vessel_performance_report(self, vessel_id: Union[int, str], 
                                    period_days: int = 365) -> Dict[str, Any]:
        """
        Generate performance report for a specific vessel.
        
        Args:
            vessel_id: ID of the vessel
            period_days: Period for analysis in days
            
        Returns:
            Performance report data
        """
        vessel = self.vessel_repo.get_by_id(vessel_id)
        if not vessel:
            raise ValueError(f"Vessel with ID {vessel_id} not found")
        
        # Calculate performance metrics
        report = {
            'vessel_id': vessel_id,
            'vessel_name': vessel.name,
            'report_period_days': period_days,
            'current_status': vessel.status.value,
            'operational_metrics': self._calculate_vessel_operational_metrics(vessel, period_days),
            'maintenance_history': self._get_vessel_maintenance_history(vessel, period_days),
            'utilization_metrics': self._calculate_vessel_utilization(vessel, period_days),
            'cost_analysis': self._calculate_vessel_costs(vessel, period_days),
            'recommendations': self._generate_vessel_recommendations(vessel)
        }
        
        return report
    
    def optimize_fleet_allocation(self, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Optimize fleet allocation based on requirements.
        
        Args:
            requirements: List of allocation requirements
            
        Returns:
            Optimization results
        """
        available_vessels = self.vessel_repo.get_available_vessels()
        
        allocation_result = {
            'total_requirements': len(requirements),
            'available_vessels': len(available_vessels),
            'allocations': [],
            'unmet_requirements': [],
            'optimization_score': 0
        }
        
        # Simple allocation algorithm (in practice, this would be more sophisticated)
        allocated_vessels = set()
        
        for requirement in requirements:
            best_match = self._find_best_vessel_match(
                requirement, 
                [v for v in available_vessels if v.id not in allocated_vessels]
            )
            
            if best_match:
                allocation_result['allocations'].append({
                    'requirement': requirement,
                    'allocated_vessel': {
                        'id': best_match.id,
                        'name': best_match.name,
                        'type': best_match.vtype.value,
                        'dwt': best_match.dwt
                    },
                    'match_score': self._calculate_match_score(requirement, best_match)
                })
                allocated_vessels.add(best_match.id)
            else:
                allocation_result['unmet_requirements'].append(requirement)
        
        # Calculate overall optimization score
        if allocation_result['allocations']:
            total_score = sum(alloc['match_score'] for alloc in allocation_result['allocations'])
            allocation_result['optimization_score'] = total_score / len(allocation_result['allocations'])
        
        return allocation_result
    
    def _validate_imo(self, imo: str) -> None:
        """Validate IMO number format."""
        if not imo or len(imo) != 7 or not imo.isdigit():
            raise ValueError("IMO must be a 7-digit number")
    
    def _validate_dwt(self, dwt: int) -> None:
        """Validate deadweight tonnage."""
        if dwt <= 0:
            raise ValueError("DWT must be positive")
        if dwt > 500_000:  # 500k tons max
            raise ValueError("DWT seems unreasonably high")
    
    def _validate_dimension(self, dimension: Decimal, dimension_name: str) -> None:
        """Validate vessel dimensions."""
        if dimension <= 0:
            raise ValueError(f"{dimension_name} must be positive")
        if dimension > 500:  # 500 meters max
            raise ValueError(f"{dimension_name} seems unreasonably large")
    
    def _validate_status_transition(self, old_status: VesselStatus, new_status: VesselStatus) -> None:
        """Validate vessel status transitions."""
        # Define allowed transitions
        allowed_transitions = {
            VesselStatus.ACTIVE: [VesselStatus.INACTIVE, VesselStatus.MAINTENANCE, VesselStatus.RETIRED],
            VesselStatus.INACTIVE: [VesselStatus.ACTIVE, VesselStatus.MAINTENANCE, VesselStatus.RETIRED],
            VesselStatus.MAINTENANCE: [VesselStatus.ACTIVE, VesselStatus.INACTIVE],
            VesselStatus.RETIRED: []  # No transitions from retired
        }
        
        if new_status not in allowed_transitions.get(old_status, []):
            raise ValueError(f"Invalid status transition from {old_status.value} to {new_status.value}")
    
    def _validate_maintenance_requirements(self, vessel: Vessel) -> None:
        """Validate requirements for putting vessel into maintenance."""
        if vessel.status == VesselStatus.RETIRED:
            raise ValueError("Cannot perform maintenance on retired vessel")
    
    def _validate_retirement_requirements(self, vessel: Vessel) -> None:
        """Validate requirements for retiring a vessel."""
        # Check if vessel has active assignments (placeholder)
        # In a real system, this would check for active lineups, contracts, etc.
        pass
    
    def _check_maintenance_conflicts(self, vessel_id: Union[int, str], 
                                   start_date: datetime, duration_days: int) -> Optional[str]:
        """Check for maintenance scheduling conflicts."""
        # This would check against existing maintenance schedules
        # For now, it's a placeholder
        return None
    
    def _calculate_operational_metrics(self, vessels: List[Vessel]) -> Dict[str, Any]:
        """Calculate operational metrics for a fleet."""
        if not vessels:
            return {}
        
        status_counts = {}
        for vessel in vessels:
            status = vessel.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'by_status': status_counts,
            'operational_percentage': (
                status_counts.get('active', 0) / len(vessels) * 100
            ),
            'maintenance_percentage': (
                status_counts.get('maintenance', 0) / len(vessels) * 100
            )
        }
    
    def _calculate_capacity_metrics(self, vessels: List[Vessel]) -> Dict[str, Any]:
        """Calculate capacity metrics for a fleet."""
        total_dwt = sum(v.dwt for v in vessels if v.dwt)
        vessel_count_by_type = {}
        
        for vessel in vessels:
            if vessel.vtype:
                vessel_type = vessel.vtype.value
                vessel_count_by_type[vessel_type] = vessel_count_by_type.get(vessel_type, 0) + 1
        
        return {
            'total_dwt': total_dwt,
            'average_dwt': total_dwt / len(vessels) if vessels else 0,
            'by_type': vessel_count_by_type
        }
    
    def _get_maintenance_overview(self, vessels: List[Vessel]) -> Dict[str, Any]:
        """Get maintenance overview for a fleet."""
        maintenance_vessels = [v for v in vessels if v.status == VesselStatus.MAINTENANCE]
        
        return {
            'vessels_in_maintenance': len(maintenance_vessels),
            'maintenance_percentage': len(maintenance_vessels) / len(vessels) * 100 if vessels else 0,
            'upcoming_maintenance': []  # Placeholder for scheduled maintenance
        }
    
    def _get_vessel_utilization_status(self, vessel: Vessel) -> str:
        """Get utilization status for a vessel."""
        # This would integrate with lineup/scheduling systems
        # For now, return based on status
        if vessel.status == VesselStatus.ACTIVE:
            return "Available"
        elif vessel.status == VesselStatus.MAINTENANCE:
            return "In Maintenance"
        else:
            return vessel.status.value.title()
    
    def _calculate_vessel_operational_metrics(self, vessel: Vessel, period_days: int) -> Dict[str, Any]:
        """Calculate operational metrics for a specific vessel."""
        # Placeholder for detailed operational metrics
        return {
            'operational_days': period_days * 0.8,  # Placeholder
            'maintenance_days': period_days * 0.1,  # Placeholder
            'idle_days': period_days * 0.1,  # Placeholder
            'utilization_rate': 80.0  # Placeholder
        }
    
    def _get_vessel_maintenance_history(self, vessel: Vessel, period_days: int) -> List[Dict[str, Any]]:
        """Get maintenance history for a vessel."""
        # Placeholder for maintenance history
        return []
    
    def _calculate_vessel_utilization(self, vessel: Vessel, period_days: int) -> Dict[str, Any]:
        """Calculate utilization metrics for a vessel."""
        # Placeholder for utilization calculations
        return {
            'total_voyages': 12,  # Placeholder
            'total_cargo_tons': 240_000,  # Placeholder
            'average_cargo_per_voyage': 20_000,  # Placeholder
            'capacity_utilization': 85.0  # Placeholder
        }
    
    def _calculate_vessel_costs(self, vessel: Vessel, period_days: int) -> Dict[str, Any]:
        """Calculate cost metrics for a vessel."""
        # Placeholder for cost calculations
        return {
            'operational_costs': 1_000_000,  # Placeholder
            'maintenance_costs': 200_000,  # Placeholder
            'fuel_costs': 800_000,  # Placeholder
            'total_costs': 2_000_000  # Placeholder
        }
    
    def _generate_vessel_recommendations(self, vessel: Vessel) -> List[str]:
        """Generate recommendations for a vessel."""
        recommendations = []
        
        # Example recommendations based on vessel status
        if vessel.status == VesselStatus.MAINTENANCE:
            recommendations.append("Complete scheduled maintenance to return to service")
        
        if not vessel.imo:
            recommendations.append("Consider adding IMO number for better tracking")
        
        if not vessel.dwt:
            recommendations.append("Update vessel specifications with DWT information")
        
        return recommendations
    
    def _find_best_vessel_match(self, requirement: Dict[str, Any], 
                               available_vessels: List[Vessel]) -> Optional[Vessel]:
        """Find the best vessel match for a requirement."""
        if not available_vessels:
            return None
        
        # Simple matching logic (in practice, this would be more sophisticated)
        required_dwt = requirement.get('min_dwt', 0)
        required_type = requirement.get('vessel_type')
        
        suitable_vessels = []
        for vessel in available_vessels:
            if vessel.dwt and vessel.dwt >= required_dwt:
                if not required_type or vessel.vtype.value == required_type:
                    suitable_vessels.append(vessel)
        
        if suitable_vessels:
            # Return vessel with closest DWT to requirement
            return min(suitable_vessels, key=lambda v: abs(v.dwt - required_dwt))
        
        return None
    
    def _calculate_match_score(self, requirement: Dict[str, Any], vessel: Vessel) -> float:
        """Calculate match score between requirement and vessel."""
        score = 100.0
        
        # Adjust score based on DWT match
        required_dwt = requirement.get('min_dwt', 0)
        if vessel.dwt and required_dwt > 0:
            dwt_ratio = vessel.dwt / required_dwt
            if dwt_ratio < 1:
                score *= dwt_ratio  # Penalize insufficient capacity
            elif dwt_ratio > 2:
                score *= 0.8  # Penalize over-capacity
        
        # Adjust score based on type match
        required_type = requirement.get('vessel_type')
        if required_type and vessel.vtype.value != required_type:
            score *= 0.7
        
        return min(score, 100.0)
    
    def _log_vessel_event(self, vessel: Vessel, event_type: str, **kwargs) -> None:
        """Log vessel events for audit trail."""
        log_data = {
            'vessel_id': vessel.id,
            'vessel_name': vessel.name,
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        
        # In a real implementation, this would write to a log table or external system
        print(f"Vessel Event: {log_data}")  # Placeholder

