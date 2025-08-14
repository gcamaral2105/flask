"""
Partner Service
==============

Business logic service for Partner management in the ERP Bauxita system.
Handles partner relationships, contracts, and business validations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from decimal import Decimal

from app.repository.partner_repository import PartnerRepository
from app.models.partner import Partner, PartnerEntity
from app.extensions import db


class PartnerService:
    """Service class for partner management business logic."""
    
    def __init__(self):
        self.partner_repo = PartnerRepository()
    
    def create_partner(self, partner_data: Dict[str, Any], 
                      entity_data: Optional[Dict[str, Any]] = None) -> Partner:
        """
        Create a new partner with business validation.
        
        Args:
            partner_data: Dictionary containing partner information
            entity_data: Optional entity information
            
        Returns:
            Created Partner instance
            
        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        required_fields = ['name']
        for field in required_fields:
            if field not in partner_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate partner name uniqueness
        existing_partner = self.partner_repo.get_by_name(partner_data['name'])
        if existing_partner:
            raise ValueError(f"Partner with name '{partner_data['name']}' already exists")
        
        # Validate partner name format
        self._validate_partner_name(partner_data['name'])
        
        # Validate entity data if provided
        if entity_data:
            self._validate_entity_data(entity_data)
        
        # Create partner with entity
        partner = self.partner_repo.create_partner_with_entity(partner_data, entity_data)
        
        # Log partner creation
        self._log_partner_event(partner, "CREATED")
        
        return partner
    
    def update_partner(self, partner_id: Union[int, str], 
                      partner_data: Dict[str, Any]) -> Partner:
        """
        Update partner information with validation.
        
        Args:
            partner_id: ID of the partner to update
            partner_data: Dictionary of data to update
            
        Returns:
            Updated Partner instance
        """
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        # Validate name change if provided
        if 'name' in partner_data and partner_data['name'] != partner.name:
            existing_partner = self.partner_repo.get_by_name(partner_data['name'])
            if existing_partner and existing_partner.id != partner.id:
                raise ValueError(f"Partner with name '{partner_data['name']}' already exists")
            self._validate_partner_name(partner_data['name'])
        
        # Update partner
        updated_partner = self.partner_repo.update(partner_id, **partner_data)
        
        # Log partner update
        self._log_partner_event(updated_partner, "UPDATED", 
                              updated_fields=list(partner_data.keys()))
        
        return updated_partner
    
    def update_partner_entity(self, partner_id: Union[int, str], 
                            entity_data: Dict[str, Any]) -> Partner:
        """
        Update partner entity information.
        
        Args:
            partner_id: ID of the partner
            entity_data: Entity data to update
            
        Returns:
            Updated Partner instance
        """
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        # Validate entity data
        self._validate_entity_data(entity_data)
        
        # Update entity
        updated_partner = self.partner_repo.update_partner_entity(partner_id, entity_data)
        
        # Log entity update
        self._log_partner_event(updated_partner, "ENTITY_UPDATED")
        
        return updated_partner
    
    def get_partner_portfolio(self, partner_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get comprehensive partner portfolio information.
        
        Args:
            partner_id: ID of the partner
            
        Returns:
            Partner portfolio data
        """
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        # Get performance metrics
        performance = self.partner_repo.get_partner_performance(partner_id)
        
        # Get partnership history
        history = self.partner_repo.get_partnership_history(partner_id)
        
        # Calculate additional metrics
        portfolio = {
            'partner_info': {
                'id': partner.id,
                'name': partner.name,
                'entity_type': self._get_partner_entity_type(partner),
                'created_at': partner.created_at.isoformat() if partner.created_at else None
            },
            'performance_metrics': performance,
            'partnership_history': history,
            'current_status': self._assess_partner_status(partner),
            'risk_assessment': self._assess_partner_risk(partner),
            'recommendations': self._generate_partner_recommendations(partner)
        }
        
        return portfolio
    
    def evaluate_partner_performance(self, partner_id: Union[int, str], 
                                   evaluation_period_days: int = 365) -> Dict[str, Any]:
        """
        Evaluate partner performance over a specified period.
        
        Args:
            partner_id: ID of the partner
            evaluation_period_days: Period for evaluation in days
            
        Returns:
            Performance evaluation results
        """
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        # Get enrollments for the period
        enrollments = self.partner_repo.get_production_enrollments(partner_id)
        
        # Filter enrollments by period
        cutoff_date = datetime.now() - timedelta(days=evaluation_period_days)
        recent_enrollments = [
            e for e in enrollments 
            if e.created_at and e.created_at >= cutoff_date
        ]
        
        evaluation = {
            'partner_id': partner_id,
            'partner_name': partner.name,
            'evaluation_period_days': evaluation_period_days,
            'total_enrollments': len(recent_enrollments),
            'performance_score': 0,
            'metrics': {
                'reliability_score': 0,
                'volume_consistency': 0,
                'contract_compliance': 0,
                'operational_efficiency': 0
            },
            'strengths': [],
            'areas_for_improvement': [],
            'overall_rating': 'Not Rated'
        }
        
        if recent_enrollments:
            # Calculate performance metrics
            evaluation['metrics'] = self._calculate_performance_metrics(partner, recent_enrollments)
            
            # Calculate overall performance score
            metrics = evaluation['metrics']
            evaluation['performance_score'] = (
                metrics['reliability_score'] * 0.3 +
                metrics['volume_consistency'] * 0.25 +
                metrics['contract_compliance'] * 0.25 +
                metrics['operational_efficiency'] * 0.2
            )
            
            # Determine overall rating
            evaluation['overall_rating'] = self._determine_performance_rating(evaluation['performance_score'])
            
            # Generate insights
            evaluation['strengths'] = self._identify_partner_strengths(partner, metrics)
            evaluation['areas_for_improvement'] = self._identify_improvement_areas(partner, metrics)
        
        return evaluation
    
    def get_partner_contracts_summary(self, partner_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get summary of partner contracts and commitments.
        
        Args:
            partner_id: ID of the partner
            
        Returns:
            Contracts summary data
        """
        partner = self.partner_repo.get_by_id(partner_id)
        if not partner:
            raise ValueError(f"Partner with ID {partner_id} not found")
        
        enrollments = self.partner_repo.get_production_enrollments(partner_id)
        
        summary = {
            'partner_id': partner_id,
            'partner_name': partner.name,
            'total_contracts': len(enrollments),
            'active_contracts': 0,
            'total_committed_tonnage': 0,
            'contracts_by_year': {},
            'contract_details': [],
            'compliance_status': 'Good'  # Placeholder
        }
        
        for enrollment in enrollments:
            contract_detail = {
                'production_id': enrollment.production_id,
                'vessel_size_t': enrollment.vessel_size_t,
                'minimum_tonnage': enrollment.minimum_tonnage,
                'status': 'Active'  # Would be determined by production status
            }
            
            if hasattr(enrollment, 'production') and enrollment.production:
                contract_detail['year'] = enrollment.production.contractual_year
                contract_detail['scenario_name'] = enrollment.production.scenario_name
                
                # Group by year
                year = enrollment.production.contractual_year
                summary['contracts_by_year'][year] = summary['contracts_by_year'].get(year, 0) + 1
                
                # Check if active
                if enrollment.production.status.value == 'active':
                    summary['active_contracts'] += 1
            
            # Sum tonnage
            if enrollment.minimum_tonnage:
                summary['total_committed_tonnage'] += enrollment.minimum_tonnage
            
            summary['contract_details'].append(contract_detail)
        
        return summary
    
    def analyze_partner_relationships(self) -> Dict[str, Any]:
        """
        Analyze partner relationships and network.
        
        Returns:
            Partner relationship analysis
        """
        # Get all partners
        all_partners = self.partner_repo.get_active()
        
        # Get partner statistics
        stats = self.partner_repo.get_partner_statistics()
        
        analysis = {
            'total_partners': len(all_partners),
            'partner_statistics': stats,
            'relationship_network': self._analyze_partner_network(all_partners),
            'partner_segments': self._segment_partners(all_partners),
            'key_insights': self._generate_relationship_insights(all_partners, stats)
        }
        
        return analysis
    
    def recommend_partner_matches(self, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recommend partners based on specific requirements.
        
        Args:
            requirements: Dictionary of requirements for partner matching
            
        Returns:
            List of recommended partners with match scores
        """
        # Get all active partners
        partners = self.partner_repo.get_active()
        
        recommendations = []
        
        for partner in partners:
            match_score = self._calculate_partner_match_score(partner, requirements)
            
            if match_score > 0:  # Only include partners with some match
                recommendation = {
                    'partner_id': partner.id,
                    'partner_name': partner.name,
                    'entity_type': self._get_partner_entity_type(partner),
                    'match_score': match_score,
                    'match_reasons': self._get_match_reasons(partner, requirements),
                    'risk_level': self._assess_partner_risk_level(partner)
                }
                recommendations.append(recommendation)
        
        # Sort by match score descending
        recommendations.sort(key=lambda x: x['match_score'], reverse=True)
        
        return recommendations[:10]  # Return top 10 matches
    
    def _validate_partner_name(self, name: str) -> None:
        """Validate partner name format."""
        if not name or len(name.strip()) < 2:
            raise ValueError("Partner name must be at least 2 characters long")
        
        if len(name) > 255:
            raise ValueError("Partner name cannot exceed 255 characters")
        
        # Check for invalid characters (basic validation)
        invalid_chars = ['<', '>', '&', '"', "'"]
        if any(char in name for char in invalid_chars):
            raise ValueError("Partner name contains invalid characters")
    
    def _validate_entity_data(self, entity_data: Dict[str, Any]) -> None:
        """Validate entity data."""
        if 'entity_type' in entity_data:
            valid_types = ['HALCO', 'OFFTAKER', 'VESSEL_OWNER', 'SERVICE_PROVIDER']
            if entity_data['entity_type'] not in valid_types:
                raise ValueError(f"Invalid entity type. Must be one of: {valid_types}")
    
    def _get_partner_entity_type(self, partner: Partner) -> Optional[str]:
        """Get partner entity type."""
        if hasattr(partner, 'entity_type') and partner.entity_type:
            return str(partner.entity_type)
        elif hasattr(partner, 'entity') and partner.entity and hasattr(partner.entity, 'entity_type'):
            return str(partner.entity.entity_type)
        return None
    
    def _assess_partner_status(self, partner: Partner) -> str:
        """Assess current partner status."""
        # This would integrate with various systems to determine status
        # For now, return based on basic criteria
        if partner.deleted_at:
            return "Inactive"
        
        # Check if partner has recent activity
        enrollments = self.partner_repo.get_production_enrollments(partner.id)
        if enrollments:
            return "Active"
        
        return "Dormant"
    
    def _assess_partner_risk(self, partner: Partner) -> Dict[str, Any]:
        """Assess partner risk factors."""
        risk_assessment = {
            'overall_risk': 'Low',
            'risk_factors': [],
            'risk_score': 0,
            'mitigation_recommendations': []
        }
        
        # Example risk factors (would be more sophisticated in practice)
        enrollments = self.partner_repo.get_production_enrollments(partner.id)
        
        if len(enrollments) == 0:
            risk_assessment['risk_factors'].append("No production history")
            risk_assessment['risk_score'] += 20
        
        if not self._get_partner_entity_type(partner):
            risk_assessment['risk_factors'].append("Undefined entity type")
            risk_assessment['risk_score'] += 10
        
        # Determine overall risk level
        if risk_assessment['risk_score'] >= 50:
            risk_assessment['overall_risk'] = 'High'
        elif risk_assessment['risk_score'] >= 25:
            risk_assessment['overall_risk'] = 'Medium'
        
        return risk_assessment
    
    def _generate_partner_recommendations(self, partner: Partner) -> List[str]:
        """Generate recommendations for partner management."""
        recommendations = []
        
        entity_type = self._get_partner_entity_type(partner)
        if not entity_type:
            recommendations.append("Define partner entity type for better categorization")
        
        enrollments = self.partner_repo.get_production_enrollments(partner.id)
        if not enrollments:
            recommendations.append("Consider enrolling partner in upcoming production scenarios")
        
        if hasattr(partner, 'vessels') and not partner.vessels:
            if entity_type == 'VESSEL_OWNER':
                recommendations.append("Add vessel information for this vessel owner")
        
        return recommendations
    
    def _calculate_performance_metrics(self, partner: Partner, 
                                     enrollments: List) -> Dict[str, float]:
        """Calculate detailed performance metrics."""
        # Placeholder metrics calculation
        metrics = {
            'reliability_score': 85.0,  # Based on delivery performance
            'volume_consistency': 90.0,  # Based on volume delivery consistency
            'contract_compliance': 95.0,  # Based on contract adherence
            'operational_efficiency': 80.0  # Based on operational metrics
        }
        
        # In a real system, these would be calculated from actual data
        return metrics
    
    def _determine_performance_rating(self, score: float) -> str:
        """Determine performance rating based on score."""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Satisfactory"
        elif score >= 60:
            return "Needs Improvement"
        else:
            return "Poor"
    
    def _identify_partner_strengths(self, partner: Partner, metrics: Dict[str, float]) -> List[str]:
        """Identify partner strengths based on metrics."""
        strengths = []
        
        if metrics['contract_compliance'] >= 90:
            strengths.append("Excellent contract compliance")
        
        if metrics['volume_consistency'] >= 85:
            strengths.append("Consistent volume delivery")
        
        if metrics['reliability_score'] >= 85:
            strengths.append("High reliability in operations")
        
        return strengths
    
    def _identify_improvement_areas(self, partner: Partner, metrics: Dict[str, float]) -> List[str]:
        """Identify areas for improvement based on metrics."""
        improvements = []
        
        if metrics['operational_efficiency'] < 75:
            improvements.append("Operational efficiency could be improved")
        
        if metrics['reliability_score'] < 80:
            improvements.append("Reliability needs attention")
        
        if metrics['volume_consistency'] < 80:
            improvements.append("Volume delivery consistency needs improvement")
        
        return improvements
    
    def _analyze_partner_network(self, partners: List[Partner]) -> Dict[str, Any]:
        """Analyze partner relationship network."""
        network = {
            'total_connections': 0,
            'network_density': 0,
            'key_hubs': [],
            'isolated_partners': []
        }
        
        # This would analyze relationships between partners
        # For now, it's a placeholder
        return network
    
    def _segment_partners(self, partners: List[Partner]) -> Dict[str, Any]:
        """Segment partners into categories."""
        segments = {
            'by_entity_type': {},
            'by_activity_level': {'high': 0, 'medium': 0, 'low': 0},
            'by_relationship_duration': {'new': 0, 'established': 0, 'long_term': 0}
        }
        
        for partner in partners:
            # Segment by entity type
            entity_type = self._get_partner_entity_type(partner) or 'Unknown'
            segments['by_entity_type'][entity_type] = segments['by_entity_type'].get(entity_type, 0) + 1
            
            # Segment by activity level (placeholder logic)
            enrollments = self.partner_repo.get_production_enrollments(partner.id)
            if len(enrollments) > 5:
                segments['by_activity_level']['high'] += 1
            elif len(enrollments) > 2:
                segments['by_activity_level']['medium'] += 1
            else:
                segments['by_activity_level']['low'] += 1
        
        return segments
    
    def _generate_relationship_insights(self, partners: List[Partner], 
                                      stats: Dict[str, Any]) -> List[str]:
        """Generate insights about partner relationships."""
        insights = []
        
        if stats['total_partners'] > 50:
            insights.append("Large partner network requires systematic relationship management")
        
        if stats.get('with_vessels', 0) > 0:
            insights.append(f"{stats['with_vessels']} partners own vessels, indicating strong asset partnerships")
        
        if stats.get('enrolled_in_productions', 0) > 0:
            insights.append(f"{stats['enrolled_in_productions']} partners actively enrolled in productions")
        
        return insights
    
    def _calculate_partner_match_score(self, partner: Partner, 
                                     requirements: Dict[str, Any]) -> float:
        """Calculate match score between partner and requirements."""
        score = 0.0
        
        # Match by entity type
        required_type = requirements.get('entity_type')
        partner_type = self._get_partner_entity_type(partner)
        if required_type and partner_type == required_type:
            score += 40.0
        
        # Match by capacity requirements
        required_capacity = requirements.get('min_capacity_tons', 0)
        if required_capacity > 0:
            # This would check partner's historical capacity
            # For now, assume all partners can meet capacity
            score += 30.0
        
        # Match by experience
        enrollments = self.partner_repo.get_production_enrollments(partner.id)
        if len(enrollments) > 0:
            score += 20.0
        
        # Match by geographic requirements (placeholder)
        score += 10.0
        
        return min(score, 100.0)
    
    def _get_match_reasons(self, partner: Partner, requirements: Dict[str, Any]) -> List[str]:
        """Get reasons why partner matches requirements."""
        reasons = []
        
        required_type = requirements.get('entity_type')
        partner_type = self._get_partner_entity_type(partner)
        if required_type and partner_type == required_type:
            reasons.append(f"Matches required entity type: {required_type}")
        
        enrollments = self.partner_repo.get_production_enrollments(partner.id)
        if enrollments:
            reasons.append(f"Has production experience ({len(enrollments)} enrollments)")
        
        return reasons
    
    def _assess_partner_risk_level(self, partner: Partner) -> str:
        """Assess partner risk level."""
        risk_assessment = self._assess_partner_risk(partner)
        return risk_assessment['overall_risk']
    
    def _log_partner_event(self, partner: Partner, event_type: str, **kwargs) -> None:
        """Log partner events for audit trail."""
        log_data = {
            'partner_id': partner.id,
            'partner_name': partner.name,
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        
        # In a real implementation, this would write to a log table or external system
        print(f"Partner Event: {log_data}")  # Placeholder

