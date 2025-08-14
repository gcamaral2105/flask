"""
Vessel Repository
================

Specific repository for Vessel model with maritime and logistics-specific
queries and operations for the ERP Bauxita supply chain system.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import Session, joinedload

from app.lib.repository.base import BaseRepository
from app.models.vessel import Vessel, VesselStatus, VesselType
from app.models.partner import Partner


class VesselRepository(BaseRepository[Vessel]):
    """Repository for Vessel model with maritime-specific operations."""
    
    ENABLE_AUDIT = True
    ENABLE_SOFT_DELETE = True
    
    def __init__(self):
        super().__init__(Vessel)
    
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Vessel]:
        """Find vessels by multiple criteria."""
        return self.find_by_multiple_criteria(criteria)
    
    def get_by_name(self, name: str) -> Optional[Vessel]:
        """Get vessel by exact name."""
        return self.session.query(Vessel).filter(
            Vessel.name == name
        ).first()
    
    def get_by_imo(self, imo: str) -> Optional[Vessel]:
        """Get vessel by IMO number."""
        return self.session.query(Vessel).filter(
            Vessel.imo == imo
        ).first()
    
    def get_by_type(self, vessel_type: VesselType) -> List[Vessel]:
        """Get all vessels of a specific type."""
        query = self.session.query(Vessel).filter(Vessel.vtype == vessel_type)
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def get_by_status(self, status: VesselStatus) -> List[Vessel]:
        """Get all vessels with a specific status."""
        query = self.session.query(Vessel).filter(Vessel.status == status)
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def get_active_vessels(self) -> List[Vessel]:
        """Get all active vessels."""
        return self.get_by_status(VesselStatus.ACTIVE)
    
    def get_available_vessels(self) -> List[Vessel]:
        """Get vessels available for operations (active and not in maintenance)."""
        query = self.session.query(Vessel).filter(
            Vessel.status.in_([VesselStatus.ACTIVE, VesselStatus.INACTIVE])
        )
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def get_by_owner(self, partner_id: Union[int, str]) -> List[Vessel]:
        """Get all vessels owned by a specific partner."""
        query = self.session.query(Vessel).filter(Vessel.owner_partner_id == partner_id)
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def get_vessels_with_owner(self) -> List[Vessel]:
        """Get all vessels with their owner information loaded."""
        query = self.session.query(Vessel).options(joinedload(Vessel.owner_partner))
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def search_by_name(self, name_pattern: str) -> List[Vessel]:
        """Search vessels by name pattern."""
        query = self.session.query(Vessel).filter(
            Vessel.name.ilike(f'%{name_pattern}%')
        )
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def get_by_dwt_range(self, min_dwt: Optional[int] = None, 
                        max_dwt: Optional[int] = None) -> List[Vessel]:
        """Get vessels within a DWT (deadweight tonnage) range."""
        query = self.session.query(Vessel)
        
        conditions = []
        if min_dwt is not None:
            conditions.append(Vessel.dwt >= min_dwt)
        if max_dwt is not None:
            conditions.append(Vessel.dwt <= max_dwt)
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        
        return query.order_by(Vessel.dwt.desc()).all()
    
    def get_by_dimensions(self, min_loa: Optional[Decimal] = None,
                         max_loa: Optional[Decimal] = None,
                         min_beam: Optional[Decimal] = None,
                         max_beam: Optional[Decimal] = None) -> List[Vessel]:
        """Get vessels within specific dimension ranges."""
        query = self.session.query(Vessel)
        
        conditions = []
        if min_loa is not None:
            conditions.append(Vessel.loa >= min_loa)
        if max_loa is not None:
            conditions.append(Vessel.loa <= max_loa)
        if min_beam is not None:
            conditions.append(Vessel.beam >= min_beam)
        if max_beam is not None:
            conditions.append(Vessel.beam <= max_beam)
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        
        return query.order_by(Vessel.loa.desc()).all()
    
    def get_vessel_statistics(self) -> Dict[str, Any]:
        """Get comprehensive vessel statistics."""
        query = self.session.query(Vessel)
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        
        vessels = query.all()
        
        stats = {
            'total_vessels': len(vessels),
            'by_type': {},
            'by_status': {},
            'by_owner': {},
            'dwt_stats': {
                'total': 0,
                'average': 0,
                'min': None,
                'max': None
            },
            'vessels_with_imo': 0,
            'vessels_with_owner': 0
        }
        
        dwt_values = []
        
        for vessel in vessels:
            # Count by type
            if vessel.vtype:
                type_key = vessel.vtype.value
                stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
            
            # Count by status
            if vessel.status:
                status_key = vessel.status.value
                stats['by_status'][status_key] = stats['by_status'].get(status_key, 0) + 1
            
            # Count by owner
            if vessel.owner_partner_id:
                stats['vessels_with_owner'] += 1
                owner_key = f"Partner_{vessel.owner_partner_id}"
                stats['by_owner'][owner_key] = stats['by_owner'].get(owner_key, 0) + 1
            
            # IMO statistics
            if vessel.imo:
                stats['vessels_with_imo'] += 1
            
            # DWT statistics
            if vessel.dwt:
                dwt_values.append(vessel.dwt)
        
        # Calculate DWT statistics
        if dwt_values:
            stats['dwt_stats']['total'] = sum(dwt_values)
            stats['dwt_stats']['average'] = sum(dwt_values) / len(dwt_values)
            stats['dwt_stats']['min'] = min(dwt_values)
            stats['dwt_stats']['max'] = max(dwt_values)
        
        return stats
    
    def get_vessels_by_type_and_status(self, vessel_type: VesselType, 
                                     status: VesselStatus) -> List[Vessel]:
        """Get vessels filtered by both type and status."""
        query = self.session.query(Vessel).filter(
            and_(
                Vessel.vtype == vessel_type,
                Vessel.status == status
            )
        )
        if self.ENABLE_SOFT_DELETE:
            query = query.filter(Vessel.deleted_at.is_(None))
        return query.order_by(Vessel.name).all()
    
    def update_vessel_status(self, vessel_id: Union[int, str], 
                           new_status: VesselStatus) -> Optional[Vessel]:
        """Update vessel status with audit trail."""
        vessel = self.get_by_id(vessel_id)
        if not vessel:
            return None
        
        old_status = vessel.status
        vessel.status = new_status
        
        # Add audit information if available
        if self.ENABLE_AUDIT:
            vessel.update_audit_fields()
        
        self.session.commit()
        
        # Fire hook for status change
        self._fire("after_status_change", vessel, 
                  old_status=old_status, new_status=new_status)
        
        return vessel
    
    def set_maintenance_status(self, vessel_id: Union[int, str]) -> Optional[Vessel]:
        """Set vessel to maintenance status."""
        return self.update_vessel_status(vessel_id, VesselStatus.MAINTENANCE)
    
    def activate_vessel(self, vessel_id: Union[int, str]) -> Optional[Vessel]:
        """Activate a vessel for operations."""
        return self.update_vessel_status(vessel_id, VesselStatus.ACTIVE)
    
    def retire_vessel(self, vessel_id: Union[int, str]) -> Optional[Vessel]:
        """Retire a vessel from service."""
        return self.update_vessel_status(vessel_id, VesselStatus.RETIRED)
    
    def get_vessels_needing_maintenance(self) -> List[Vessel]:
        """Get vessels that might need maintenance (placeholder for future logic)."""
        # This is a placeholder - in a real system, this might check:
        # - Last maintenance date
        # - Operating hours
        # - Condition reports
        # For now, just return vessels in maintenance status
        return self.get_by_status(VesselStatus.MAINTENANCE)
    
    def assign_owner(self, vessel_id: Union[int, str], 
                    partner_id: Union[int, str]) -> Optional[Vessel]:
        """Assign an owner partner to a vessel."""
        vessel = self.get_by_id(vessel_id)
        if not vessel:
            return None
        
        old_owner_id = vessel.owner_partner_id
        vessel.owner_partner_id = partner_id
        
        if self.ENABLE_AUDIT:
            vessel.update_audit_fields()
        
        self.session.commit()
        
        # Fire hook for owner change
        self._fire("after_owner_change", vessel,
                  old_owner_id=old_owner_id, new_owner_id=partner_id)
        
        return vessel
    
    def remove_owner(self, vessel_id: Union[int, str]) -> Optional[Vessel]:
        """Remove owner assignment from a vessel."""
        return self.assign_owner(vessel_id, None)
    
    def get_fleet_by_owner(self, partner_id: Union[int, str]) -> Dict[str, Any]:
        """Get comprehensive fleet information for a specific owner."""
        vessels = self.get_by_owner(partner_id)
        
        fleet_info = {
            'owner_id': partner_id,
            'total_vessels': len(vessels),
            'by_type': {},
            'by_status': {},
            'total_dwt': 0,
            'vessels': []
        }
        
        for vessel in vessels:
            # Add to vessel list
            fleet_info['vessels'].append({
                'id': vessel.id,
                'name': vessel.name,
                'type': vessel.vtype.value if vessel.vtype else None,
                'status': vessel.status.value if vessel.status else None,
                'dwt': vessel.dwt
            })
            
            # Count by type
            if vessel.vtype:
                type_key = vessel.vtype.value
                fleet_info['by_type'][type_key] = fleet_info['by_type'].get(type_key, 0) + 1
            
            # Count by status
            if vessel.status:
                status_key = vessel.status.value
                fleet_info['by_status'][status_key] = fleet_info['by_status'].get(status_key, 0) + 1
            
            # Sum DWT
            if vessel.dwt:
                fleet_info['total_dwt'] += vessel.dwt
        
        return fleet_info

