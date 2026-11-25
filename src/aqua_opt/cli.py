"""CLI entrypoint for aqua-opt."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .farm import PondSpec, get_species_profile, plan_pond_operations
from .water_chem import WaterReading, audit_pond_chemistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aqua-opt",
        description="Audit fishpond NH3 toxicity, elevation-adjusted DO, carrying capacity, and FCR feeding.",
    )
    parser.add_argument("--species", default="nile_tilapia", help="nile_tilapia, african_catfish, or rainbow_trout.")
    parser.add_argument("--volume-m3", type=float, default=600.0, help="Pond or cage volume m3.")
    parser.add_argument("--fish-count", type=int, default=3000, help="Number of stocked fish.")
    parser.add_argument("--avg-weight-g", type=float, default=250.0, help="Mean individual weight (grams).")
    parser.add_argument("--temp-c", type=float, default=26.5, help="Water temperature C.")
    parser.add_argument("--ph", type=float, default=7.6, help="Pond water pH.")
    parser.add_argument("--do-mg-l", type=float, default=5.2, help="Measured dissolved oxygen mg/L.")
    parser.add_argument("--tan-mg-l", type=float, default=0.8, help="Measured Total Ammonia Nitrogen mg/L.")
    parser.add_argument("--elevation-m", type=float, default=1134.0, help="Site altitude m above sea level.")
    parser.add_argument("--aerated", action="store_true", help="Mechanical aeration active.")
    args = parser.parse_args(argv)

    prof = get_species_profile(args.species)
    chem = audit_pond_chemistry(
        WaterReading(
            temp_c=args.temp_c,
            ph=args.ph,
            dissolved_oxygen_mg_l=args.do_mg_l,
            tan_mg_l=args.tan_mg_l,
            elevation_m=args.elevation_m,
        ),
        min_safe_do_mg_l=prof.min_safe_do_mg_l,
    )
    plan = plan_pond_operations(
        PondSpec(
            species=args.species,
            volume_m3=args.volume_m3,
            fish_count=args.fish_count,
            avg_fish_weight_g=args.avg_weight_g,
            water_temp_c=args.temp_c,
            aerated=args.aerated,
        )
    )
    print(json.dumps({"water_chemistry": asdict(chem), "pond_plan": asdict(plan)}, indent=2))
    has_danger = chem.ammonia_status == "acute_lethal" or chem.oxygen_status == "critical_hypoxia"
    return 1 if has_danger else 0


if __name__ == "__main__":
    raise SystemExit(main())
