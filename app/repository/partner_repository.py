"""
Partner Repository
=================

Specific repository for Partner model with business relationship-specific
queries and operations for the ERP Bauxita supply chain system.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Union
from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import Session, joinedload

from app.lib.repository.base import BaseRepository
from app.models.partner import Partner, PartnerEntity
from app.models.production import ProductionPartnerEnrollment


class PartnerRepository(BaseRepository[Partner]):
    """Repository for Partner model with business relationship operations."""
    
    ENABLE_AUDIT = True
    ENABLE_SOFT_DELETE = True
    
    def __init__(self):
        super().__init__(Partner)
    
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Partner]:
        """Find partners by multiple criteria."""
        return self.find_by_multiple_criteria(criteria)
    
    def get_by_name(self, name: str) -> Optional[Partner]:
        """Get partner by exact name."""
        return self.session.query(Partner).filter(
            Partner.name == name
        ).first()
    
    def search_by_name(self, name_pattern: str) -> List[Partner]:
        """Search partners by name pattern."""
        query = self.session.query(Partner).filter(
            Partner.name.ilike(f'%{name_pattern}%')
        )
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        return query.order_by(Partner.name).all()
    
    def get_by_entity_type(self, entity_type: str) -> List[Partner]:
        """Get partners by entity type (if entity_type field exists on Partner)."""
        # This assumes Partner has entity_type field directly
        # If not, it would need to join with PartnerEntity
        query = self.session.query(Partner)
        
        # Check if Partner has entity_type field directly
        if hasattr(Partner, 'entity_type'):
            query = query.filter(Partner.entity_type == entity_type)
        else:
            # Join with PartnerEntity if entity_type is in related table
            query = query.join(PartnerEntity, Partner.entity_id == PartnerEntity.id)
            query = query.filter(PartnerEntity.entity_type == entity_type)
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        return query.order_by(Partner.name).all()
    
    def get_halco_buyers(self) -> List[Partner]:
        """Get all HALCO buyer partners."""
        return self.get_by_entity_type('HALCO')
    
    def get_offtakers(self) -> List[Partner]:
        """Get all offtaker partners."""
        return self.get_by_entity_type('OFFTAKER')
    
    def get_vessel_owners(self) -> List[Partner]:
        """Get partners who own vessels."""
        from app.models.vessel import Vessel
        
        query = self.session.query(Partner).join(
            Vessel, Partner.id == Vessel.owner_partner_id
        ).distinct()
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        return query.order_by(Partner.name).all()
    
    def get_with_vessels(self) -> List[Partner]:
        """Get partners with their vessels loaded."""
        query = self.session.query(Partner).options(joinedload(Partner.vessels))
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        return query.order_by(Partner.name).all()
    
    def get_enrolled_in_production(self, production_id: Union[int, str]) -> List[Partner]:
        """Get all partners enrolled in a specific production."""
        query = self.session.query(Partner).join(
            ProductionPartnerEnrollment,
            Partner.id == ProductionPartnerEnrollment.partner_id
        ).filter(
            ProductionPartnerEnrollment.production_id == production_id
        )
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        return query.order_by(Partner.name).all()
    
    def get_production_enrollments(self, partner_id: Union[int, str]) -> List[ProductionPartnerEnrollment]:
        """Get all production enrollments for a specific partner."""
        return self.session.query(ProductionPartnerEnrollment).filter(
            ProductionPartnerEnrollment.partner_id == partner_id
        ).order_by(ProductionPartnerEnrollment.created_at.desc()).all()
    
    def get_active_production_partners(self) -> List[Partner]:
        """Get partners enrolled in active productions."""
        from app.models.production import Production, ProductionStatus
        
        query = self.session.query(Partner).join(
            ProductionPartnerEnrollment,
            Partner.id == ProductionPartnerEnrollment.partner_id
        ).join(
            Production,
            ProductionPartnerEnrollment.production_id == Production.id
        ).filter(
            Production.status == ProductionStatus.ACTIVE
        ).distinct()
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        return query.order_by(Partner.name).all()
    
    def get_partner_statistics(self) -> Dict[str, Any]:
        """Get comprehensive partner statistics."""
        query = self.session.query(Partner)
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        partners = query.all()
        
        stats = {
            'total_partners': len(partners),
            'by_entity_type': {},
            'with_vessels': 0,
            'enrolled_in_productions': 0,
            'active_partnerships': 0
        }
        
        # Count partners with vessels
        vessel_owners = self.get_vessel_owners()
        stats['with_vessels'] = len(vessel_owners)
        
        # Count partners enrolled in productions
        production_partners = self.get_active_production_partners()
        stats['enrolled_in_productions'] = len(production_partners)
        
        # Count by entity type (if available)
        for partner in partners:
            entity_type = None
            if hasattr(partner, 'entity_type') and partner.entity_type:
                entity_type = partner.entity_type
            elif hasattr(partner, 'entity') and partner.entity and hasattr(partner.entity, 'entity_type'):
                entity_type = partner.entity.entity_type
            
            if entity_type:
                type_key = str(entity_type)
                stats['by_entity_type'][type_key] = stats['by_entity_type'].get(type_key, 0) + 1
        
        return stats
    
    def get_partner_performance(self, partner_id: Union[int, str]) -> Dict[str, Any]:
        """Get performance metrics for a specific partner."""
        partner = self.get_by_id(partner_id)
        if not partner:
            return {}
        
        # Get production enrollments
        enrollments = self.get_production_enrollments(partner_id)
        
        # Get vessels owned
        vessels = []
        if hasattr(partner, 'vessels'):
            vessels = partner.vessels
        
        performance = {
            'partner_id': partner_id,
            'partner_name': partner.name,
            'total_enrollments': len(enrollments),
            'total_vessels_owned': len(vessels),
            'enrollments_by_year': {},
            'total_contracted_tonnage': 0,
            'vessel_types_owned': {}
        }
        
        # Analyze enrollments
        for enrollment in enrollments:
            if hasattr(enrollment, 'production') and enrollment.production:
                year = enrollment.production.contractual_year
                performance['enrollments_by_year'][year] = performance['enrollments_by_year'].get(year, 0) + 1
                
                # Sum contracted tonnage
                if enrollment.minimum_tonnage:
                    performance['total_contracted_tonnage'] += enrollment.minimum_tonnage
        
        # Analyze vessels
        for vessel in vessels:
            if hasattr(vessel, 'vtype') and vessel.vtype:
                vessel_type = vessel.vtype.value
                performance['vessel_types_owned'][vessel_type] = performance['vessel_types_owned'].get(vessel_type, 0) + 1
        
        return performance
    
    def create_partner_with_entity(self, partner_data: Dict[str, Any], 
                                 entity_data: Optional[Dict[str, Any]] = None) -> Partner:
        """Create a partner with associated entity information."""
        # Create entity first if provided
        entity_id = None
        if entity_data:
            entity = PartnerEntity(**entity_data)
            self.session.add(entity)
            self.session.flush()  # Get the ID without committing
            entity_id = entity.id
        
        # Create partner
        if entity_id:
            partner_data['entity_id'] = entity_id
        
        partner = self.create(**partner_data)
        return partner
    
    def update_partner_entity(self, partner_id: Union[int, str], 
                            entity_data: Dict[str, Any]) -> Optional[Partner]:
        """Update partner's entity information."""
        partner = self.get_by_id(partner_id)
        if not partner:
            return None
        
        # Update entity if it exists
        if hasattr(partner, 'entity') and partner.entity:
            for key, value in entity_data.items():
                if hasattr(partner.entity, key):
                    setattr(partner.entity, key, value)
        else:
            # Create new entity
            entity = PartnerEntity(**entity_data)
            self.session.add(entity)
            self.session.flush()
            partner.entity_id = entity.id
        
        if self.ENABLE_AUDIT:
            partner.update_audit_fields()
        
        self.session.commit()
        return partner
    
    def get_partners_by_contract_volume(self, min_volume: Optional[int] = None,
                                      max_volume: Optional[int] = None) -> List[Partner]:
        """Get partners filtered by their total contracted volume."""
        # This would require aggregating data from ProductionPartnerEnrollment
        query = self.session.query(Partner).join(
            ProductionPartnerEnrollment,
            Partner.id == ProductionPartnerEnrollment.partner_id
        )
        
        # Group by partner and sum minimum tonnage
        if min_volume is not None or max_volume is not None:
            subquery = self.session.query(
                ProductionPartnerEnrollment.partner_id,
                func.sum(ProductionPartnerEnrollment.minimum_tonnage).label('total_volume')
            ).group_by(ProductionPartnerEnrollment.partner_id).subquery()
            
            query = self.session.query(Partner).join(
                subquery, Partner.id == subquery.c.partner_id
            )
            
            if min_volume is not None:
                query = query.filter(subquery.c.total_volume >= min_volume)
            if max_volume is not None:
                query = query.filter(subquery.c.total_volume <= max_volume)
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Partner.deleted_at.is_(None))
        
        return query.distinct().order_by(Partner.name).all()
    
    def get_partnership_history(self, partner_id: Union[int, str]) -> Dict[str, Any]:
        """Get complete partnership history for a partner."""
        partner = self.get_by_id(partner_id)
        if not partner:
            return {}
        
        enrollments = self.get_production_enrollments(partner_id)
        
        history = {
            'partner_id': partner_id,
            'partner_name': partner.name,
            'first_enrollment': None,
            'last_enrollment': None,
            'total_years_active': 0,
            'years_enrolled': [],
            'total_contracted_tonnage': 0,
            'enrollment_details': []
        }
        
        years_set = set()
        
        for enrollment in enrollments:
            enrollment_detail = {
                'production_id': enrollment.production_id,
                'vessel_size_t': enrollment.vessel_size_t,
                'minimum_tonnage': enrollment.minimum_tonnage,
                'created_at': enrollment.created_at.isoformat() if enrollment.created_at else None
            }
            
            if hasattr(enrollment, 'production') and enrollment.production:
                enrollment_detail['year'] = enrollment.production.contractual_year
                enrollment_detail['scenario_name'] = enrollment.production.scenario_name
                years_set.add(enrollment.production.contractual_year)
            
            history['enrollment_details'].append(enrollment_detail)
            
            # Sum tonnage
            if enrollment.minimum_tonnage:
                history['total_contracted_tonnage'] += enrollment.minimum_tonnage
            
            # Track first/last enrollment dates
            if enrollment.created_at:
                if not history['first_enrollment'] or enrollment.created_at < history['first_enrollment']:
                    history['first_enrollment'] = enrollment.created_at.isoformat()
                if not history['last_enrollment'] or enrollment.created_at > history['last_enrollment']:
                    history['last_enrollment'] = enrollment.created_at.isoformat()
        
        history['years_enrolled'] = sorted(list(years_set))
        history['total_years_active'] = len(years_set)
        
        return history