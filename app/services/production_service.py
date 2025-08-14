"""
Production Service
=================

Business logic service for Production management in the ERP Bauxita system.
Handles complex production scenarios, partner enrollments, and business rules.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from decimal import Decimal

from app.repository.production_repository import ProductionRepository
from app.repository.partner_repository import PartnerRepository
from app.models.production import Production, ProductionStatus, ProductionPartnerEnrollment
from app.models.partner import Partner
from app.extensions import db


class ProductionService:
    """Service class for production management business logic."""
    
    def __init__(self):
        self.production_repo = ProductionRepository()
        self.partner_repo = PartnerRepository()
    
    def create_production_scenario(self, scenario_data: Dict[str, Any]) -> Production:
        """
        Create a new production scenario with business validation.
        
        Args:
            scenario_data: Dictionary containing scenario information
            
        Returns:
            Created Production instance
            
        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        required_fields = [
            'scenario_name', 'contractual_year', 'total_planned_tonnage',
            'start_date_contractual_year', 'end_date_contractual_year'
        ]
        
        for field in required_fields:
            if field not in scenario_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Business validations
        self._validate_scenario_dates(
            scenario_data['start_date_contractual_year'],
            scenario_data['end_date_contractual_year']
        )
        
        self._validate_tonnage(scenario_data['total_planned_tonnage'])
        
        # Check for duplicate scenario names in the same year
        existing = self.production_repo.session.query(Production).filter(
            Production.contractual_year == scenario_data['contractual_year'],
            Production.scenario_name == scenario_data['scenario_name']
        ).first()
        
        if existing:
            raise ValueError(
                f"Scenario '{scenario_data['scenario_name']}' already exists for year {scenario_data['contractual_year']}"
            )
        
        # Set default values
        scenario_data.setdefault('status', ProductionStatus.DRAFT)
        scenario_data.setdefault('standard_moisture_content', Decimal('3.00'))
        scenario_data.setdefault('version', 1)
        
        return self.production_repo.create(**scenario_data)
    
    def activate_production_scenario(self, production_id: Union[int, str]) -> Production:
        """
        Activate a production scenario with business rules validation.
        
        Args:
            production_id: ID of the production to activate
            
        Returns:
            Activated Production instance
            
        Raises:
            ValueError: If activation is not allowed
        """
        production = self.production_repo.get_by_id(production_id)
        if not production:
            raise ValueError(f"Production with ID {production_id} not found")
        
        # Validate that scenario can be activated
        if production.status == ProductionStatus.ACTIVE:
            raise ValueError("Production scenario is already active")
        
        if production.status == ProductionStatus.COMPLETED:
            raise ValueError("Cannot activate a completed production scenario")
        
        # Check if scenario has minimum required enrollments
        if len(production.enrolled_partners) == 0:
            raise ValueError("Cannot activate production scenario without partner enrollments")
        
        # Validate total tonnage allocation
        self._validate_tonnage_allocation(production)
        
        # Activate the scenario (repository handles deactivating others)
        activated_production = self.production_repo.activate_scenario(production_id)
        
        # Log activation event
        self._log_production_event(activated_production, "ACTIVATED")
        
        return activated_production
    
    def complete_production_scenario(self, production_id: Union[int, str]) -> Production:
        """
        Complete a production scenario and perform final validations.
        
        Args:
            production_id: ID of the production to complete
            
        Returns:
            Completed Production instance
        """
        production = self.production_repo.get_by_id(production_id)
        if not production:
            raise ValueError(f"Production with ID {production_id} not found")
        
        if production.status != ProductionStatus.ACTIVE:
            raise ValueError("Only active production scenarios can be completed")
        
        # Perform completion validations
        self._validate_completion_requirements(production)
        
        completed_production = self.production_repo.complete_scenario(production_id)
        
        # Log completion event
        self._log_production_event(completed_production, "COMPLETED")
        
        return completed_production
    
    def enroll_partner_in_production(self, production_id: Union[int, str],
                                   partner_id: Union[int, str],
                                   enrollment_data: Dict[str, Any]) -> ProductionPartnerEnrollment:
        """
        Enroll a partner in a production scenario with business validation.
        
        Args:
            production_id: ID of the production
            partner_id: ID of the partner
            enrollment_data: Enrollment details
            
        Returns:
            Created ProductionPartnerEnrollment instance
        """
        production = self.production_repo.get_by_id(production_id)
        if not production:
            raise ValueError(f"Production with ID {production_id} not found")
        
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        # Check if partner is already enrolled
        existing_enrollment = self.production_repo.get_partner_enrollment(production_id, partner_id)
        if existing_enrollment:
            raise ValueError(f"Partner {partner.name} is already enrolled in this production")
        
        # Validate enrollment data
        required_fields = ['vessel_size_t', 'minimum_tonnage']
        for field in required_fields:
            if field not in enrollment_data:
                raise ValueError(f"Missing required enrollment field: {field}")
        
        # Business validations
        self._validate_vessel_size(enrollment_data['vessel_size_t'])
        self._validate_tonnage(enrollment_data['minimum_tonnage'])
        
        # Create enrollment
        enrollment_data.update({
            'production_id': production_id,
            'partner_id': partner_id
        })
        
        enrollment = ProductionPartnerEnrollment(**enrollment_data)
        db.session.add(enrollment)
        db.session.commit()
        
        # Log enrollment event
        self._log_production_event(production, "PARTNER_ENROLLED", partner_name=partner.name)
        
        return enrollment
    
    def update_partner_enrollment(self, production_id: Union[int, str],
                                partner_id: Union[int, str],
                                updates: Dict[str, Any]) -> ProductionPartnerEnrollment:
        """
        Update partner enrollment with business validation.
        
        Args:
            production_id: ID of the production
            partner_id: ID of the partner
            updates: Fields to update
            
        Returns:
            Updated ProductionPartnerEnrollment instance
        """
        enrollment = self.production_repo.get_partner_enrollment(production_id, partner_id)
        if not enrollment:
            raise ValueError("Partner enrollment not found")
        
        # Validate updates
        if 'vessel_size_t' in updates:
            self._validate_vessel_size(updates['vessel_size_t'])
        
        if 'minimum_tonnage' in updates:
            self._validate_tonnage(updates['minimum_tonnage'])
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(enrollment, key):
                setattr(enrollment, key, value)
        
        db.session.commit()
        
        return enrollment
    
    def calculate_production_metrics(self, production_id: Union[int, str]) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics for a production scenario.
        
        Args:
            production_id: ID of the production
            
        Returns:
            Dictionary containing calculated metrics
        """
        production = self.production_repo.get_by_id(production_id)
        if not production:
            raise ValueError(f"Production with ID {production_id} not found")
        
        metrics = {
            'production_id': production_id,
            'scenario_name': production.scenario_name,
            'contractual_year': production.contractual_year,
            'status': production.status.value,
            'total_planned_tonnage': production.total_planned_tonnage,
            'duration_days': production.duration_days,
            'enrolled_partners_count': len(production.enrolled_partners),
            'total_minimum_tonnage': 0,
            'total_vessel_capacity': 0,
            'tonnage_utilization_percent': 0,
            'partners_by_type': {},
            'vessel_size_distribution': {},
            'average_vessel_size': 0
        }
        
        vessel_sizes = []
        
        for enrollment in production.enrolled_partners:
            metrics['total_minimum_tonnage'] += enrollment.minimum_tonnage or 0
            metrics['total_vessel_capacity'] += enrollment.vessel_size_t or 0
            
            if enrollment.vessel_size_t:
                vessel_sizes.append(enrollment.vessel_size_t)
                
                # Vessel size distribution
                size_range = self._get_vessel_size_range(enrollment.vessel_size_t)
                metrics['vessel_size_distribution'][size_range] = \
                    metrics['vessel_size_distribution'].get(size_range, 0) + 1
            
            # Partner type distribution (if available)
            if hasattr(enrollment.partner, 'entity_type'):
                partner_type = str(enrollment.partner.entity_type)
                metrics['partners_by_type'][partner_type] = \
                    metrics['partners_by_type'].get(partner_type, 0) + 1
        
        # Calculate utilization
        if production.total_planned_tonnage > 0:
            metrics['tonnage_utilization_percent'] = \
                (metrics['total_minimum_tonnage'] / production.total_planned_tonnage) * 100
        
        # Calculate average vessel size
        if vessel_sizes:
            metrics['average_vessel_size'] = sum(vessel_sizes) / len(vessel_sizes)
        
        return metrics
    
    def get_production_dashboard_data(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get dashboard data for production management.
        
        Args:
            year: Optional year filter
            
        Returns:
            Dashboard data dictionary
        """
        current_year = year or date.today().year
        
        # Get productions for the year
        productions = self.production_repo.get_by_year(current_year)
        active_production = self.production_repo.get_active_by_year(current_year)
        
        dashboard = {
            'year': current_year,
            'total_scenarios': len(productions),
            'active_scenario': None,
            'scenarios_by_status': {},
            'total_planned_tonnage': 0,
            'total_enrolled_partners': 0,
            'recent_activities': [],
            'key_metrics': {}
        }
        
        # Process scenarios
        for production in productions:
            status = production.status.value
            dashboard['scenarios_by_status'][status] = \
                dashboard['scenarios_by_status'].get(status, 0) + 1
            
            if production.status in [ProductionStatus.ACTIVE, ProductionStatus.PLANNED]:
                dashboard['total_planned_tonnage'] += production.total_planned_tonnage
                dashboard['total_enrolled_partners'] += len(production.enrolled_partners)
        
        # Active scenario details
        if active_production:
            dashboard['active_scenario'] = {
                'id': active_production.id,
                'name': active_production.scenario_name,
                'tonnage': active_production.total_planned_tonnage,
                'partners': len(active_production.enrolled_partners),
                'activated_at': active_production.activated_at.isoformat() if active_production.activated_at else None
            }
        
        # Key metrics
        dashboard['key_metrics'] = self._calculate_key_metrics(productions)
        
        return dashboard
    
    def _validate_scenario_dates(self, start_date: date, end_date: date) -> None:
        """Validate scenario date range."""
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")
        
        duration = (end_date - start_date).days
        if duration < 30:
            raise ValueError("Production scenario must span at least 30 days")
        
        if duration > 400:
            raise ValueError("Production scenario cannot span more than 400 days")
    
    def _validate_tonnage(self, tonnage: int) -> None:
        """Validate tonnage values."""
        if tonnage <= 0:
            raise ValueError("Tonnage must be positive")
        
        if tonnage > 100_000_000:  # 100 million tons seems reasonable as max
            raise ValueError("Tonnage value seems unreasonably high")
    
    def _validate_vessel_size(self, vessel_size: int) -> None:
        """Validate vessel size values."""
        if vessel_size <= 0:
            raise ValueError("Vessel size must be positive")
        
        if vessel_size > 500_000:  # 500k tons seems reasonable as max vessel size
            raise ValueError("Vessel size seems unreasonably large")
    
    def _validate_tonnage_allocation(self, production: Production) -> None:
        """Validate that tonnage allocation is reasonable."""
        total_minimum = sum(e.minimum_tonnage or 0 for e in production.enrolled_partners)
        
        if total_minimum > production.total_planned_tonnage * 1.2:
            raise ValueError(
                "Total minimum tonnage exceeds planned tonnage by more than 20%. "
                "This may indicate over-allocation."
            )
    
    def _validate_completion_requirements(self, production: Production) -> None:
        """Validate requirements for completing a production scenario."""
        # Check if end date has passed
        if production.end_date_contractual_year > date.today():
            raise ValueError("Cannot complete production scenario before end date")
        
        # Ensure all VLDs are processed (placeholder - would need VLD repository)
        # This would check that all vessel loading documents are in final status
        pass
    
    def _get_vessel_size_range(self, vessel_size: int) -> str:
        """Categorize vessel size into ranges."""
        if vessel_size < 50_000:
            return "Small (<50k)"
        elif vessel_size < 100_000:
            return "Medium (50k-100k)"
        elif vessel_size < 200_000:
            return "Large (100k-200k)"
        else:
            return "Very Large (>200k)"
    
    def _calculate_key_metrics(self, productions: List[Production]) -> Dict[str, Any]:
        """Calculate key performance metrics."""
        if not productions:
            return {}
        
        total_tonnage = sum(p.total_planned_tonnage for p in productions)
        total_partners = sum(len(p.enrolled_partners) for p in productions)
        
        return {
            'average_tonnage_per_scenario': total_tonnage / len(productions) if productions else 0,
            'average_partners_per_scenario': total_partners / len(productions) if productions else 0,
            'total_scenarios_created': len(productions),
            'completion_rate': len([p for p in productions if p.status == ProductionStatus.COMPLETED]) / len(productions) * 100
        }
    
    def _log_production_event(self, production: Production, event_type: str, **kwargs) -> None:
        """Log production events for audit trail."""
        # This would integrate with a logging system
        # For now, it's a placeholder for future implementation
        log_data = {
            'production_id': production.id,
            'scenario_name': production.scenario_name,
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        
        # In a real implementation, this would write to a log table or external system
        print(f"Production Event: {log_data}")  # Placeholder

