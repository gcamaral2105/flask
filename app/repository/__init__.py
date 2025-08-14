"""
Repository Module
================

Centralized imports for all repository classes in the ERP Bauxita system.
"""

from .production_repository import ProductionRepository
from .vessel_repository import VesselRepository
from .partner_repository import PartnerRepository

__all__ = [
    'ProductionRepository',
    'VesselRepository', 
    'PartnerRepository'
]
