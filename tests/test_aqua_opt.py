"""Tests for aqua-opt."""

from __future__ import annotations

import json

import pytest

from aqua_opt import (
    PondSpec,
    WaterReading,
    audit_pond_chemistry,
    dissolved_oxygen_saturation_mg_l,
    plan_pond_operations,
    unionized_ammonia_mg_l,
)
from aqua_opt.cli import main as cli_main


def test_emerson_nh3_spikes_dramatically_at_high_ph() -> None:
    # At 25C, TAN=1.0 mg/L: pH 7.0 => ~0.0056 mg/L (safe), pH 9.0 => ~0.36 mg/L (lethal!)
    nh3_neutral = unionized_ammonia_mg_l(1.0, temp_c=25.0, ph=7.0)
    nh3_alkaline = unionized_ammonia_mg_l(1.0, temp_c=25.0, ph=9.0)
    assert nh3_neutral < 0.01
    assert nh3_alkaline > 0.30

    toxic = audit_pond_chemistry(WaterReading(temp_c=28.0, ph=9.0, dissolved_oxygen_mg_l=6.0, tan_mg_l=1.0))
    assert toxic.ammonia_status == "acute_lethal"
    assert any("ACUTE NH3 TOXICITY" in a for a in toxic.alerts)


def test_benson_krause_do_saturation_drops_at_lake_victoria_altitude() -> None:
    do_sea = dissolved_oxygen_saturation_mg_l(25.0, elevation_m=0.0)
    do_vic = dissolved_oxygen_saturation_mg_l(25.0, elevation_m=1134.0)
    # Textbook sea-level 25C freshwater DO saturation is ~8.26 mg/L
    assert do_sea == pytest.approx(8.26, abs=0.05)
    # Lake Victoria (~1134m) drops ~12-13% to ~7.2 mg/L
    assert 7.0 < do_vic < 7.4


def test_pond_overstocking_and_aerator_sizing() -> None:
    # 500 m3 un-aerated pond with 6000 tilapia @ 350g => 2100 kg => 4.2 kg/m3 (> 2.0 un-aerated limit)
    plan = plan_pond_operations(
        PondSpec(species="nile_tilapia", volume_m3=500.0, fish_count=6000, avg_fish_weight_g=350.0, aerated=False)
    )
    assert plan.overstocked is True
    assert plan.total_biomass_kg == pytest.approx(2100.0)
    assert plan.daily_feed_kg > 30.0
    assert plan.recommended_aerator_kw > 0.5
    assert any("OVERSTOCKED" in w for w in plan.warnings)


def test_cli_exit_code_on_safe_vs_toxic_pond(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["--ph", "7.4", "--tan-mg-l", "0.5", "--do-mg-l", "5.5"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["water_chemistry"]["ammonia_status"] == "safe"

    assert cli_main(["--ph", "9.1", "--tan-mg-l", "1.2", "--do-mg-l", "5.5"]) == 1
    out2 = json.loads(capsys.readouterr().out)
    assert out2["water_chemistry"]["ammonia_status"] == "acute_lethal"
