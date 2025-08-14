"""
Capesize Repository
==================

Repository for CapesizeVessel model with specialized operations for 
capesize vessel management and transloader operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload, selectinload

from app.lib.repository.base import BaseRepository
from app.models.capesize import CapesizeVessel, CapesizeStatus
from app.models.partner import Partner
from app.models.vessel import Vessel
from app.models.shuttle import ShuttleOperation


class CapesizeRepository(BaseRepository[CapesizeVessel]):
    """Repository for CapesizeVessel operations."""
    
    def __init__(self):
        super().__init__(CapesizeVessel)
    
    def get_active_operations(self) -> List[CapesizeVessel]:
        """Get active capesize operations (not completed or departed)."""
        return self.session.query(CapesizeVessel).filter(
            CapesizeVessel.status.in_([
                CapesizeStatus.SCHEDULED,
                CapesizeStatus.ARRIVED,
                CapesizeStatus.LOADING
            ])
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel),
            selectinload(CapesizeVessel.product)
        ).order_by(CapesizeVessel.ata_anchorage.asc()).all()
    
    def get_by_status(self, status: CapesizeStatus) -> List[CapesizeVessel]:
        """Get capesize vessels by status."""
        return self.session.query(CapesizeVessel).filter(
            CapesizeVessel.status == status
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel)
        ).order_by(CapesizeVessel.ata_anchorage.desc()).all()
    
    def get_by_partner(self, partner_id: int) -> List[CapesizeVessel]:
        """Get capesize operations for a specific partner."""
        return self.session.query(CapesizeVessel).filter(
            CapesizeVessel.partner_id == partner_id
        ).options(
            selectinload(CapesizeVessel.cape_vessel),
            selectinload(CapesizeVessel.product)
        ).order_by(desc(CapesizeVessel.ata_anchorage)).all()
    
    def get_by_layday_period(self, start_date: date, end_date: date) -> List[CapesizeVessel]:
        """Get capesize vessels with laydays in the specified period."""
        return self.session.query(CapesizeVessel).filter(
            or_(
                and_(
                    CapesizeVessel.layday_start >= start_date,
                    CapesizeVessel.layday_start <= end_date
                ),
                and_(
                    CapesizeVessel.layday_end >= start_date,
                    CapesizeVessel.layday_end <= end_date
                ),
                and_(
                    CapesizeVessel.layday_start <= start_date,
                    CapesizeVessel.layday_end >= end_date
                )
            )
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel)
        ).order_by(CapesizeVessel.layday_start.asc()).all()
    
    def get_awaiting_shuttles(self) -> List[CapesizeVessel]:
        """Get capesize vessels waiting for shuttle operations."""
        return self.session.query(CapesizeVessel).filter(
            and_(
                CapesizeVessel.status.in_([
                    CapesizeStatus.ARRIVED,
                    CapesizeStatus.LOADING
                ]),
                CapesizeVessel.current_tonnage < CapesizeVessel.target_tonnage
            )
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel),
            selectinload(CapesizeVessel.cycles)
        ).order_by(CapesizeVessel.ata_anchorage.asc()).all()
    
    def get_completed_in_period(self, start_date: date, end_date: date) -> List[CapesizeVessel]:
        """Get completed capesize operations in a period."""
        return self.session.query(CapesizeVessel).filter(
            and_(
                CapesizeVessel.status.in_([
                    CapesizeStatus.COMPLETED,
                    CapesizeStatus.DEPARTED
                ]),
                CapesizeVessel.departure_anchorage >= start_date,
                CapesizeVessel.departure_anchorage <= end_date
            )
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel)
        ).order_by(CapesizeVessel.departure_anchorage.desc()).all()
    
    def get_overdue_vessels(self) -> List[CapesizeVessel]:
        """Get vessels that are overdue (past layday end but not arrived)."""
        today = date.today()
        return self.session.query(CapesizeVessel).filter(
            and_(
                CapesizeVessel.layday_end < today,
                CapesizeVessel.status == CapesizeStatus.SCHEDULED
            )
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel)
        ).order_by(CapesizeVessel.layday_end.asc()).all()
    
    def get_upcoming_arrivals(self, days_ahead: int = 7) -> List[CapesizeVessel]:
        """Get vessels expected to arrive in the next N days."""
        end_date = date.today() + timedelta(days=days_ahead)
        
        return self.session.query(CapesizeVessel).filter(
            and_(
                CapesizeVessel.layday_start <= end_date,
                CapesizeVessel.layday_end >= date.today(),
                CapesizeVessel.status == CapesizeStatus.SCHEDULED
            )
        ).options(
            selectinload(CapesizeVessel.partner),
            selectinload(CapesizeVessel.cape_vessel)
        ).order_by(CapesizeVessel.layday_start.asc()).all()
    
    def create_capesize_operation(self, partner_id: int, target_tonnage: int,
                                 layday_start: date, layday_end: date,
                                 ata_anchorage: datetime, product_id: int,
                                 cape_vessel_id: Optional[int] = None,
                                 **kwargs) -> CapesizeVessel:
        """Create a new capesize operation."""
        capesize = CapesizeVessel(
            partner_id=partner_id,
            target_tonnage=target_tonnage,
            layday_start=layday_start,
            layday_end=layday_end,
            ata_anchorage=ata_anchorage,
            product_id=product_id,
            cape_vessel_id=cape_vessel_id,
            current_tonnage=0,
            status=CapesizeStatus.SCHEDULED,
            **kwargs
        )
        
        self.session.add(capesize)
        self.session.commit()
        return capesize
    
    def update_status(self, capesize_id: int, new_status: CapesizeStatus) -> Optional[CapesizeVessel]:
        """Update capesize vessel status."""
        capesize = self.get_by_id(capesize_id)
        if not capesize:
            return None
        
        capesize.status = new_status
        
        # Auto-update timestamps based on status
        if new_status == CapesizeStatus.ARRIVED and not capesize.ata_anchorage:
            capesize.ata_anchorage = datetime.utcnow()
        elif new_status == CapesizeStatus.DEPARTED and not capesize.departure_anchorage:
            capesize.departure_anchorage = datetime.utcnow()
        
        self.session.commit()
        return capesize
    
    def add_tonnage(self, capesize_id: int, tonnage: int) -> Optional[CapesizeVessel]:
        """Add tonnage to a capesize vessel from shuttle operation."""
        capesize = self.get_by_id(capesize_id)
        if not capesize:
            return None
        
        capesize.current_tonnage += tonnage
        
        # Auto-complete if target reached
        if capesize.current_tonnage >= capesize.target_tonnage:
            capesize.status = CapesizeStatus.COMPLETED
        
        self.session.commit()
        return capesize
    
    def get_loading_progress(self, capesize_id: int) -> Dict[str, Any]:
        """Get detailed loading progress for a capesize vessel."""
        capesize = self.get_by_id(capesize_id)
        if not capesize:
            return {}
        
        # Get associated shuttle operations
        shuttle_ops = self.session.query(ShuttleOperation).filter(
            ShuttleOperation.cape_operation_id == capesize_id
        ).options(
            selectinload(ShuttleOperation.shuttle)
        ).order_by(ShuttleOperation.load_start_at.asc()).all()
        
        completed_volume = sum(
            op.volume for op in shuttle_ops 
            if op.volume and op.discharge_end_at
        )
        
        in_progress_volume = sum(
            op.volume for op in shuttle_ops 
            if op.volume and op.load_start_at and not op.discharge_end_at
        )
        
        progress_pct = (completed_volume / capesize.target_tonnage * 100) if capesize.target_tonnage > 0 else 0
        
        return {
            'capesize_id': capesize_id,
            'vessel_name': capesize.cape_vessel.name if capesize.cape_vessel else None,
            'partner': capesize.partner.name if capesize.partner else None,
            'target_tonnage': capesize.target_tonnage,
            'current_tonnage': capesize.current_tonnage,
            'completed_volume': completed_volume,
            'in_progress_volume': in_progress_volume,
            'remaining_tonnage': max(0, capesize.target_tonnage - completed_volume),
            'progress_percentage': round(progress_pct, 2),
            'shuttle_operations': len(shuttle_ops),
            'completed_operations': len([op for op in shuttle_ops if op.discharge_end_at]),
            'status': capesize.status.value,
            'operations_detail': [
                {
                    'operation_id': op.id,
                    'shuttle_name': op.shuttle.vessel.name if op.shuttle and op.shuttle.vessel else None,
                    'volume': op.volume,
                    'load_start': op.load_start_at.isoformat() if op.load_start_at else None,
                    'discharge_end': op.discharge_end_at.isoformat() if op.discharge_end_at else None,
                    'completed': bool(op.discharge_end_at)
                }
                for op in shuttle_ops
            ]
        }
    
    def get_capesize_statistics(self, start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get capesize operations statistics."""
        query = self.session.query(CapesizeVessel)
        
        if start_date and end_date:
            query = query.filter(
                or_(
                    and_(
                        CapesizeVessel.ata_anchorage >= start_date,
                        CapesizeVessel.ata_anchorage <= end_date
                    ),
                    and_(
                        CapesizeVessel.departure_anchorage >= start_date,
                        CapesizeVessel.departure_anchorage <= end_date
                    )
                )
            )
        
        total_operations = query.count()
        
        # Status distribution
        status_stats = query.with_entities(
            CapesizeVessel.status,
            func.count(CapesizeVessel.id).label('count')
        ).group_by(CapesizeVessel.status).all()
        
        # Tonnage statistics
        tonnage_stats = query.with_entities(
            func.sum(CapesizeVessel.target_tonnage).label('total_target'),
            func.sum(CapesizeVessel.current_tonnage).label('total_current'),
            func.avg(CapesizeVessel.target_tonnage).label('avg_target'),
            func.avg(CapesizeVessel.current_tonnage).label('avg_current')
        ).first()
        
        # Completion statistics
        completed_ops = query.filter(
            CapesizeVessel.status.in_([
                CapesizeStatus.COMPLETED,
                CapesizeStatus.DEPARTED
            ])
        ).all()
        
        # Calculate average loading time for completed operations
        loading_times = []
        for op in completed_ops:
            if op.ata_anchorage and op.departure_anchorage:
                duration = (op.departure_anchorage - op.ata_anchorage).total_seconds() / 3600
                loading_times.append(duration)
        
        avg_loading_time = sum(loading_times) / len(loading_times) if loading_times else 0
        
        return {
            'total_operations': total_operations,
            'status_distribution': {
                status.value: count for status, count in status_stats
            },
            'tonnage': {
                'total_target': int(tonnage_stats.total_target) if tonnage_stats.total_target else 0,
                'total_current': int(tonnage_stats.total_current) if tonnage_stats.total_current else 0,
                'average_target': float(tonnage_stats.avg_target) if tonnage_stats.avg_target else 0,
                'average_current': float(tonnage_stats.avg_current) if tonnage_stats.avg_current else 0,
                'completion_rate': (tonnage_stats.total_current / tonnage_stats.total_target * 100) 
                                 if tonnage_stats.total_target else 0
            },
            'performance': {
                'completed_operations': len(completed_ops),
                'completion_rate': len(completed_ops) / total_operations * 100 if total_operations else 0,
                'average_loading_hours': round(avg_loading_time, 2)
            }
        }
    
    def get_partner_capesize_summary(self, partner_id: int,
                                    start_date: Optional[date] = None,
                                    end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get capesize operations summary for a specific partner."""
        query = self.session.query(CapesizeVessel).filter(
            CapesizeVessel.partner_id == partner_id
        )
        
        if start_date and end_date:
            query = query.filter(
                and_(
                    CapesizeVessel.ata_anchorage >= start_date,
                    CapesizeVessel.ata_anchorage <= end_date
                )
            )
        
        operations = query.all()
        
        total_target = sum(op.target_tonnage for op in operations)
        total_current = sum(op.current_tonnage for op in operations)
        completed_ops = [op for op in operations if op.status in [
            CapesizeStatus.COMPLETED, CapesizeStatus.DEPARTED
        ]]
        
        return {
            'partner_id': partner_id,
            'total_operations': len(operations),
            'completed_operations': len(completed_ops),
            'completion_rate': len(completed_ops) / len(operations) * 100 if operations else 0,
            'tonnage': {
                'total_target': total_target,
                'total_loaded': total_current,
                'achievement_rate': total_current / total_target * 100 if total_target else 0
            },
            'average_vessel_size': total_target / len(operations) if operations else 0
        }
    
    def get_anchorage_queue(self) -> List[Dict[str, Any]]:
        """Get current anchorage queue with waiting times."""
        active_operations = self.get_active_operations()
        
        queue = []
        for op in active_operations:
            waiting_time = None
            if op.ata_anchorage and op.status == CapesizeStatus.ARRIVED:
                waiting_time = (datetime.utcnow() - op.ata_anchorage).total_seconds() / 3600
            
            queue.append({
                'capesize_id': op.id,
                'vessel_name': op.cape_vessel.name if op.cape_vessel else 'TBN',
                'partner': op.partner.name if op.partner else None,
                'status': op.status.value,
                'target_tonnage': op.target_tonnage,
                'current_tonnage': op.current_tonnage,
                'progress_percentage': (op.current_tonnage / op.target_tonnage * 100) if op.target_tonnage > 0 else 0,
                'ata_anchorage': op.ata_anchorage.isoformat() if op.ata_anchorage else None,
                'waiting_hours': round(waiting_time, 2) if waiting_time else None,
                'layday_start': op.layday_start.isoformat(),
                'layday_end': op.layday_end.isoformat()
            })
        
        return sorted(queue, key=lambda x: x['ata_anchorage'] or '9999-12-31')
    
    def estimate_completion_time(self, capesize_id: int) -> Optional[Dict[str, Any]]:
        """Estimate completion time for a capesize operation."""
        capesize = self.get_by_id(capesize_id)
        if not capesize:
            return None
        
        remaining_tonnage = capesize.target_tonnage - capesize.current_tonnage
        if remaining_tonnage <= 0:
            return {
                'capesize_id': capesize_id,
                'status': 'completed',
                'remaining_tonnage': 0
            }
        
        # Get historical shuttle performance
        avg_shuttle_volume = self.session.query(
            func.avg(ShuttleOperation.volume)
        ).filter(
            and_(
                ShuttleOperation.volume.isnot(None),
                ShuttleOperation.discharge_end_at.isnot(None)
            )
        ).scalar() or 15000  # Default assumption
        
        avg_cycle_time = self.session.query(
            func.avg(
                func.extract('epoch', 
                    ShuttleOperation.return_at - ShuttleOperation.load_start_at) / 3600
            )
        ).filter(
            and_(
                ShuttleOperation.load_start_at.isnot(None),
                ShuttleOperation.return_at.isnot(None)
            )
        ).scalar() or 24  # Default 24 hours per cycle
        
        # Estimate shuttles needed
        shuttles_needed = max(1, round(remaining_tonnage / avg_shuttle_volume))
        
        # Estimate time (assuming sequential operations for simplicity)
        estimated_hours = shuttles_needed * avg_cycle_time
        estimated_completion = datetime.utcnow() + timedelta(hours=estimated_hours)
        
        return {
            'capesize_id': capesize_id,
            'remaining_tonnage': remaining_tonnage,
            'estimated_shuttles_needed': shuttles_needed,
            'estimated_hours': round(estimated_hours, 1),
            'estimated_completion': estimated_completion.isoformat(),
            'assumptions': {
                'average_shuttle_volume': avg_shuttle_volume,
                'average_cycle_hours': avg_cycle_time
            }
        }

