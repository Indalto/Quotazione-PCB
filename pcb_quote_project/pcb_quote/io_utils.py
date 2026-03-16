from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .models import (
    LayoutQuoteInputs, BoardConstraints, HoleType, KeepoutRect,
    ComponentsInputs, HighSpeedInputs, HighSpeedInterface, Tariffs
)
from .calculations import QuoteCoeffs, DEFAULT_COEFFS


def save_json(path: str | Path, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inputs_to_dict(inp: LayoutQuoteInputs, coeffs: QuoteCoeffs) -> Dict[str, Any]:
    return {"inputs": asdict(inp), "coeffs": asdict(coeffs)}


def dict_to_inputs(d: Dict[str, Any]) -> Tuple[LayoutQuoteInputs, QuoteCoeffs]:
    inp = LayoutQuoteInputs()
    coeffs = DEFAULT_COEFFS

    coeffs_d = d.get("coeffs")
    if isinstance(coeffs_d, dict):
        try:
            coeffs = QuoteCoeffs(**coeffs_d)
        except Exception:
            coeffs = DEFAULT_COEFFS

    inputs_d = d.get("inputs", d)
    if not isinstance(inputs_d, dict):
        return inp, coeffs

    tariffs = inputs_d.get("tariffs", {}) or {}
    inp.tariffs = Tariffs(
        layout_eur_per_h=float(tariffs.get("layout_eur_per_h", inp.tariffs.layout_eur_per_h)),
        si_pi_eur_per_h=float(tariffs.get("si_pi_eur_per_h", inp.tariffs.si_pi_eur_per_h)),
    )

    board = inputs_d.get("board", {}) or {}
    holes_list = board.get("holes", []) or []
    keepouts_list = board.get("keepouts", []) or []

    holes: List[HoleType] = []
    for h in holes_list:
        try:
            holes.append(HoleType(diameter_mm=float(h.get("diameter_mm", 0.0)), count=int(h.get("count", 0))))
        except Exception:
            continue

    keepouts: List[KeepoutRect] = []
    for k in keepouts_list:
        try:
            keepouts.append(KeepoutRect(
                side=str(k.get("side", "TOP")),
                width_mm=float(k.get("width_mm", 0.0)),
                height_mm=float(k.get("height_mm", 0.0)),
                count=int(k.get("count", 1)),
            ))
        except Exception:
            continue

    inp.board = BoardConstraints(
        width_mm=float(board.get("width_mm", inp.board.width_mm)),
        height_mm=float(board.get("height_mm", inp.board.height_mm)),
        holes=holes,
        keepouts=keepouts,
    )

    comps = inputs_d.get("components", {}) or {}
    inp.components = ComponentsInputs(
        bga_count=int(comps.get("bga_count", 0)),
        bga_total_pins_effective=int(comps.get("bga_total_pins_effective", 0)),
        min_bga_pitch_mm=float(comps.get("min_bga_pitch_mm", 0.8)),
        passives=int(comps.get("passives", 0)),
        actives=int(comps.get("actives", 0)),
        critical=int(comps.get("critical", 0)),
        connectors=int(comps.get("connectors", 0)),
        layers=int(comps.get("layers", 12)),
        hdi=bool(comps.get("hdi", True)),
        tht=bool(comps.get("tht", False)),
    )

    hs = inputs_d.get("highspeed", {}) or {}
    itfs = hs.get("interfaces", []) or []
    interfaces: List[HighSpeedInterface] = []
    for it in itfs:
        interfaces.append(HighSpeedInterface(
            name=str(it.get("name", "Interface")),
            data_rate_gbps=float(it.get("data_rate_gbps", 0.0)),
            diff_pairs=int(it.get("diff_pairs", 0)),
            se_lines=int(it.get("se_lines", 0)),
            match_ps=float(it.get("match_ps", 10.0)),
        ))
    inp.highspeed = HighSpeedInputs(interfaces=interfaces)

    inp.buffer_pct = float(inputs_d.get("buffer_pct", inp.buffer_pct))
    inp.week_hours = float(inputs_d.get("week_hours", inp.week_hours))
    return inp, coeffs