"""
Production Repository
====================

Specific repository for Production model with business-specific queries
and operations for the ERP Bauxita supply chain system.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Any, List, Optional, Union
from sqlalchemy import and_, or_, desc, asc
from sqlalchemy.orm import Session

from app.lib.repository.base import BaseRepository
from app.models.production import Production, ProductionStatus, ProductionPartnerEnrollment
from app.models.partner import Partner


class ProductionRepository(BaseRepository[Production]):
    """Repository for Production model with business-specific operations."""
    
    ENABLE_AUDIT = True
    ENABLE_SOFT_DELETE = True
    
    def __init__(self):
        super().__init__(Production)
    
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Production]:
        """Find productions by multiple criteria."""
        return self.find_by_multiple_criteria(criteria)
    
    def get_by_year(self, year: int) -> List[Production]:
        """Get all productions for a specific contractual year."""
        return self.session.query(Production).filter(
            Production.contractual_year == year
        ).order_by(Production.scenario_name, Production.version.desc()).all()
    
    def get_active_by_year(self, year: int) -> Optional[Production]:
        """Get the active production for a specific year."""
        return self.session.query(Production).filter(
            and_(
                Production.contractual_year == year,
                Production.status == ProductionStatus.ACTIVE
            )
        ).first()
    
    def get_current_active(self) -> Optional[Production]:
        """Get the active production for the current year."""
        current_year = date.today().year
        return self.get_active_by_year(current_year)
    
    def get_by_status(self, status: ProductionStatus) -> List[Production]:
        """Get all productions with a specific status."""
        query = self.session.query(Production).filter(Production.status == status)
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Production.deleted_at.is_(None))
        return query.order_by(Production.contractual_year.desc()).all()
    
    def get_completed_productions(self, up_to_year: Optional[int] = None) -> List[Production]:
        """Get all completed productions up to a specific year."""
        cutoff_year = up_to_year or date.today().year
        return self.session.query(Production).filter(
            and_(
                Production.contractual_year < cutoff_year,
                Production.status == ProductionStatus.COMPLETED
            )
        ).order_by(
            Production.contractual_year.desc(),
            Production.scenario_name.asc(),
            Production.version.desc()
        ).all()
    
    def get_draft_scenarios(self, year: Optional[int] = None) -> List[Production]:
        """Get all draft scenarios, optionally filtered by year."""
        query = self.session.query(Production).filter(Production.status == ProductionStatus.DRAFT)
        if year:
            query = query.filter(Production.contractual_year == year)
        return query.order_by(Production.contractual_year.desc(), Production.scenario_name).all()
    
    def activate_scenario(self, production_id: Union[int, str]) -> Optional[Production]:
        """
        Activate a production scenario.
        Ensures only one active scenario per year by deactivating others.
        """
        production = self.get_by_id(production_id)
        if not production:
            return None
        
        # Deactivate any existing active scenario for the same year
        existing_active = self.get_active_by_year(production.contractual_year)
        if existing_active and existing_active.id != production.id:
            existing_active.status = ProductionStatus.PLANNED
            existing_active.activated_at = None
        
        # Activate the target scenario
        production.status = ProductionStatus.ACTIVE
        production.activated_at = datetime.utcnow()
        
        self.session.commit()
        return production
    
    def complete_scenario(self, production_id: Union[int, str]) -> Optional[Production]:
        """Mark a production scenario as completed."""
        production = self.get_by_id(production_id)
        if not production:
            return None
        
        production.status = ProductionStatus.COMPLETED
        production.completed_at = datetime.utcnow()
        
        self.session.commit()
        return production
    
    def create_scenario_copy(self, base_production_id: Union[int, str], 
                           new_scenario_name: str, 
                           new_year: Optional[int] = None) -> Optional[Production]:
        """Create a copy of an existing production scenario."""
        base_production = self.get_by_id(base_production_id)
        if not base_production:
            return None
        
        # Prepare data for the new scenario
        new_data = {
            'scenario_name': new_scenario_name,
            'scenario_description': f"Copy of {base_production.scenario_name}",
            'contractual_year': new_year or base_production.contractual_year,
            'total_planned_tonnage': base_production.total_planned_tonnage,
            'start_date_contractual_year': base_production.start_date_contractual_year,
            'end_date_contractual_year': base_production.end_date_contractual_year,
            'standard_moisture_content': base_production.standard_moisture_content,
            'base_scenario_id': base_production.id,
            'status': ProductionStatus.DRAFT
        }
        
        new_production = self.create(**new_data)
        
        # Copy partner enrollments
        for enrollment in base_production.enrolled_partners:
            enrollment_data = {
                'production_id': new_production.id,
                'partner_id': enrollment.partner_id,
                'vessel_size_t': enrollment.vessel_size_t,
                'minimum_tonnage': enrollment.minimum_tonnage,
                'adjusted_tonnage': enrollment.adjusted_tonnage,
                'manual_incentive_tonnage': enrollment.manual_incentive_tonnage,
                'calculated_incentive_tonnage': enrollment.calculated_incentive_tonnage
            }
            
            new_enrollment = ProductionPartnerEnrollment(**enrollment_data)
            self.session.add(new_enrollment)
        
        self.session.commit()
        return new_production
    
    def get_scenarios_by_base(self, base_scenario_id: Union[int, str]) -> List[Production]:
        """Get all scenarios derived from a base scenario."""
        return self.session.query(Production).filter(
            Production.base_scenario_id == base_scenario_id
        ).order_by(Production.version.desc()).all()
    
    def get_production_statistics(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Get production statistics for a specific year or all years."""
        query = self.session.query(Production)
        if year:
            query = query.filter(Production.contractual_year == year)
        
        productions = query.all()
        
        stats = {
            'total_scenarios': len(productions),
            'by_status': {},
            'total_planned_tonnage': 0,
            'years_covered': set(),
            'active_scenarios': 0
        }
        
        for prod in productions:
            # Count by status
            status_key = prod.status.value
            stats['by_status'][status_key] = stats['by_status'].get(status_key, 0) + 1
            
            # Sum tonnage for active/completed scenarios
            if prod.status in [ProductionStatus.ACTIVE, ProductionStatus.COMPLETED]:
                stats['total_planned_tonnage'] += prod.total_planned_tonnage
            
            # Track years
            stats['years_covered'].add(prod.contractual_year)
            
            # Count active scenarios
            if prod.status == ProductionStatus.ACTIVE:
                stats['active_scenarios'] += 1
        
        stats['years_covered'] = sorted(list(stats['years_covered']))
        return stats
    
    def search_by_name(self, name_pattern: str) -> List[Production]:
        """Search productions by scenario name pattern."""
        return self.session.query(Production).filter(
            Production.scenario_name.ilike(f'%{name_pattern}%')
        ).order_by(Production.contractual_year.desc(), Production.scenario_name).all()
    
    def get_productions_with_partner(self, partner_id: Union[int, str]) -> List[Production]:
        """Get all productions that have a specific partner enrolled."""
        return self.session.query(Production).join(
            ProductionPartnerEnrollment,
            Production.id == ProductionPartnerEnrollment.production_id
        ).filter(
            ProductionPartnerEnrollment.partner_id == partner_id
        ).distinct().order_by(Production.contractual_year.desc()).all()
    
    def get_partner_enrollment(self, production_id: Union[int, str], 
                             partner_id: Union[int, str]) -> Optional[ProductionPartnerEnrollment]:
        """Get specific partner enrollment for a production."""
        return self.session.query(ProductionPartnerEnrollment).filter(
            and_(
                ProductionPartnerEnrollment.production_id == production_id,
                ProductionPartnerEnrollment.partner_id == partner_id
            )
        ).first()
    
    def update_partner_enrollment(self, production_id: Union[int, str], 
                                partner_id: Union[int, str], 
                                **enrollment_data: Any) -> Optional[ProductionPartnerEnrollment]:
        """Update partner enrollment data."""
        enrollment = self.get_partner_enrollment(production_id, partner_id)
        if not enrollment:
            return None
        
        for key, value in enrollment_data.items():
            if hasattr(enrollment, key):
                setattr(enrollment, key, value)
        
        self.session.commit()
        return enrollment

