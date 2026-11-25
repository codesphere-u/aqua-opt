"""Aquaculture water chemistry: Emerson et al. (1975) NH3 toxicity & Benson-Krause DO saturation."""

from __future__ import annotations

import math
from dataclasses import dataclass


def unionized_ammonia_fraction(temp_c: float, ph: float) -> float:
    """Emerson et al. (1975) equilibrium fraction of toxic un-ionized NH3 in Total Ammonia Nitrogen."""
    if not (0.0 <= temp_c <= 45.0):
        raise ValueError(f"temp_c must be in [0, 45] C, got {temp_c}")
    if not (4.0 <= ph <= 11.0):
        raise ValueError(f"ph must be in [4, 11], got {ph}")
    t_k = temp_c + 273.15
    pka = 0.09018 + (2729.92 / t_k)
    return 1.0 / (1.0 + float(10.0 ** (pka - ph)))


def unionized_ammonia_mg_l(tan_mg_l: float, temp_c: float, ph: float) -> float:
    """Compute toxic un-ionized NH3-N concentration (mg/L) from TAN, water temperature, and pH."""
    if tan_mg_l < 0.0:
        raise ValueError("tan_mg_l cannot be negative")
    return tan_mg_l * unionized_ammonia_fraction(temp_c, ph)


def dissolved_oxygen_saturation_mg_l(
    temp_c: float,
    *,
    elevation_m: float = 0.0,
    salinity_ppt: float = 0.0,
) -> float:
    """Benson-Krause (1984) dissolved oxygen saturation (mg/L) adjusted for altitude and salinity."""
    if not (0.0 <= temp_c <= 45.0):
        raise ValueError(f"temp_c must be in [0, 45] C, got {temp_c}")
    if elevation_m < -100.0 or elevation_m > 5000.0:
        raise ValueError(f"elevation_m out of range: {elevation_m}")
    if salinity_ppt < 0.0 or salinity_ppt > 45.0:
        raise ValueError(f"salinity_ppt out of range: {salinity_ppt}")

    t_k = temp_c + 273.15
    ln_do = (
        -139.34411
        + 1.575701e5 / t_k
        - 6.642308e7 / (t_k**2)
        + 1.243800e10 / (t_k**3)
        - 8.621949e11 / (t_k**4)
    )
    do_fresh_sea = math.exp(ln_do)

    # Barometric pressure altitude correction
    pressure_ratio = float((1.0 - 2.25577e-5 * elevation_m) ** 5.25588)

    # Salinity factor (Benson-Krause)
    sal_factor = math.exp(-salinity_ppt * (0.017674 - 10.754 / t_k + 2140.7 / (t_k**2)))
    return do_fresh_sea * pressure_ratio * sal_factor


@dataclass(frozen=True)
class WaterReading:
    """Pond or cage water-quality field measurement."""

    temp_c: float
    ph: float
    dissolved_oxygen_mg_l: float
    tan_mg_l: float
    nitrite_mg_l: float = 0.0
    elevation_m: float = 1134.0  # Lake Victoria basin default
    salinity_ppt: float = 0.0


@dataclass(frozen=True)
class WaterChemistryReport:
    """Water-quality toxicity and hypoxia audit for aquaculture ponds."""

    do_saturation_mg_l: float
    do_saturation_pct: float
    nh3_fraction: float
    unionized_nh3_mg_l: float
    ammonia_status: str  # "safe", "chronic_stress", "acute_lethal"
    oxygen_status: str  # "optimal", "stress", "critical_hypoxia"
    alerts: tuple[str, ...]


def audit_pond_chemistry(
    reading: WaterReading,
    *,
    min_safe_do_mg_l: float = 3.5,
) -> WaterChemistryReport:
    """Audit pond/cage water reading for NH3 toxicity, nitrite stress, and hypoxia."""
    do_sat = dissolved_oxygen_saturation_mg_l(
        reading.temp_c,
        elevation_m=reading.elevation_m,
        salinity_ppt=reading.salinity_ppt,
    )
    do_pct = (reading.dissolved_oxygen_mg_l / do_sat) * 100.0 if do_sat > 0 else 0.0
    nh3_frac = unionized_ammonia_fraction(reading.temp_c, reading.ph)
    nh3 = reading.tan_mg_l * nh3_frac

    alerts: list[str] = []
    if nh3 >= 0.05:
        nh3_status = "acute_lethal"
        alerts.append(
            f"ACUTE NH3 TOXICITY: un-ionized NH3 is {nh3:.4f} mg/L (>=0.05 mg/L lethal threshold at "
            f"pH {reading.ph:.1f}, {reading.temp_c:.1f}C). Halt feeding immediately and flush >=30% water."
        )
    elif nh3 >= 0.02:
        nh3_status = "chronic_stress"
        alerts.append(
            f"CHRONIC NH3 STRESS: un-ionized NH3 is {nh3:.4f} mg/L (0.02-0.05 mg/L impairs gills/FCR). "
            "Reduce feeding rate and increase water exchange."
        )
    else:
        nh3_status = "safe"

    if reading.dissolved_oxygen_mg_l < min_safe_do_mg_l * 0.7:
        do_status = "critical_hypoxia"
        alerts.append(
            f"CRITICAL HYPOXIA: DO {reading.dissolved_oxygen_mg_l:.2f} mg/L ({do_pct:.0f}% sat); "
            "start emergency paddlewheel/blower aeration immediately."
        )
    elif reading.dissolved_oxygen_mg_l < min_safe_do_mg_l:
        do_status = "stress"
        alerts.append(
            f"LOW DISSOLVED OXYGEN: {reading.dissolved_oxygen_mg_l:.2f} mg/L < {min_safe_do_mg_l:.1f} mg/L "
            "safe floor; increase dawn aeration."
        )
    else:
        do_status = "optimal"

    if reading.nitrite_mg_l >= 0.5:
        alerts.append(
            f"HIGH NITRITE ({reading.nitrite_mg_l:.2f} mg/L >= 0.5): brown-blood disease risk; "
            "dose sodium chloride (salt) to maintain Cl-:NO2- ratio >= 10:1."
        )

    return WaterChemistryReport(
        do_saturation_mg_l=round(do_sat, 2),
        do_saturation_pct=round(do_pct, 1),
        nh3_fraction=round(nh3_frac, 5),
        unionized_nh3_mg_l=round(nh3, 4),
        ammonia_status=nh3_status,
        oxygen_status=do_status,
        alerts=tuple(alerts),
    )
