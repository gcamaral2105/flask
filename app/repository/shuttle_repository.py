"""
Shuttle Repository
=================

Repository for Shuttle and ShuttleOperation models with specialized operations 
for transloader vessel management.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload, selectinload

from app.lib.repository.base import BaseRepository
from app.models.shuttle import Shuttle, ShuttleStatus, ShuttleOperation, ShuttleOperationStatus
from app.models.vessel import Vessel, VesselType
from app.models.partner import Partner
from app.models.capesize import CapesizeVessel


class ShuttleRepository(BaseRepository[Shuttle]):
    """Repository for Shuttle operations."""
    
    def __init__(self):
        super().__init__(Shuttle)
    
    def get_active_shuttles(self) -> List[Shuttle]:
        """Get all active shuttle vessels."""
        return self.session.query(Shuttle).filter(
            Shuttle.status == ShuttleStatus.ACTIVE
        ).options(
            selectinload(Shuttle.vessel)
        ).all()
    
    def get_by_status(self, status: ShuttleStatus) -> List[Shuttle]:
        """Get shuttles by status."""
        return self.session.query(Shuttle).filter(
            Shuttle.status == status
        ).options(
            selectinload(Shuttle.vessel)
        ).all()
    
    def get_available_shuttles(self, date_from: Optional[datetime] = None,
                              date_to: Optional[datetime] = None) -> List[Shuttle]:
        """Get shuttles available for operations in a time window."""
        query = self.session.query(Shuttle).filter(
            Shuttle.status == ShuttleStatus.ACTIVE
        )
        
        if date_from and date_to:
            # Check for conflicting operations
            conflicting_ops = self.session.query(ShuttleOperation.shuttle_id).filter(
                and_(
                    or_(
                        and_(
                            ShuttleOperation.load_start_at <= date_to,
                            ShuttleOperation.return_at >= date_from
                        ),
                        and_(
                            ShuttleOperation.load_start_at <= date_to,
                            ShuttleOperation.return_at.is_(None),
                            ShuttleOperation.load_start_at >= date_from
                        )
                    ),
                    ShuttleOperation.discharge_end_at.is_(None)  # Not completed
                )
            ).subquery()
            
            query = query.filter(
                ~Shuttle.id.in_(conflicting_ops)
            )
        
        return query.options(selectinload(Shuttle.vessel)).all()
    
    def get_by_vessel_name(self, vessel_name: str) -> Optional[Shuttle]:
        """Get shuttle by vessel name."""
        return self.session.query(Shuttle).join(Vessel).filter(
            Vessel.name.ilike(f"%{vessel_name}%")
        ).options(selectinload(Shuttle.vessel)).first()
    
    def get_alcoa_shuttles(self) -> List[Shuttle]:
        """Get shuttles operated by Alcoa (CSL Argosy and CSL Acadian)."""
        return self.session.query(Shuttle).join(Vessel).filter(
            Vessel.name.in_(['CSL Argosy', 'CSL Acadian'])
        ).options(selectinload(Shuttle.vessel)).all()
    
    def get_shuttle_statistics(self, start_date: Optional[date] = None,
                              end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get shuttle fleet statistics."""
        total_shuttles = self.session.query(Shuttle).count()
        
        status_distribution = self.session.query(
            Shuttle.status,
            func.count(Shuttle.id).label('count')
        ).group_by(Shuttle.status).all()
        
        # Operations statistics
        ops_query = self.session.query(ShuttleOperation)
        if start_date and end_date:
            ops_query = ops_query.filter(
                and_(
                    ShuttleOperation.load_start_at >= start_date,
                    ShuttleOperation.load_start_at <= end_date
                )
            )
        
        total_operations = ops_query.count()
        completed_operations = ops_query.filter(
            ShuttleOperation.discharge_end_at.isnot(None)
        ).count()
        
        # Volume statistics
        volume_stats = ops_query.filter(
            ShuttleOperation.volume.isnot(None)
        ).with_entities(
            func.sum(ShuttleOperation.volume).label('total_volume'),
            func.avg(ShuttleOperation.volume).label('avg_volume'),
            func.count(ShuttleOperation.id).label('ops_with_volume')
        ).first()
        
        return {
            'fleet_size': total_shuttles,
            'status_distribution': {
                status.value: count for status, count in status_distribution
            },
            'operations': {
                'total_operations': total_operations,
                'completed_operations': completed_operations,
                'completion_rate': completed_operations / total_operations * 100 if total_operations else 0
            },
            'volume': {
                'total_volume': int(volume_stats.total_volume) if volume_stats.total_volume else 0,
                'average_volume': float(volume_stats.avg_volume) if volume_stats.avg_volume else 0,
                'operations_with_volume': volume_stats.ops_with_volume or 0
            }
        }
    
    def get_maintenance_schedule(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Get upcoming maintenance windows for shuttles."""
        end_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        maintenance_windows = self.session.query(Shuttle).join(
            Shuttle.maintenance_windows
        ).filter(
            and_(
                Shuttle.maintenance_windows.any(),
                # Add maintenance window date filters here when model is available
            )
        ).all()
        
        return [
            {
                'shuttle_id': shuttle.id,
                'vessel_name': shuttle.vessel.name if shuttle.vessel else None,
                'maintenance_windows': [
                    # Serialize maintenance windows
                    window.to_dict() if hasattr(window, 'to_dict') else str(window)
                    for window in shuttle.maintenance_windows
                ]
            }
            for shuttle in maintenance_windows
        ]


class ShuttleOperationRepository(BaseRepository[ShuttleOperation]):
    """Repository for ShuttleOperation operations."""
    
    def __init__(self):
        super().__init__(ShuttleOperation)
    
    def get_active_operations(self) -> List[ShuttleOperation]:
        """Get currently active shuttle operations."""
        return self.session.query(ShuttleOperation).filter(
            and_(
                ShuttleOperation.load_start_at.isnot(None),
                ShuttleOperation.discharge_end_at.is_(None)
            )
        ).options(
            selectinload(ShuttleOperation.shuttle),
            selectinload(ShuttleOperation.cape_vessel),
            selectinload(ShuttleOperation.loading_lineup)
        ).order_by(ShuttleOperation.load_start_at.desc()).all()
    
    def get_by_shuttle(self, shuttle_id: int,
                      start_date: Optional[date] = None,
                      end_date: Optional[date] = None) -> List[ShuttleOperation]:
        """Get operations for a specific shuttle."""
        query = self.session.query(ShuttleOperation).filter(
            ShuttleOperation.shuttle_id == shuttle_id
        )
        
        if start_date:
            query = query.filter(
                ShuttleOperation.load_start_at >= start_date
            )
        
        if end_date:
            query = query.filter(
                ShuttleOperation.load_start_at <= end_date
            )
        
        return query.options(
            selectinload(ShuttleOperation.cape_vessel),
            selectinload(ShuttleOperation.loading_lineup)
        ).order_by(desc(ShuttleOperation.load_start_at)).all()
    
    def get_by_capesize_vessel(self, cape_vessel_name: str) -> List[ShuttleOperation]:
        """Get operations for a specific capesize vessel."""
        return self.session.query(ShuttleOperation).filter(
            ShuttleOperation.cape_vessel_name.ilike(f"%{cape_vessel_name}%")
        ).options(
            selectinload(ShuttleOperation.shuttle),
            selectinload(ShuttleOperation.cape_vessel)
        ).order_by(desc(ShuttleOperation.load_start_at)).all()
    
    def get_completed_operations(self, start_date: date, end_date: date) -> List[ShuttleOperation]:
        """Get completed operations in a date range."""
        return self.session.query(ShuttleOperation).filter(
            and_(
                ShuttleOperation.discharge_end_at.isnot(None),
                ShuttleOperation.discharge_end_at >= start_date,
                ShuttleOperation.discharge_end_at <= end_date
            )
        ).options(
            selectinload(ShuttleOperation.shuttle),
            selectinload(ShuttleOperation.cape_vessel)
        ).order_by(ShuttleOperation.discharge_end_at.desc()).all()
    
    def get_sublet_operations(self, partner_id: Optional[int] = None) -> List[ShuttleOperation]:
        """Get sublet operations, optionally filtered by partner."""
        query = self.session.query(ShuttleOperation).filter(
            ShuttleOperation.is_sublet == True
        )
        
        if partner_id:
            query = query.filter(
                ShuttleOperation.sublet_partner_id == partner_id
            )
        
        return query.options(
            selectinload(ShuttleOperation.shuttle),
            selectinload(ShuttleOperation.sublet_partner)
        ).order_by(desc(ShuttleOperation.load_start_at)).all()
    
    def get_operations_by_vld(self, vld_id: int) -> List[ShuttleOperation]:
        """Get operations associated with a specific VLD."""
        return self.session.query(ShuttleOperation).filter(
            or_(
                ShuttleOperation.loading_vld_id == vld_id,
                ShuttleOperation.sublet_vld_id == vld_id
            )
        ).options(
            selectinload(ShuttleOperation.shuttle),
            selectinload(ShuttleOperation.loading_vld),
            selectinload(ShuttleOperation.sublet_vld)
        ).all()
    
    def create_operation(self, shuttle_id: int, cape_vessel_name: str,
                        loading_lineup_id: Optional[int] = None,
                        cape_vessel_id: Optional[int] = None,
                        **kwargs) -> ShuttleOperation:
        """Create a new shuttle operation."""
        operation = ShuttleOperation(
            shuttle_id=shuttle_id,
            cape_vessel_name=cape_vessel_name,
            loading_lineup_id=loading_lineup_id,
            cape_vessel_id=cape_vessel_id,
            **kwargs
        )
        
        self.session.add(operation)
        self.session.commit()
        return operation
    
    def start_loading(self, operation_id: int) -> Optional[ShuttleOperation]:
        """Mark operation as started loading."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return None
        
        operation.load_start_at = datetime.utcnow()
        self.session.commit()
        return operation
    
    def complete_loading(self, operation_id: int, volume: Optional[int] = None) -> Optional[ShuttleOperation]:
        """Mark loading as completed."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return None
        
        operation.load_end_at = datetime.utcnow()
        if volume:
            operation.volume = volume
        
        self.session.commit()
        return operation
    
    def start_transit(self, operation_id: int) -> Optional[ShuttleOperation]:
        """Mark operation as in transit."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return None
        
        operation.sail_out_at = datetime.utcnow()
        self.session.commit()
        return operation
    
    def start_discharge(self, operation_id: int) -> Optional[ShuttleOperation]:
        """Mark discharge as started."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return None
        
        operation.discharge_start_at = datetime.utcnow()
        self.session.commit()
        return operation
    
    def complete_discharge(self, operation_id: int) -> Optional[ShuttleOperation]:
        """Mark discharge as completed."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return None
        
        operation.discharge_end_at = datetime.utcnow()
        self.session.commit()
        return operation
    
    def complete_operation(self, operation_id: int) -> Optional[ShuttleOperation]:
        """Mark entire operation as completed (shuttle returned)."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return None
        
        operation.return_at = datetime.utcnow()
        self.session.commit()
        return operation
    
    def create_sublet_operation(self, shuttle_id: int, cape_vessel_name: str,
                               sublet_partner_id: int, sublet_vld_id: int,
                               **kwargs) -> ShuttleOperation:
        """Create a sublet operation."""
        operation = ShuttleOperation(
            shuttle_id=shuttle_id,
            cape_vessel_name=cape_vessel_name,
            sublet_partner_id=sublet_partner_id,
            sublet_vld_id=sublet_vld_id,
            is_sublet=True,
            **kwargs
        )
        
        self.session.add(operation)
        self.session.commit()
        return operation
    
    def get_operation_performance(self, operation_id: int) -> Dict[str, Any]:
        """Calculate performance metrics for a specific operation."""
        operation = self.get_by_id(operation_id)
        if not operation:
            return {}
        
        metrics = {
            'operation_id': operation_id,
            'shuttle_name': operation.shuttle.vessel.name if operation.shuttle and operation.shuttle.vessel else None,
            'cape_vessel_name': operation.cape_vessel_name,
            'volume': operation.volume,
            'is_sublet': operation.is_sublet
        }
        
        # Calculate durations
        if operation.load_start_at and operation.load_end_at:
            loading_duration = (operation.load_end_at - operation.load_start_at).total_seconds() / 3600
            metrics['loading_hours'] = round(loading_duration, 2)
        
        if operation.sail_out_at and operation.discharge_start_at:
            transit_duration = (operation.discharge_start_at - operation.sail_out_at).total_seconds() / 3600
            metrics['transit_hours'] = round(transit_duration, 2)
        
        if operation.discharge_start_at and operation.discharge_end_at:
            discharge_duration = (operation.discharge_end_at - operation.discharge_start_at).total_seconds() / 3600
            metrics['discharge_hours'] = round(discharge_duration, 2)
        
        if operation.load_start_at and operation.return_at:
            total_duration = (operation.return_at - operation.load_start_at).total_seconds() / 3600
            metrics['total_cycle_hours'] = round(total_duration, 2)
        
        # Calculate rates
        if operation.volume and 'loading_hours' in metrics and metrics['loading_hours'] > 0:
            metrics['loading_rate_tph'] = round(operation.volume / metrics['loading_hours'], 1)
        
        if operation.volume and 'discharge_hours' in metrics and metrics['discharge_hours'] > 0:
            metrics['discharge_rate_tph'] = round(operation.volume / metrics['discharge_hours'], 1)
        
        return metrics
    
    def get_shuttle_utilization(self, shuttle_id: int, 
                               start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate shuttle utilization for a period."""
        operations = self.get_by_shuttle(shuttle_id, start_date, end_date)
        
        total_period_hours = (end_date - start_date).days * 24
        operational_hours = 0
        
        for operation in operations:
            if operation.load_start_at and operation.return_at:
                # Ensure dates are within the period
                start = max(operation.load_start_at.date(), start_date)
                end = min(operation.return_at.date(), end_date)
                
                if start <= end:
                    duration = (operation.return_at - operation.load_start_at).total_seconds() / 3600
                    operational_hours += duration
        
        utilization_pct = (operational_hours / total_period_hours * 100) if total_period_hours > 0 else 0
        
        return {
            'shuttle_id': shuttle_id,
            'period_days': (end_date - start_date).days,
            'total_operations': len(operations),
            'operational_hours': round(operational_hours, 2),
            'total_period_hours': total_period_hours,
            'utilization_percentage': round(utilization_pct, 2),
            'total_volume': sum(op.volume for op in operations if op.volume)
        }
    
    def get_capesize_completion_analysis(self, cape_vessel_name: str) -> Dict[str, Any]:
        """Analyze how many shuttles were needed to complete a capesize vessel."""
        operations = self.get_by_capesize_vessel(cape_vessel_name)
        
        if not operations:
            return {}
        
        completed_ops = [op for op in operations if op.discharge_end_at]
        total_volume = sum(op.volume for op in completed_ops if op.volume)
        
        # Group by time proximity to identify loading sessions
        loading_sessions = []
        if completed_ops:
            completed_ops.sort(key=lambda x: x.load_start_at or datetime.min)
            
            current_session = [completed_ops[0]]
            for op in completed_ops[1:]:
                # If operations are within 48 hours, consider them part of same loading session
                if (op.load_start_at and current_session[-1].load_start_at and 
                    (op.load_start_at - current_session[-1].load_start_at).days <= 2):
                    current_session.append(op)
                else:
                    loading_sessions.append(current_session)
                    current_session = [op]
            
            if current_session:
                loading_sessions.append(current_session)
        
        return {
            'cape_vessel_name': cape_vessel_name,
            'total_operations': len(operations),
            'completed_operations': len(completed_ops),
            'total_volume': total_volume,
            'loading_sessions': len(loading_sessions),
            'average_shuttles_per_session': len(completed_ops) / len(loading_sessions) if loading_sessions else 0,
            'sessions_detail': [
                {
                    'session_number': i + 1,
                    'shuttles_used': len(session),
                    'total_volume': sum(op.volume for op in session if op.volume),
                    'start_date': min(op.load_start_at for op in session if op.load_start_at).date(),
                    'end_date': max(op.discharge_end_at for op in session if op.discharge_end_at).date()
                }
                for i, session in enumerate(loading_sessions)
            ]
        }

