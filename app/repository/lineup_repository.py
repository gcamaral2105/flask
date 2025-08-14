"""
Lineup Repository
================

Repository for Lineup model with specialized operations for CBG line-up management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload, selectinload

from app.lib.repository.base import BaseRepository
from app.models.lineup import Lineup, LineupStatus
from app.models.vld import VLD
from app.models.partner import Partner
from app.models.berth import Berth
from app.models.vessel import Vessel


class LineupRepository(BaseRepository[Lineup]):
    """Repository for Lineup operations."""
    
    def __init__(self):
        super().__init__(Lineup)
    
    def get_current_lineup(self, limit: int = 50) -> List[Lineup]:
        """Get current lineup ordered by ETA/ETB."""
        return self.session.query(Lineup).filter(
            Lineup.status.in_([
                LineupStatus.SCHEDULED,
                LineupStatus.ETA_RECEIVED,
                LineupStatus.ARRIVED,
                LineupStatus.NOR_TENDERED,
                LineupStatus.BERTHED,
                LineupStatus.LOADING
            ])
        ).order_by(
            Lineup.eta.asc().nullslast(),
            Lineup.etb.asc().nullslast()
        ).limit(limit).all()
    
    def get_by_status(self, status: LineupStatus) -> List[Lineup]:
        """Get lineups by status."""
        return self.session.query(Lineup).filter(
            Lineup.status == status
        ).order_by(Lineup.eta.asc().nullslast()).all()
    
    def get_by_partner(self, partner_id: int) -> List[Lineup]:
        """Get lineups for a specific partner."""
        return self.session.query(Lineup).filter(
            Lineup.partner_id == partner_id
        ).order_by(desc(Lineup.eta)).all()
    
    def get_by_berth(self, berth_id: int, 
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None) -> List[Lineup]:
        """Get lineups for a specific berth within date range."""
        query = self.session.query(Lineup).filter(
            Lineup.berth_id == berth_id
        )
        
        if start_date:
            query = query.filter(
                or_(
                    Lineup.etb >= start_date,
                    Lineup.atb >= start_date
                )
            )
        
        if end_date:
            query = query.filter(
                or_(
                    Lineup.etb <= end_date,
                    Lineup.atb <= end_date
                )
            )
        
        return query.order_by(Lineup.etb.asc().nullslast()).all()
    
    def get_by_date_range(self, start_date: date, end_date: date) -> List[Lineup]:
        """Get lineups within a date range based on ETA/ETB."""
        return self.session.query(Lineup).filter(
            or_(
                and_(Lineup.eta >= start_date, Lineup.eta <= end_date),
                and_(Lineup.etb >= start_date, Lineup.etb <= end_date),
                and_(Lineup.ata >= start_date, Lineup.ata <= end_date),
                and_(Lineup.atb >= start_date, Lineup.atb <= end_date)
            )
        ).order_by(Lineup.eta.asc().nullslast()).all()
    
    def get_active_loading(self) -> List[Lineup]:
        """Get lineups currently loading."""
        return self.session.query(Lineup).filter(
            Lineup.status == LineupStatus.LOADING
        ).order_by(Lineup.loading_start.asc()).all()
    
    def get_waiting_for_berth(self) -> List[Lineup]:
        """Get vessels waiting for berth (arrived but not berthed)."""
        return self.session.query(Lineup).filter(
            and_(
                Lineup.status.in_([
                    LineupStatus.ARRIVED,
                    LineupStatus.NOR_TENDERED
                ]),
                Lineup.ata.isnot(None),
                Lineup.atb.is_(None)
            )
        ).order_by(Lineup.ata.asc()).all()
    
    def get_overdue_vessels(self) -> List[Lineup]:
        """Get vessels that are overdue (past ETA but not arrived)."""
        now = datetime.utcnow()
        return self.session.query(Lineup).filter(
            and_(
                Lineup.eta < now,
                Lineup.ata.is_(None),
                Lineup.status.in_([
                    LineupStatus.SCHEDULED,
                    LineupStatus.ETA_RECEIVED
                ])
            )
        ).order_by(Lineup.eta.asc()).all()
    
    def get_by_vld(self, vld_id: int) -> List[Lineup]:
        """Get lineups for a specific VLD."""
        return self.session.query(Lineup).filter(
            Lineup.vld_id == vld_id
        ).all()
    
    def get_by_vessel_name(self, vessel_name: str) -> List[Lineup]:
        """Get lineups for a specific vessel name."""
        return self.session.query(Lineup).filter(
            Lineup.vessel_name.ilike(f"%{vessel_name}%")
        ).order_by(desc(Lineup.eta)).all()
    
    def get_completed_in_period(self, start_date: date, end_date: date) -> List[Lineup]:
        """Get completed lineups in a specific period."""
        return self.session.query(Lineup).filter(
            and_(
                Lineup.status.in_([LineupStatus.COMPLETED, LineupStatus.DEPARTED]),
                Lineup.loading_completion >= start_date,
                Lineup.loading_completion <= end_date
            )
        ).order_by(Lineup.loading_completion.asc()).all()
    
    def get_lineup_statistics(self, start_date: Optional[date] = None,
                             end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get lineup statistics for a period."""
        query = self.session.query(Lineup)
        
        if start_date and end_date:
            query = query.filter(
                or_(
                    and_(Lineup.eta >= start_date, Lineup.eta <= end_date),
                    and_(Lineup.loading_completion >= start_date, 
                         Lineup.loading_completion <= end_date)
                )
            )
        
        total_lineups = query.count()
        
        # Status distribution
        status_stats = self.session.query(
            Lineup.status,
            func.count(Lineup.id).label('count')
        ).group_by(Lineup.status)
        
        if start_date and end_date:
            status_stats = status_stats.filter(
                or_(
                    and_(Lineup.eta >= start_date, Lineup.eta <= end_date),
                    and_(Lineup.loading_completion >= start_date, 
                         Lineup.loading_completion <= end_date)
                )
            )
        
        status_distribution = {
            status.value: count for status, count in status_stats.all()
        }
        
        # Tonnage statistics
        tonnage_stats = query.filter(
            Lineup.actual_tonnage.isnot(None)
        ).with_entities(
            func.sum(Lineup.actual_tonnage).label('total_tonnage'),
            func.avg(Lineup.actual_tonnage).label('avg_tonnage'),
            func.count(Lineup.id).label('vessels_with_tonnage')
        ).first()
        
        # Performance metrics
        completed_query = query.filter(
            Lineup.status.in_([LineupStatus.COMPLETED, LineupStatus.DEPARTED])
        )
        
        # Average waiting time (arrival to berthing)
        waiting_time_stats = self.session.query(
            func.avg(
                func.extract('epoch', Lineup.atb - Lineup.ata) / 3600
            ).label('avg_waiting_hours')
        ).filter(
            and_(
                Lineup.ata.isnot(None),
                Lineup.atb.isnot(None),
                Lineup.atb >= Lineup.ata
            )
        )
        
        if start_date and end_date:
            waiting_time_stats = waiting_time_stats.filter(
                and_(Lineup.ata >= start_date, Lineup.ata <= end_date)
            )
        
        avg_waiting_hours = waiting_time_stats.scalar()
        
        # Average loading time
        loading_time_stats = self.session.query(
            func.avg(
                func.extract('epoch', 
                    Lineup.loading_completion - Lineup.loading_start) / 3600
            ).label('avg_loading_hours')
        ).filter(
            and_(
                Lineup.loading_start.isnot(None),
                Lineup.loading_completion.isnot(None),
                Lineup.loading_completion >= Lineup.loading_start
            )
        )
        
        if start_date and end_date:
            loading_time_stats = loading_time_stats.filter(
                and_(Lineup.loading_start >= start_date, 
                     Lineup.loading_completion <= end_date)
            )
        
        avg_loading_hours = loading_time_stats.scalar()
        
        return {
            'total_lineups': total_lineups,
            'status_distribution': status_distribution,
            'tonnage': {
                'total_tonnage': int(tonnage_stats.total_tonnage) if tonnage_stats.total_tonnage else 0,
                'average_tonnage': float(tonnage_stats.avg_tonnage) if tonnage_stats.avg_tonnage else 0,
                'vessels_with_tonnage': tonnage_stats.vessels_with_tonnage or 0
            },
            'performance': {
                'average_waiting_hours': float(avg_waiting_hours) if avg_waiting_hours else 0,
                'average_loading_hours': float(avg_loading_hours) if avg_loading_hours else 0
            }
        }
    
    def get_berth_utilization(self, berth_id: int, 
                             start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate berth utilization for a period."""
        lineups = self.get_by_berth(berth_id, start_date, end_date)
        
        total_hours = (end_date - start_date).days * 24
        occupied_hours = 0
        
        for lineup in lineups:
            if lineup.atb and lineup.ats:
                duration = (lineup.ats - lineup.atb).total_seconds() / 3600
                occupied_hours += duration
            elif lineup.atb and lineup.loading_completion:
                duration = (lineup.loading_completion - lineup.atb).total_seconds() / 3600
                occupied_hours += duration
        
        utilization_pct = (occupied_hours / total_hours * 100) if total_hours > 0 else 0
        
        return {
            'berth_id': berth_id,
            'period_days': (end_date - start_date).days,
            'total_hours': total_hours,
            'occupied_hours': round(occupied_hours, 2),
            'utilization_percentage': round(utilization_pct, 2),
            'vessels_served': len(lineups)
        }
    
    def get_partner_performance(self, partner_id: int,
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get performance metrics for a specific partner."""
        query = self.session.query(Lineup).filter(
            Lineup.partner_id == partner_id
        )
        
        if start_date and end_date:
            query = query.filter(
                and_(
                    Lineup.eta >= start_date,
                    Lineup.eta <= end_date
                )
            )
        
        lineups = query.all()
        completed_lineups = [l for l in lineups if l.status in [
            LineupStatus.COMPLETED, LineupStatus.DEPARTED
        ]]
        
        total_planned = sum(l.planned_tonnage for l in lineups if l.planned_tonnage)
        total_actual = sum(l.actual_tonnage for l in completed_lineups if l.actual_tonnage)
        
        on_time_arrivals = sum(
            1 for l in lineups 
            if l.eta and l.ata and l.ata <= l.eta + timedelta(hours=6)
        )
        
        return {
            'partner_id': partner_id,
            'total_lineups': len(lineups),
            'completed_lineups': len(completed_lineups),
            'completion_rate': len(completed_lineups) / len(lineups) * 100 if lineups else 0,
            'tonnage': {
                'planned': total_planned,
                'actual': total_actual,
                'achievement_rate': total_actual / total_planned * 100 if total_planned else 0
            },
            'punctuality': {
                'on_time_arrivals': on_time_arrivals,
                'on_time_rate': on_time_arrivals / len(lineups) * 100 if lineups else 0
            }
        }
    
    def update_status(self, lineup_id: int, new_status: LineupStatus,
                     timestamp_field: Optional[str] = None) -> Optional[Lineup]:
        """Update lineup status and related timestamp."""
        lineup = self.get_by_id(lineup_id)
        if not lineup:
            return None
        
        lineup.status = new_status
        
        # Auto-update timestamps based on status
        now = datetime.utcnow()
        if new_status == LineupStatus.ARRIVED and not lineup.ata:
            lineup.ata = now
        elif new_status == LineupStatus.BERTHED and not lineup.atb:
            lineup.atb = now
        elif new_status == LineupStatus.LOADING and not lineup.loading_start:
            lineup.loading_start = now
        elif new_status == LineupStatus.COMPLETED and not lineup.loading_completion:
            lineup.loading_completion = now
        elif new_status == LineupStatus.DEPARTED and not lineup.ats:
            lineup.ats = now
        
        # Custom timestamp field
        if timestamp_field:
            setattr(lineup, timestamp_field, now)
        
        self.session.commit()
        return lineup
    
    def search_by_vessel_or_partner(self, search_term: str) -> List[Lineup]:
        """Search lineups by vessel name or partner name."""
        return self.session.query(Lineup).join(Partner).filter(
            or_(
                Lineup.vessel_name.ilike(f"%{search_term}%"),
                Partner.name.ilike(f"%{search_term}%")
            )
        ).order_by(desc(Lineup.eta)).all()
    
    def get_upcoming_arrivals(self, days_ahead: int = 7) -> List[Lineup]:
        """Get vessels expected to arrive in the next N days."""
        end_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        return self.session.query(Lineup).filter(
            and_(
                Lineup.eta <= end_date,
                Lineup.eta >= datetime.utcnow(),
                Lineup.status.in_([
                    LineupStatus.SCHEDULED,
                    LineupStatus.ETA_RECEIVED
                ])
            )
        ).order_by(Lineup.eta.asc()).all()
    
    def get_lineup_conflicts(self) -> List[Dict[str, Any]]:
        """Identify potential berth conflicts in the lineup."""
        conflicts = []
        
        # Get all active lineups with berth assignments
        active_lineups = self.session.query(Lineup).filter(
            Lineup.status.in_([
                LineupStatus.SCHEDULED,
                LineupStatus.ETA_RECEIVED,
                LineupStatus.ARRIVED,
                LineupStatus.NOR_TENDERED,
                LineupStatus.BERTHED,
                LineupStatus.LOADING
            ])
        ).filter(
            Lineup.etb.isnot(None)
        ).order_by(Lineup.berth_id, Lineup.etb).all()
        
        # Group by berth and check for overlaps
        berth_lineups = {}
        for lineup in active_lineups:
            if lineup.berth_id not in berth_lineups:
                berth_lineups[lineup.berth_id] = []
            berth_lineups[lineup.berth_id].append(lineup)
        
        for berth_id, lineups in berth_lineups.items():
            for i in range(len(lineups) - 1):
                current = lineups[i]
                next_lineup = lineups[i + 1]
                
                # Estimate completion time
                current_end = current.ets or (
                    current.etb + timedelta(hours=24) if current.etb else None
                )
                
                if current_end and next_lineup.etb and current_end > next_lineup.etb:
                    conflicts.append({
                        'berth_id': berth_id,
                        'conflict_type': 'overlap',
                        'first_lineup': {
                            'id': current.id,
                            'vessel_name': current.vessel_name,
                            'etb': current.etb.isoformat() if current.etb else None,
                            'estimated_completion': current_end.isoformat()
                        },
                        'second_lineup': {
                            'id': next_lineup.id,
                            'vessel_name': next_lineup.vessel_name,
                            'etb': next_lineup.etb.isoformat() if next_lineup.etb else None
                        },
                        'overlap_hours': (current_end - next_lineup.etb).total_seconds() / 3600
                    })
        
        return conflicts

