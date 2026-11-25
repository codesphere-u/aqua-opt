"""Tilapia, catfish, and trout carrying capacity, aerator kW sizing, and FCR feeding schedule."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeciesProfile:
    """Biological growth, stocking, and oxygen thresholds for farmed fish species."""

    key: str
    display_name: str
    optimal_temp_min_c: float
    optimal_temp_max_c: float
    min_safe_do_mg_l: float
    max_unaerated_density_kg_m3: float
    max_aerated_density_kg_m3: float
    typical_fcr: float
    o2_consumption_g_per_kg_fish_hr: float


SPECIES_PROFILES: dict[str, SpeciesProfile] = {
    "nile_tilapia": SpeciesProfile(
        key="nile_tilapia",
        display_name="Nile Tilapia (Oreochromis niloticus)",
        optimal_temp_min_c=24.0,
        optimal_temp_max_c=30.0,
        min_safe_do_mg_l=3.5,
        max_unaerated_density_kg_m3=2.0,
        max_aerated_density_kg_m3=12.0,
        typical_fcr=1.55,
        o2_consumption_g_per_kg_fish_hr=0.35,
    ),
    "african_catfish": SpeciesProfile(
        key="african_catfish",
        display_name="African Catfish (Clarias gariepinus)",
        optimal_temp_min_c=25.0,
        optimal_temp_max_c=31.0,
        min_safe_do_mg_l=2.0,  # Facultative air-breather
        max_unaerated_density_kg_m3=8.0,
        max_aerated_density_kg_m3=35.0,
        typical_fcr=1.35,
        o2_consumption_g_per_kg_fish_hr=0.30,
    ),
    "rainbow_trout": SpeciesProfile(
        key="rainbow_trout",
        display_name="Rainbow Trout (Oncorhynchus mykiss)",
        optimal_temp_min_c=12.0,
        optimal_temp_max_c=18.0,
        min_safe_do_mg_l=5.5,
        max_unaerated_density_kg_m3=1.0,
        max_aerated_density_kg_m3=25.0,
        typical_fcr=1.20,
        o2_consumption_g_per_kg_fish_hr=0.45,
    ),
}


def get_species_profile(key: str) -> SpeciesProfile:
    norm = key.strip().lower().replace("-", "_").replace(" ", "_")
    if norm not in SPECIES_PROFILES:
        raise KeyError(f"Unknown species '{key}'. Available: {', '.join(sorted(SPECIES_PROFILES))}")
    return SPECIES_PROFILES[norm]


def _stage_feeding_rate_and_protein(avg_fish_weight_g: float) -> tuple[float, int, int]:
    """Return (pct_body_weight_per_day, target_crude_protein_pct, meals_per_day)."""
    if avg_fish_weight_g < 10.0:
        return (8.0, 40, 4)
    if avg_fish_weight_g < 50.0:
        return (5.0, 35, 3)
    if avg_fish_weight_g < 150.0:
        return (3.5, 32, 3)
    if avg_fish_weight_g < 350.0:
        return (2.5, 30, 2)
    return (1.8, 28, 2)


@dataclass(frozen=True)
class PondSpec:
    """Fishpond or cage dimensions, stocking count, and current biomass stage."""

    species: str
    volume_m3: float
    fish_count: int
    avg_fish_weight_g: float
    water_temp_c: float = 26.0
    aerated: bool = False

    def __post_init__(self) -> None:
        if self.volume_m3 <= 0 or self.fish_count <= 0 or self.avg_fish_weight_g <= 0:
            raise ValueError("volume_m3, fish_count, and avg_fish_weight_g must be positive")


@dataclass(frozen=True)
class PondPlanResult:
    """Biomass density, daily ration, FCR growth forecast, and aerator kW sizing."""

    species: str
    total_biomass_kg: float
    stocking_density_kg_m3: float
    carrying_capacity_kg_m3: float
    overstocked: bool
    feeding_rate_pct_bw: float
    recommended_crude_protein_pct: int
    meals_per_day: int
    daily_feed_kg: float
    projected_daily_gain_kg: float
    estimated_tan_excreted_g_day: float
    peak_night_o2_demand_kg_hr: float
    recommended_aerator_kw: float
    warnings: tuple[str, ...]


def plan_pond_operations(
    pond: PondSpec,
    *,
    aerator_sae_kg_o2_per_kwh: float = 1.2,
) -> PondPlanResult:
    """Compute stocking density limits, daily feed ration, TAN loading, and aerator kW sizing."""
    prof = get_species_profile(pond.species)
    biomass_kg = (pond.fish_count * pond.avg_fish_weight_g) / 1000.0
    density = biomass_kg / pond.volume_m3
    cap = prof.max_aerated_density_kg_m3 if pond.aerated else prof.max_unaerated_density_kg_m3
    overstocked = density > cap

    feed_pct, protein_pct, meals = _stage_feeding_rate_and_protein(pond.avg_fish_weight_g)
    # Reduce ration if water temperature is outside species optimal window
    warnings: list[str] = []
    temp_factor = 1.0
    if pond.water_temp_c < prof.optimal_temp_min_c or pond.water_temp_c > prof.optimal_temp_max_c:
        temp_factor = 0.70
        warnings.append(
            f"SUB-OPTIMAL TEMPERATURE ({pond.water_temp_c:.1f}C outside "
            f"{prof.optimal_temp_min_c:.0f}-{prof.optimal_temp_max_c:.0f}C): reduced feed ration by 30%."
        )

    daily_feed = biomass_kg * (feed_pct / 100.0) * temp_factor
    daily_gain = daily_feed / prof.typical_fcr

    # Standard aquaculture rule of thumb: ~0.092 * protein_fraction kg TAN excreted per kg feed
    tan_g_day = daily_feed * (protein_pct / 100.0) * 92.0

    # Peak nighttime oxygen demand = fish respiration + feed BOD (0.30 kg O2/kg feed spread over 12h)
    fish_o2_kg_hr = (biomass_kg * prof.o2_consumption_g_per_kg_fish_hr) / 1000.0
    feed_o2_kg_hr = (daily_feed * 0.30) / 12.0
    peak_o2_kg_hr = fish_o2_kg_hr + feed_o2_kg_hr

    # Natural surface diffusion covers up to ~0.08 kg O2/hr per 1000 m3; aerator supplies deficit
    natural_o2_kg_hr = (pond.volume_m3 / 1000.0) * 0.08
    deficit_o2 = max(0.0, peak_o2_kg_hr - natural_o2_kg_hr)
    aerator_kw = deficit_o2 / aerator_sae_kg_o2_per_kwh

    if overstocked:
        warnings.append(
            f"OVERSTOCKED POND: {density:.2f} kg/m3 exceeds carrying capacity {cap:.1f} kg/m3 "
            f"({'aerated' if pond.aerated else 'un-aerated'}). Harvest/grade fish or add mechanical aeration."
        )

    return PondPlanResult(
        species=prof.key,
        total_biomass_kg=round(biomass_kg, 2),
        stocking_density_kg_m3=round(density, 2),
        carrying_capacity_kg_m3=round(cap, 2),
        overstocked=overstocked,
        feeding_rate_pct_bw=round(feed_pct * temp_factor, 2),
        recommended_crude_protein_pct=protein_pct,
        meals_per_day=meals,
        daily_feed_kg=round(daily_feed, 2),
        projected_daily_gain_kg=round(daily_gain, 2),
        estimated_tan_excreted_g_day=round(tan_g_day, 1),
        peak_night_o2_demand_kg_hr=round(peak_o2_kg_hr, 3),
        recommended_aerator_kw=round(aerator_kw, 2),
        warnings=tuple(warnings),
    )
