from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple

from .models import LayoutQuoteInputs


@dataclass
class QuoteCoeffs:
    # visual hint conversion only
    ps_to_mil_approx: float = 3.94

    # Placement
    k_place_bga_base_h: float = 6.0
    k_place_per_bga_h: float = 2.0
    k_place_pins_per_100_h: float = 1.0

    # Component categories
    k_place_passive_h: float = 0.002
    k_place_active_h: float = 0.03
    k_place_critical_h: float = 0.20
    k_place_connector_h: float = 0.10

    # HDI multiplier
    k_hdi_multiplier: float = 1.15

    # Routing (standard)
    k_route_std_base_h: float = 20.0
    k_route_density_scale_h: float = 18.0

    # Routing (high speed)
    k_route_diff_pair_h: float = 0.55
    k_route_se_h: float = 0.18

    # SI/PI
    k_si_base_h: float = 12.0
    k_si_per_interface_h: float = 4.0

    # NEW: SI scaling with data-rate difficulty (applied to per-interface SI)
    k_si_rate_multiplier: float = 1.0

    # DFM/Cleanup
    k_dfm_pct: float = 0.12


DEFAULT_COEFFS = QuoteCoeffs()


def ps_to_mil(ps: float, coeffs: QuoteCoeffs) -> float:
    return float(ps) * float(coeffs.ps_to_mil_approx)


