"""Aquaculture water chemistry (Emerson NH3, Benson-Krause DO), carrying capacity, and FCR feeding."""

from .farm import (
    SPECIES_PROFILES,
    PondPlanResult,
    PondSpec,
    SpeciesProfile,
    get_species_profile,
    plan_pond_operations,
)
from .water_chem import (
    WaterChemistryReport,
    WaterReading,
    audit_pond_chemistry,
    dissolved_oxygen_saturation_mg_l,
    unionized_ammonia_mg_l,
)

__all__ = [
    "SPECIES_PROFILES",
    "PondPlanResult",
    "PondSpec",
    "SpeciesProfile",
    "WaterChemistryReport",
    "WaterReading",
    "audit_pond_chemistry",
    "dissolved_oxygen_saturation_mg_l",
    "get_species_profile",
    "plan_pond_operations",
    "unionized_ammonia_mg_l",
]
__version__ = "0.1.0"