def _safe_div(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return n / d


def _density_pin_per_cm2_layer_sides(inp: LayoutQuoteInputs) -> Tuple[float, float]:
    layers = max(inp.components.layers, 1)
    pins = float(inp.components.bga_total_pins_effective)
    dens_top = _safe_div(pins, float(inp.board.usable_top_cm2) * float(layers))
    dens_bottom = _safe_div(pins, float(inp.board.usable_bottom_cm2) * float(layers))
    return dens_top, dens_bottom


def _density_effective(dens_top: float, dens_bottom: float) -> float:
    # Conservative: bottleneck side dominates complexity
    return max(float(dens_top), float(dens_bottom))


def _f_pitch(pitch_mm: float) -> float:
    if pitch_mm >= 0.8:
        return 1.0
    if pitch_mm >= 0.65:
        return 1.2
    return 1.4


def _f_density(dens: float) -> float:
    if dens < 10:
        return 1.0
    if dens < 16:
        return 1.25
    return 1.55


def _f_hdi(inp: LayoutQuoteInputs, coeffs: QuoteCoeffs) -> float:
    return float(coeffs.k_hdi_multiplier) if inp.components.hdi else 1.0


def _severity_from_match_ps(match_ps: float) -> float:
    ps = float(match_ps)
    if ps >= 50:
        return 1.0
    if ps >= 20:
        return 1.2
    if ps >= 10:
        return 1.35
    if ps >= 5:
        return 1.55
    return 1.8


def _severity_from_data_rate(data_rate_gbps: float) -> float:
    gbps = float(data_rate_gbps)
    if gbps <= 2.5:
        return 1.0
    if gbps <= 6:
        return 1.15
    if gbps <= 10:
        return 1.30
    if gbps <= 16:
        return 1.50
    return 1.70


def estimate_layout_quote(inp: LayoutQuoteInputs, coeffs: QuoteCoeffs | None = None) -> Dict[str, Any]:
    coeffs = coeffs or DEFAULT_COEFFS

    dens_top, dens_bottom = _density_pin_per_cm2_layer_sides(inp)
    dens_eff = _density_effective(dens_top, dens_bottom)

    f_pitch = _f_pitch(inp.components.min_bga_pitch_mm)
    f_density = _f_density(dens_eff)
    f_hdi = _f_hdi(inp, coeffs)

    # Placement
    t_place = (
        (coeffs.k_place_bga_base_h + coeffs.k_place_per_bga_h * float(inp.components.bga_count))
        + coeffs.k_place_pins_per_100_h * (float(inp.components.bga_total_pins_effective) / 100.0)
        + coeffs.k_place_passive_h * float(inp.components.passives)
        + coeffs.k_place_active_h * float(inp.components.actives)
        + coeffs.k_place_critical_h * float(inp.components.critical)
        + coeffs.k_place_connector_h * float(inp.components.connectors)
    ) * f_pitch * f_density * f_hdi

    # High-speed routing per interface
    t_route_hs = 0.0
    hs_breakdown: List[Dict[str, Any]] = []
    for itf in inp.highspeed.interfaces:
        sev = _severity_from_match_ps(itf.match_ps) * _severity_from_data_rate(itf.data_rate_gbps)
        t_diff = float(coeffs.k_route_diff_pair_h) * float(itf.diff_pairs) * sev
        t_se = float(coeffs.k_route_se_h) * float(itf.se_lines) * sev
        t_route_hs += (t_diff + t_se)
        hs_breakdown.append({
            "name": itf.name,
            "data_rate_gbps": itf.data_rate_gbps,
            "match_ps": itf.match_ps,
            "match_mil_approx": ps_to_mil(itf.match_ps, coeffs),
            "diff_pairs": itf.diff_pairs,
            "se_lines": itf.se_lines,
            "severity": sev,
            "hours_total": t_diff + t_se,
        })

    # Standard routing uses dens_eff
    t_route_std = float(coeffs.k_route_std_base_h) * f_density + (float(coeffs.k_route_density_scale_h) * dens_eff / 10.0)
    t_route_total = t_route_hs + t_route_std

    # SI/PI: base + per-interface scaled by data-rate severity
    t_si = float(coeffs.k_si_base_h) * (1.0 + 0.15 * (f_density - 1.0))
    for itf in inp.highspeed.interfaces:
        rate_sev = _severity_from_data_rate(itf.data_rate_gbps)
        t_si += float(coeffs.k_si_per_interface_h) * float(coeffs.k_si_rate_multiplier) * rate_sev

    # DFM
    t_dfm = float(coeffs.k_dfm_pct) * (t_place + t_route_total)

    buffer_factor = 1.0 + float(inp.buffer_pct)

    hours = {
        "Placement": t_place,
        "Routing HS": t_route_hs,
        "Routing STD": t_route_std,
        "SI/PI": t_si,
        "DFM/Cleanup": t_dfm,
    }
    hours_buf = {k: v * buffer_factor for k, v in hours.items()}
    total_h = sum(hours_buf.values())

    week_hours = float(inp.week_hours) if inp.week_hours else 40.0
    weeks_buf = {k: (v / week_hours) for k, v in hours_buf.items()}
    total_w = total_h / week_hours

    layout_rate = float(inp.tariffs.layout_eur_per_h)
    si_rate = float(inp.tariffs.si_pi_eur_per_h)

    costs_buf = {}
    for k, hbuf in hours_buf.items():
        rate = si_rate if k == "SI/PI" else layout_rate
        costs_buf[k] = hbuf * rate
    total_cost = sum(costs_buf.values())

    return {
        "coeffs": asdict(coeffs),
        "inputs": asdict(inp),
        "board": {
            "gross_cm2": inp.board.gross_cm2,
            "holes_area_cm2": inp.board.holes_area_mm2 / 100.0,
            "keepout_top_cm2": inp.board.keepout_top_mm2 / 100.0,
            "keepout_bottom_cm2": inp.board.keepout_bottom_mm2 / 100.0,
            "usable_top_cm2": inp.board.usable_top_cm2,
            "usable_bottom_cm2": inp.board.usable_bottom_cm2,
            "occupied_top_pct": inp.board.occupied_top_pct,
            "occupied_bottom_pct": inp.board.occupied_bottom_pct,
            "free_top_pct": inp.board.free_top_pct,
            "free_bottom_pct": inp.board.free_bottom_pct,
        },
        "factors": {
            "density_top_pin_per_cm2_layer": dens_top,
            "density_bottom_pin_per_cm2_layer": dens_bottom,
            "density_effective": dens_eff,
            "f_pitch": f_pitch,
            "f_density": f_density,
            "f_hdi": f_hdi,
        },
        "highspeed": {"interfaces": hs_breakdown},
        "breakdown": {
            "hours_with_buffer": hours_buf,
            "weeks_with_buffer": weeks_buf,
            "costs_with_buffer": costs_buf,
            "rates": {"layout": layout_rate, "si_pi": si_rate},
            "totals": {"hours": total_h, "weeks": total_w, "cost": total_cost},
        }
    }