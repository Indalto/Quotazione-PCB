from __future__ import annotations

import json
from typing import Any
from dataclasses import asdict

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox, QVBoxLayout,
    QPushButton, QTabWidget, QHBoxLayout, QGroupBox, QLabel,
    QTableWidget, QTableWidgetItem, QDialog, QDialogButtonBox, QGridLayout,
    QHeaderView, QSizePolicy, QAbstractItemView, QSplitter, QFileDialog, QMessageBox
)

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from pcb_quote.models import (
    LayoutQuoteInputs, BoardConstraints, HoleType, KeepoutRect,
    ComponentsInputs, HighSpeedInputs, HighSpeedInterface, Tariffs
)
from pcb_quote.calculations import estimate_layout_quote, QuoteCoeffs, DEFAULT_COEFFS


# ---------- Helpers UI ----------
def groupbox(title: str, layout) -> QGroupBox:
    b = QGroupBox(title)
    b.setLayout(layout)
    return b


def _note_label(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #5a6b7b; font-size: 9pt;")
    return lbl


def _ro_item(s: str) -> QTableWidgetItem:
    it = QTableWidgetItem(str(s))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    return it


def _num_item(val: str) -> QTableWidgetItem:
    it = QTableWidgetItem(val)
    it.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
    return it


def _text_item(val: str) -> QTableWidgetItem:
    it = QTableWidgetItem(val)
    it.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    return it


def _configure_table(tbl: QTableWidget, stretch_last: bool = True):
    tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    tbl.setAlternatingRowColors(True)
    tbl.setShowGrid(True)
    tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    vh = tbl.verticalHeader()
    vh.setVisible(True)
    vh.setDefaultSectionSize(30)
    vh.setMinimumSectionSize(18)
    vh.setSectionResizeMode(QHeaderView.Interactive)
    vh.setSectionsMovable(True)

    hh = tbl.horizontalHeader()
    hh.setStretchLastSection(stretch_last)
    hh.setSectionResizeMode(QHeaderView.Interactive)
    hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    hh.setSectionsMovable(True)
    hh.setFixedHeight(32)

    tbl.setWordWrap(True)
    tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
    tbl.setSelectionMode(QAbstractItemView.SingleSelection)


def make_table_interactive(tbl: QTableWidget):
    tbl.horizontalHeader().setSectionsMovable(True)
    tbl.verticalHeader().setSectionsMovable(True)
    tbl.setDragEnabled(True)
    tbl.setAcceptDrops(True)
    tbl.setDragDropMode(QAbstractItemView.InternalMove)
    tbl.setDropIndicatorShown(True)
    tbl.setDefaultDropAction(Qt.MoveAction)
    tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
    tbl.setSelectionMode(QAbstractItemView.SingleSelection)


# ---------- Parsers tolleranti ----------
def _parse_hole_entry(h: Any):
    try:
        if isinstance(h, HoleType):
            return h
        if hasattr(h, "diameter_mm") or hasattr(h, "diameter"):
            diameter = getattr(h, "diameter_mm", getattr(h, "diameter", 0.0))
            metall = getattr(h, "metallization_mm", getattr(h, "metallization", 0.0))
            count = getattr(h, "count", getattr(h, "qty", 1))
            return HoleType(diameter_mm=float(diameter), metallization_mm=float(metall), count=int(count))
        if isinstance(h, dict):
            diameter = h.get("diameter_mm", h.get("diameter", 0.0))
            metall = h.get("metallization_mm", h.get("metallization", 0.0))
            count = h.get("count", h.get("qty", 1))
            return HoleType(diameter_mm=float(diameter), metallization_mm=float(metall), count=int(count))
        if isinstance(h, (list, tuple)):
            if len(h) == 2:
                diameter, count = h
                return HoleType(diameter_mm=float(diameter), metallization_mm=0.0, count=int(count))
            if len(h) >= 3:
                diameter, metall, count = h[0], h[1], h[2]
                return HoleType(diameter_mm=float(diameter), metallization_mm=float(metall), count=int(count))
    except Exception:
        pass
    return None


def _parse_keepout_entry(k: Any):
    try:
        if isinstance(k, KeepoutRect):
            return k
        if hasattr(k, "side"):
            side = getattr(k, "side", "TOP")
            w = getattr(k, "width_mm", getattr(k, "width", 0.0))
            h = getattr(k, "height_mm", getattr(k, "height", 0.0))
            c = getattr(k, "count", getattr(k, "qty", 1))
            return KeepoutRect(side=str(side).upper(), width_mm=float(w), height_mm=float(h), count=int(c))
        if isinstance(k, dict):
            side = k.get("side", "TOP")
            w = k.get("width_mm", k.get("width", 0.0))
            h = k.get("height_mm", k.get("height", 0.0))
            c = k.get("count", k.get("qty", 1))
            return KeepoutRect(side=str(side).upper(), width_mm=float(w), height_mm=float(h), count=int(c))
        if isinstance(k, (list, tuple)):
            if len(k) == 4:
                side, w, h, c = k
                return KeepoutRect(side=str(side).upper(), width_mm=float(w), height_mm=float(h), count=int(c))
            if len(k) == 3:
                w, h, c = k
                return KeepoutRect(side="TOP", width_mm=float(w), height_mm=float(h), count=int(c))
    except Exception:
        pass
    return None


def _parse_hs_entry(it: Any):
    try:
        if isinstance(it, HighSpeedInterface):
            return it
        if hasattr(it, "name"):
            return HighSpeedInterface(
                name=str(getattr(it, "name", "IF")),
                data_rate_gbps=float(getattr(it, "data_rate_gbps", getattr(it, "gbps", 0.0))),
                diff_pairs=int(getattr(it, "diff_pairs", getattr(it, "dp", 0))),
                se_lines=int(getattr(it, "se_lines", getattr(it, "se", 0))),
                match_ps=float(getattr(it, "match_ps", getattr(it, "ps", 50.0))),
            )
        if isinstance(it, dict):
            return HighSpeedInterface(
                name=str(it.get("name", it.get("nome", "IF"))),
                data_rate_gbps=float(it.get("data_rate_gbps", it.get("gbps", 0.0))),
                diff_pairs=int(it.get("diff_pairs", it.get("dp", 0))),
                se_lines=int(it.get("se_lines", it.get("se", 0))),
                match_ps=float(it.get("match_ps", it.get("ps", 50.0))),
            )
        if isinstance(it, (list, tuple)):
            if len(it) >= 5:
                name, gbps, dp, se, ps = it[:5]
            elif len(it) == 4:
                name, gbps, dp, se = it
                ps = 50.0
            elif len(it) == 3:
                name, gbps, dp = it
                se = 0; ps = 50.0
            elif len(it) == 2:
                name, gbps = it
                dp = 0; se = 0; ps = 50.0
            else:
                return None
            return HighSpeedInterface(name=str(name), data_rate_gbps=float(gbps), diff_pairs=int(dp), se_lines=int(se), match_ps=float(ps))
    except Exception:
        pass
    return None


# ---------- CoeffsDialog ----------
class CoeffsDialog(QDialog):
    def __init__(self, coeffs: QuoteCoeffs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coefficienti di stima (calibrabili)")
        self.coeffs = coeffs

        outer = QVBoxLayout(self)
        outer.addWidget(_note_label("Modifica i coefficienti del modello. I valori in minuti verranno convertiti internamente in ore."))

        grid = QGridLayout()
        outer.addLayout(grid)
        self._fields = {}

        def add_row(r: int, key: str, label: str, desc: str, value: float, minv=0.0, maxv=1e6, step=0.01, decimals=4):
            lab = QLabel(label); lab.setStyleSheet("font-weight: 600;")
            sp = QDoubleSpinBox()
            sp.setRange(minv, maxv)
            sp.setDecimals(decimals)
            sp.setSingleStep(step)
            sp.setValue(float(value))
            note = _note_label(desc)
            grid.addWidget(lab, r, 0)
            grid.addWidget(sp, r, 1)
            grid.addWidget(note, r, 2)
            self._fields[key] = sp

        c = coeffs
        r = 0
        add_row(r, "sys_study_system_h", "Studio sistema e analisi documentazione (ore)", "Analisi iniziale requisiti e documentazione.", c.sys_study_system_h, 0, 200, 0.5, 2); r += 1
        add_row(r, "sys_setup_pcb_h", "Setup iniziale PCB (ore)", "Definizione stack-up, net-classes e vincoli EDA.", c.sys_setup_pcb_h, 0, 200, 0.5, 2); r += 1
        add_row(r, "sys_mech_study_h", "Studio meccanico (ore)", "Analisi vincoli meccanici, fori speciali e interfaccie meccaniche.", c.sys_mech_study_h, 0, 200, 0.5, 2); r += 1
        add_row(r, "sys_dfm_documentation_h", "Documentazione di fabbricazione (ore)", "Tempo fisso per preparare i deliverable per produzione.", c.sys_dfm_documentation_h, 0, 200, 0.5, 2); r += 1

        add_row(r, "k_place_bga_base_h", "Placement base BGA (ore)", "Overhead iniziale per gestione BGA e regole.", c.k_place_bga_base_h, 0, 500, 0.5, 2); r += 1
        add_row(r, "k_place_per_bga_h", "Placement per BGA (ore)", "Ore addizionali per ogni BGA.", c.k_place_per_bga_h, 0, 100, 0.25, 2); r += 1
        add_row(r, "k_place_pins_per_100_min", "Placement per 100 pin BGA (min)", "Minuti per gestire 100 pin BGA.", c.k_place_pins_per_100_min, 0, 600, 1.0, 2); r += 1

        add_row(r, "k_place_passive_min", "Placement per passivo (min/pezzo)", "Minuti medi per piazzare un passivo.", c.k_place_passive_min, 0, 10, 0.01, 3); r += 1
        add_row(r, "k_place_active_min", "Placement per attivo (min/pezzo)", "Minuti medi per piazzare un componente attivo.", c.k_place_active_min, 0, 60, 0.1, 2); r += 1
        add_row(r, "k_place_critical_min", "Placement per critico (min/pezzo)", "Minuti per componenti critici.", c.k_place_critical_min, 0, 300, 0.1, 2); r += 1
        add_row(r, "k_place_connector_min", "Placement per connettore (min/pezzo)", "Minuti medi per connettori (meccanica + routing).", c.k_place_connector_min, 0, 120, 0.1, 2); r += 1

        add_row(r, "k_hdi_multiplier", "Moltiplicatore HDI", "Moltiplicatore applicato se la board è HDI.", c.k_hdi_multiplier, 1.0, 5.0, 0.01, 2); r += 1

        add_row(r, "k_route_std_base_h", "Routing STD base (ore)", "Ore base per routing standard.", c.k_route_std_base_h, 0, 2000, 0.5, 2); r += 1
        add_row(r, "k_route_density_scale_h", "Routing STD per densità (ore)", "Scala il routing STD con la densità effettiva.", c.k_route_density_scale_h, 0, 2000, 0.5, 2); r += 1
        add_row(r, "k_route_trace_min", "Sbroglio per traccia (min/traccia)", "Minuti per traccia.", c.k_route_trace_min, 0.01, 10.0, 0.01, 3); r += 1

        add_row(r, "k_route_diff_pair_min", "Routing HS: coppia diff (min/coppia)", "Minuti per coppia diff (prima di severity).", c.k_route_diff_pair_min, 0, 1000, 0.5, 2); r += 1
        add_row(r, "k_route_se_min", "Routing HS: linea SE (min/linea)", "Minuti per linea single-ended.", c.k_route_se_min, 0, 500, 0.1, 2); r += 1

        add_row(r, "k_si_base_h", "SI/PI base (ore)", "Ore base per attività SI/PI.", c.k_si_base_h, 0, 2000, 0.5, 2); r += 1
        add_row(r, "k_si_per_interface_min", "SI per interfaccia (min/interfaccia)", "Minuti addizionali SI per ogni interfaccia HS.", c.k_si_per_interface_min, 0, 5000, 1.0, 2); r += 1
        add_row(r, "k_si_rate_multiplier", "Moltiplicatore SI per data-rate", "Scala la parte SI legata al data-rate.", c.k_si_rate_multiplier, 0.0, 10.0, 0.01, 2); r += 1

        add_row(r, "k_cleanup_pct", "Cleanup / Revisione pre-produzione (%)", "Percentuale applicata a (placement + routing).", c.k_cleanup_pct, 0.0, 1.0, 0.01, 4); r += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def get_coeffs(self) -> QuoteCoeffs:
        d = {k: float(w.value()) for k, w in self._fields.items()}
        return QuoteCoeffs(**d)


# ---------- GeneralTab ----------
class GeneralTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        self.tar_layout = QDoubleSpinBox(); self.tar_layout.setRange(1, 2000); self.tar_layout.setValue(75); self.tar_layout.setSuffix(" €/h")
        self.tar_si = QDoubleSpinBox(); self.tar_si.setRange(1, 2000); self.tar_si.setValue(90); self.tar_si.setSuffix(" €/h")
        self.buffer = QDoubleSpinBox(); self.buffer.setDecimals(2); self.buffer.setRange(0, 2.0); self.buffer.setValue(0.25)
        self.week_hours = QDoubleSpinBox(); self.week_hours.setRange(1, 80); self.week_hours.setValue(40); self.week_hours.setSuffix(" h")

        form.addRow("Tariffa Layout", self.tar_layout)
        form.addRow("Tariffa SI/PI", self.tar_si)
        form.addRow("Buffer (0.25 = 25%)", self.buffer)
        form.addRow("Ore per settimana", self.week_hours)

        outer.addWidget(groupbox("Generale", form))
        outer.addStretch()


# ---------- BoardTab ----------
class BoardTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        dim_form = QFormLayout()
        dim_form.setLabelAlignment(Qt.AlignRight)
        dim_form.setFormAlignment(Qt.AlignTop)
        self.w_mm = QDoubleSpinBox(); self.w_mm.setRange(1, 5000); self.w_mm.setValue(180); self.w_mm.setSuffix(" mm")
        self.h_mm = QDoubleSpinBox(); self.h_mm.setRange(1, 5000); self.h_mm.setValue(140); self.h_mm.setSuffix(" mm")
        dim_form.addRow("PCB Width", self.w_mm)
        dim_form.addRow("PCB Height", self.h_mm)
        outer.addWidget(groupbox("Dimensioni", dim_form))

        row = QHBoxLayout(); row.setSpacing(12)

        holes_box = QGroupBox("Fori (per tipo)"); holes_v = QVBoxLayout(holes_box)
        holes_btn = QHBoxLayout(); self.hole_add = QPushButton("Aggiungi"); self.hole_del = QPushButton("Rimuovi")
        holes_btn.addWidget(self.hole_add); holes_btn.addWidget(self.hole_del); holes_btn.addStretch()
        self.holes_table = QTableWidget(0, 3); self.holes_table.setHorizontalHeaderLabels(["Diametro (mm)", "Metallizzazione (mm)", "Quantità"])
        _configure_table(self.holes_table); make_table_interactive(self.holes_table)
        for c in range(3): self.holes_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Interactive)
        holes_v.addLayout(holes_btn); holes_v.addWidget(self.holes_table)

        keep_box = QGroupBox("Keep-out (rettangoli)"); keep_v = QVBoxLayout(keep_box)
        keep_btn = QHBoxLayout(); self.keep_add = QPushButton("Aggiungi"); self.keep_del = QPushButton("Rimuovi")
        keep_btn.addWidget(self.keep_add); keep_btn.addWidget(self.keep_del); keep_btn.addStretch()
        self.keep_table = QTableWidget(0, 4); self.keep_table.setHorizontalHeaderLabels(["Lato", "W (mm)", "H (mm)", "Qty"])
        _configure_table(self.keep_table); make_table_interactive(self.keep_table)
        for c in range(4): self.keep_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Interactive)
        keep_v.addLayout(keep_btn); keep_v.addWidget(self.keep_table)

        row.addWidget(holes_box, 1); row.addWidget(keep_box, 1)
        outer.addLayout(row)

        summary_box = QGroupBox("Riepilogo Area (calcolato)"); summary_layout = QVBoxLayout(summary_box)
        self.summary_table = QTableWidget(6, 3); self.summary_table.setHorizontalHeaderLabels(["Voce", "TOP", "BOTTOM"])
        self.summary_table.verticalHeader().setVisible(False); _configure_table(self.summary_table); make_table_interactive(self.summary_table)
        self.summary_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for c in range(3): self.summary_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Interactive)
        summary_layout.addWidget(self.summary_table); outer.addWidget(summary_box)

        self.hole_add.clicked.connect(lambda: self.add_hole_row(3.2, 0.0, 1)); self.hole_del.clicked.connect(self.del_hole_row)
        self.keep_add.clicked.connect(lambda: self.add_keepout_row("TOP", 10, 10, 1)); self.keep_del.clicked.connect(self.del_keepout_row)

        self._debounce = QTimer(self); self._debounce.setSingleShot(True); self._debounce.setInterval(200); self._debounce.timeout.connect(self.update_area_summary)
        self.w_mm.valueChanged.connect(self._schedule_update); self.h_mm.valueChanged.connect(self._schedule_update)
        self.holes_table.itemChanged.connect(self._schedule_update); self.keep_table.itemChanged.connect(self._schedule_update)

        self.add_hole_row(3.2, 0.0, 4); self.add_keepout_row("TOP", 20, 10, 2); self.add_keepout_row("BOTTOM", 15, 8, 2); self.update_area_summary()

    def _schedule_update(self): self._debounce.start()

    def add_hole_row(self, diameter: float = 3.2, metall: float = 0.0, count: int = 1):
        r = self.holes_table.rowCount(); self.holes_table.insertRow(r)
        self.holes_table.setItem(r, 0, _num_item(f"{float(diameter):.2f}")); self.holes_table.setItem(r, 1, _num_item(f"{float(metall):.3f}")); self.holes_table.setItem(r, 2, _num_item(str(int(count))))

    def del_hole_row(self):
        r = self.holes_table.currentRow()
        if r >= 0: self.holes_table.removeRow(r); self._schedule_update()

    def add_keepout_row(self, side: str = "TOP", w: float = 10.0, h: float = 10.0, count: int = 1):
        r = self.keep_table.rowCount(); self.keep_table.insertRow(r)
        self.keep_table.setItem(r, 0, _text_item(side)); self.keep_table.setItem(r, 1, _num_item(f"{float(w):.2f}")); self.keep_table.setItem(r, 2, _num_item(f"{float(h):.2f}")); self.keep_table.setItem(r, 3, _num_item(str(int(count))))

    def del_keepout_row(self):
        r = self.keep_table.currentRow()
        if r >= 0: self.keep_table.removeRow(r); self._schedule_update()

    def collect_holes(self):
        holes = []
        for r in range(self.holes_table.rowCount()):
            d_txt = self.holes_table.item(r, 0).text().strip() if self.holes_table.item(r, 0) else "0"
            m_txt = self.holes_table.item(r, 1).text().strip() if self.holes_table.item(r, 1) else "0"
            c_txt = self.holes_table.item(r, 2).text().strip() if self.holes_table.item(r, 2) else "0"
            try:
                d = float(d_txt); m = float(m_txt); c = int(float(c_txt))
            except Exception:
                continue
            if d > 0 and c > 0:
                holes.append(HoleType(diameter_mm=d, metallization_mm=m, count=c))
        return holes

    def collect_keepouts(self):
        keepouts = []
        for r in range(self.keep_table.rowCount()):
            s = (self.keep_table.item(r, 0).text().strip() if self.keep_table.item(r, 0) else "TOP").upper()
            w_txt = self.keep_table.item(r, 1).text().strip() if self.keep_table.item(r, 1) else "0"
            h_txt = self.keep_table.item(r, 2).text().strip() if self.keep_table.item(r, 2) else "0"
            c_txt = self.keep_table.item(r, 3).text().strip() if self.keep_table.item(r, 3) else "1"
            try:
                w = float(w_txt); h = float(h_txt); c = int(float(c_txt))
            except Exception:
                continue
            if w > 0 and h > 0 and c > 0:
                keepouts.append(KeepoutRect(side=s, width_mm=w, height_mm=h, count=c))
        return keepouts

    def update_area_summary(self):
        board = BoardConstraints(width_mm=float(self.w_mm.value()), height_mm=float(self.h_mm.value()), holes=self.collect_holes(), keepouts=self.collect_keepouts())
        def set_row(row: int, label: str, top: str, bottom: str):
            self.summary_table.setItem(row, 0, _ro_item(label)); self.summary_table.setItem(row, 1, _ro_item(top)); self.summary_table.setItem(row, 2, _ro_item(bottom))
        holes_cm2 = board.holes_area_mm2 / 100.0
        set_row(0, "Area lorda (cm²)", f"{board.gross_cm2:.1f}", f"{board.gross_cm2:.1f}")
        set_row(1, "Area fori (cm²)", f"{holes_cm2:.1f}", f"{holes_cm2:.1f}")
        set_row(2, "Keep-out (cm²)", f"{board.keepout_top_mm2/100.0:.1f}", f"{board.keepout_bottom_mm2/100.0:.1f}")
        set_row(3, "Superficie Utile (cm²)", f"{board.usable_top_cm2:.1f}", f"{board.usable_bottom_cm2:.1f}")
        set_row(4, "Occupazione %", f"{board.occupied_top_pct:.1f}%", f"{board.occupied_bottom_pct:.1f}%")
        set_row(5, "Spazio libero %", f"{board.free_top_pct:.1f}%", f"{board.free_bottom_pct:.1f}%")
        self.summary_table.resizeRowsToContents()
        header_h = self.summary_table.horizontalHeader().height()
        rows_h = sum(self.summary_table.rowHeight(r) for r in range(self.summary_table.rowCount()))
        frame = self.summary_table.frameWidth() * 2; extra = 8
        total_min_h = header_h + rows_h + frame + extra
        self.summary_table.setMinimumHeight(total_min_h)


# ---------- ComponentsTab ----------
class ComponentsTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        self.bga_count = QSpinBox(); self.bga_count.setRange(0, 1000); self.bga_count.setValue(3)
        self.bga_pins = QSpinBox(); self.bga_pins.setRange(0, 500000); self.bga_pins.setValue(1443)
        self.pitch = QDoubleSpinBox(); self.pitch.setDecimals(2); self.pitch.setRange(0.3, 2.0); self.pitch.setValue(0.8); self.pitch.setSuffix(" mm")
        self.layers = QSpinBox(); self.layers.setRange(2, 40); self.layers.setValue(12)
        self.hdi = QCheckBox("HDI (richiede competenze aggiuntive)"); self.hdi.setChecked(True)
        self.tht = QCheckBox("THT (tecnologia PCB — nessun effort aggiuntivo)"); self.tht.setChecked(False)

        flags = QWidget(); hb = QHBoxLayout(flags); hb.setContentsMargins(0, 0, 0, 0)
        hb.addWidget(self.hdi); hb.addWidget(self.tht); hb.addStretch()

        form.addRow("Numero BGA", self.bga_count)
        form.addRow("Pin BGA totali (effettivi)", self.bga_pins)
        form.addRow("Pitch minimo BGA", self.pitch)
        form.addRow("Layers", self.layers)
        form.addRow("Tecnologia", flags)

        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight); form2.setFormAlignment(Qt.AlignTop)
        self.passives = QSpinBox(); self.passives.setRange(0, 500000); self.passives.setValue(800)
        self.actives = QSpinBox(); self.actives.setRange(0, 200000); self.actives.setValue(40)
        self.critical = QSpinBox(); self.critical.setRange(0, 200000); self.critical.setValue(6)
        self.connectors = QSpinBox(); self.connectors.setRange(0, 200000); self.connectors.setValue(12)
        form2.addRow("Passivi (n)", self.passives); form2.addRow("Attivi (n)", self.actives); form2.addRow("Critici (n)", self.critical); form2.addRow("Connettori (n)", self.connectors)

        outer.addWidget(groupbox("BGA / Stack", form))
        outer.addWidget(groupbox("Conteggi componenti", form2))
        outer.addStretch()


# ---------- HighSpeedTab (table sopra, chart sotto) ----------
class HighSpeedTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.addWidget(_note_label("Ogni riga = una interfaccia (JESD, DDR, Ethernet...). Matching ps: più basso = più complesso."))

        splitter = QSplitter(Qt.Vertical)

        top = QWidget(); top_layout = QVBoxLayout(top)
        btn_row = QHBoxLayout(); self.add_btn = QPushButton("Aggiungi"); self.del_btn = QPushButton("Rimuovi")
        btn_row.addWidget(self.add_btn); btn_row.addWidget(self.del_btn); btn_row.addStretch()
        top_layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nome", "Gbps", "Diff pairs", "SE lines", "Match (ps)", "Ore"])
        _configure_table(self.table); make_table_interactive(self.table)
        for c in range(6): self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Interactive)
        top_layout.addWidget(self.table)

        bottom = QWidget(); bottom_layout = QVBoxLayout(bottom)
        self.pie_fig = Figure(figsize=(6, 3)); self.pie_canvas = FigureCanvas(self.pie_fig)
        bottom_layout.addWidget(self.pie_canvas)

        splitter.addWidget(top); splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 2); splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter)

        self.add_btn.clicked.connect(lambda: self.add_row(("Interface", 10.0, 0, 0, 10.0)))
        self.del_btn.clicked.connect(self.del_row)
        self.add_row(("JESD204", 10.0, 32, 0, 10.0))

    def add_row(self, defaults=("Interface", 10.0, 0, 0, 10.0)):
        r = self.table.rowCount(); self.table.insertRow(r)
        name, gbps, dp, se, ps = defaults
        self.table.setItem(r, 0, _text_item(str(name))); self.table.setItem(r, 1, _num_item(f"{float(gbps):.2f}"))
        self.table.setItem(r, 2, _num_item(str(int(dp)))); self.table.setItem(r, 3, _num_item(str(int(se))))
        self.table.setItem(r, 4, _num_item(f"{float(ps):.2f}")); self.table.setItem(r, 5, _ro_item("0.0"))
        self._adjust_table_height()

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0: self.table.removeRow(r); self._adjust_table_height()

    def _adjust_table_height(self, max_visible_rows: int = 12):
        rows = max(1, min(self.table.rowCount(), max_visible_rows))
        row_h = self.table.verticalHeader().defaultSectionSize()
        header_h = self.table.horizontalHeader().height()
        frame = self.table.frameWidth() * 2
        total_h = header_h + rows * row_h + frame + 12
        self.table.setMinimumHeight(total_h)

    def collect_interfaces(self):
        itfs = []
        for r in range(self.table.rowCount()):
            def cell(c: int) -> str:
                return self.table.item(r, c).text().strip() if self.table.item(r, c) else ""
            name = cell(0) or f"IF{r+1}"
            try:
                gbps = float(cell(1) or 0.0); dp = int(float(cell(2) or 0)); se = int(float(cell(3) or 0)); ps = float(cell(4) or 50.0)
            except ValueError:
                continue
            itfs.append(HighSpeedInterface(name=name, data_rate_gbps=gbps, diff_pairs=dp, se_lines=se, match_ps=ps))
        return itfs

    def update_from_results(self, res: dict):
        hs = res.get("highspeed", {}).get("interfaces", [])
        self.table.setRowCount(len(hs))
        labels = []; sizes = []
        for r, it in enumerate(hs):
            self.table.setItem(r, 0, _ro_item(it["name"])); self.table.setItem(r, 1, _ro_item(f"{it['data_rate_gbps']:.2f}"))
            self.table.setItem(r, 2, _ro_item(str(int(it["diff_pairs"])))); self.table.setItem(r, 3, _ro_item(str(int(it["se_lines"]))))
            self.table.setItem(r, 4, _ro_item(f"{it['match_ps']:.2f}"))
            hrs = it.get("hours_total", 0.0); self.table.setItem(r, 5, _ro_item(f"{hrs:.1f}"))
            labels.append(it["name"]); sizes.append(max(0.0, float(hrs)))

        self._adjust_table_height(max_visible_rows=20)
        fig = self.pie_fig; fig.clear(); ax = fig.add_subplot(111)
        if sum(sizes) > 0:
            wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct="%1.1f%%", startangle=90)
            ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5))
            ax.set_title("Ore per interfaccia (HS)"); ax.axis('equal')
        else:
            ax.text(0.5, 0.5, "Nessuna ora calcolata", ha='center', va='center'); ax.set_title("Ore per interfaccia (HS)")
        fig.tight_layout(); self.pie_canvas.draw()


# ---------- ResultsTab (solo Totals + 2 charts) ----------
class ResultsTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        grid = QGridLayout(); grid.setSpacing(12)

        self.totals_table = QTableWidget(0, 5)
        self.totals_table.setHorizontalHeaderLabels(["Attività", "Ore", "Weeks", "Rate €/h", "Costo €"])
        _configure_table(self.totals_table); make_table_interactive(self.totals_table)

        self.pie_hours_fig = Figure(figsize=(5, 4)); self.pie_hours_canvas = FigureCanvas(self.pie_hours_fig)
        self.pie_cost_fig = Figure(figsize=(5, 4)); self.pie_cost_canvas = FigureCanvas(self.pie_cost_fig)

        grid.addWidget(groupbox("Riepilogo Totali (somma voci rilevanti)", QVBoxLayout()), 0, 0)
        grid.itemAtPosition(0, 0).widget().layout().addWidget(self.totals_table)
        grid.addWidget(self.pie_hours_canvas, 0, 1)
        grid.addWidget(self.pie_cost_canvas, 1, 1)

        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1); grid.setRowStretch(1, 1)
        outer.addLayout(grid)

    def set_results(self, res: dict):
        bd = res.get("breakdown", {})
        hours = bd.get("hours_with_buffer", {})
        weeks = bd.get("weeks_with_buffer", {})
        costs = bd.get("costs_with_buffer", {})
        rates = bd.get("rates", {})

        totals_order = ["Placement", "Routing HS", "Routing STD", "SI/PI", "DFM Documentation (fixed)", "DFM/Cleanup (proportional)"]
        labels_it = {
            "Placement": "Placement",
            "Routing HS": "Routing HS",
            "Routing STD": "Routing STD",
            "SI/PI": "SI/PI",
            "DFM Documentation (fixed)": "DFM - Documentazione (fissa)",
            "DFM/Cleanup (proportional)": "DFM - Cleanup (proporz.)"
        }

        self.totals_table.setRowCount(len(totals_order) + 1)
        for r, k in enumerate(totals_order):
            hrs = hours.get(k, 0.0); wks = weeks.get(k, 0.0); cost = costs.get(k, 0.0)
            rate_col = rates.get("si_pi") if k == "SI/PI" else rates.get("layout", 0.0)
            self.totals_table.setItem(r, 0, _ro_item(labels_it.get(k, k)))
            self.totals_table.setItem(r, 1, _ro_item(f"{hrs:.1f}"))
            self.totals_table.setItem(r, 2, _ro_item(f"{wks:.2f}"))
            self.totals_table.setItem(r, 3, _ro_item(f"{rate_col:.0f}"))
            self.totals_table.setItem(r, 4, _ro_item(f"{cost:.0f}"))

        total_h = bd.get("totals", {}).get("hours", 0.0); total_w = bd.get("totals", {}).get("weeks", 0.0); total_c = bd.get("totals", {}).get("cost", 0.0)
        last = len(totals_order)
        item0 = _ro_item("TOTAL"); item1 = _ro_item(f"{total_h:.1f}"); item2 = _ro_item(f"{total_w:.2f}"); item3 = _ro_item(f"{rates.get('layout',0.0):.0f}"); item4 = _ro_item(f"{total_c:.0f}")
        bold_font = QFont(); bold_font.setBold(True)
        for it in (item0, item1, item2, item3, item4): it.setFont(bold_font); it.setForeground(QBrush(QColor("#c0392b")))
        self.totals_table.setItem(last, 0, item0); self.totals_table.setItem(last, 1, item1); self.totals_table.setItem(last, 2, item2); self.totals_table.setItem(last, 3, item3); self.totals_table.setItem(last, 4, item4)
        self.totals_table.resizeRowsToContents()
        self._adjust_table_height(self.totals_table, max_visible_rows=8)

        # pie hours
        labels = []; sizes = []
        for k in totals_order:
            v = hours.get(k, 0.0)
            if v > 0: labels.append(labels_it.get(k, k)); sizes.append(float(v))
        fig = self.pie_hours_fig; fig.clear(); ax = fig.add_subplot(111)
        if sum(sizes) > 0:
            wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct="%1.1f%%", startangle=90)
            ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5)); ax.set_title("Distribuzione ore"); ax.axis('equal')
        else:
            ax.text(0.5, 0.5, "Nessuna ora", ha='center', va='center'); ax.set_title("Distribuzione ore")
        fig.tight_layout(); self.pie_hours_canvas.draw()

        # pie cost
        labels_c = []; sizes_c = []
        for k in totals_order:
            v = costs.get(k, 0.0)
            if v > 0: labels_c.append(labels_it.get(k, k)); sizes_c.append(float(v))
        fig2 = self.pie_cost_fig; fig2.clear(); ax2 = fig2.add_subplot(111)
        if sum(sizes_c) > 0:
            wedges, texts, autotexts = ax2.pie(sizes_c, labels=None, autopct="%1.1f%%", startangle=90)
            ax2.legend(wedges, labels_c, loc="center left", bbox_to_anchor=(1.0, 0.5)); ax2.set_title("Distribuzione costo per attività"); ax2.axis('equal')
        else:
            ax2.text(0.5, 0.5, "Nessun costo calcolato", ha='center', va='center'); ax2.set_title("Distribuzione costo per attività")
        fig2.tight_layout(); self.pie_cost_canvas.draw()

    def _adjust_table_height(self, tbl: QTableWidget, max_visible_rows: int = 8):
        rows = max(1, min(tbl.rowCount(), max_visible_rows))
        row_h = tbl.verticalHeader().defaultSectionSize()
        header_h = tbl.horizontalHeader().height()
        frame = tbl.frameWidth() * 2
        total_h = header_h + rows * row_h + frame + 12
        tbl.setMinimumHeight(total_h)


# ---------- QuoteForm main (usa le classi definite sopra) ----------
class QuoteForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.coeffs: QuoteCoeffs = DEFAULT_COEFFS

        vbox = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.general = GeneralTab()
        self.board = BoardTab()
        self.components = ComponentsTab()
        self.hs = HighSpeedTab()
        self.results = ResultsTab()

        self.tabs.addTab(self.general, "Generale")
        self.tabs.addTab(self.board, "Board/Meccanica")
        self.tabs.addTab(self.components, "Componenti")
        self.tabs.addTab(self.hs, "High-speed")
        self.tabs.addTab(self.results, "Risultati")
        vbox.addWidget(self.tabs)

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("Carica")
        self.coeffs_btn = QPushButton("Coefficienti…")
        self.coeffs_btn.setStyleSheet("background:#e74c3c; border:1px solid #c0392b;")
        self.save_btn = QPushButton("Salva")
        self.refresh_btn = QPushButton("Aggiorna")
        btn_row.addStretch()
        btn_row.addWidget(self.load_btn); btn_row.addWidget(self.coeffs_btn); btn_row.addWidget(self.save_btn); btn_row.addWidget(self.refresh_btn)
        vbox.addLayout(btn_row)

        # collegamenti
        self.refresh_btn.clicked.connect(self.recalc)
        self.coeffs_btn.clicked.connect(self.open_coeffs_dialog)
        self.save_btn.clicked.connect(self.save_to_file)
        self.load_btn.clicked.connect(self.load_from_file)

        QTimer.singleShot(50, self.recalc)

    def open_coeffs_dialog(self):
        dlg = CoeffsDialog(self.coeffs, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.coeffs = dlg.get_coeffs()
            self.recalc()

    def collect_inputs(self) -> LayoutQuoteInputs:
        tariffs = Tariffs(layout_eur_per_h=float(self.general.tar_layout.value()), si_pi_eur_per_h=float(self.general.tar_si.value()))
        board = BoardConstraints(width_mm=float(self.board.w_mm.value()), height_mm=float(self.board.h_mm.value()), holes=self.board.collect_holes(), keepouts=self.board.collect_keepouts())
        comps = ComponentsInputs(
            bga_count=int(self.components.bga_count.value()),
            bga_total_pins_effective=int(self.components.bga_pins.value()),
            min_bga_pitch_mm=float(self.components.pitch.value()),
            passives=int(self.components.passives.value()),
            actives=int(self.components.actives.value()),
            critical=int(self.components.critical.value()),
            connectors=int(self.components.connectors.value()),
            layers=int(self.components.layers.value()),
            hdi=bool(self.components.hdi.isChecked()),
            tht=bool(self.components.tht.isChecked()),
        )
        hs = HighSpeedInputs(interfaces=self.hs.collect_interfaces())
        return LayoutQuoteInputs(board=board, components=comps, highspeed=hs, buffer_pct=float(self.general.buffer.value()), week_hours=float(self.general.week_hours.value()), tariffs=tariffs)

    def _serialize_inputs(self, inp: LayoutQuoteInputs) -> dict:
        b = inp.board; c = inp.components; hs = inp.highspeed
        return {
            "tariffs": asdict(inp.tariffs),
            "buffer_pct": float(inp.buffer_pct),
            "week_hours": float(inp.week_hours),
            "board": {
                "width_mm": float(b.width_mm),
                "height_mm": float(b.height_mm),
                "holes": [{"diameter_mm": h.diameter_mm, "metallization_mm": getattr(h, "metallization_mm", 0.0), "count": h.count} for h in getattr(b, "holes", [])],
                "keepouts": [{"side": k.side, "width_mm": k.width_mm, "height_mm": k.height_mm, "count": k.count} for k in getattr(b, "keepouts", [])],
            },
            "components": asdict(c),
            "highspeed": {"interfaces": [asdict(it) for it in getattr(hs, "interfaces", [])]},
            "coeffs": asdict(self.coeffs),
        }

    def save_to_file(self):
        try:
            inp = self.collect_inputs()
            data = self._serialize_inputs(inp)
            fname, _ = QFileDialog.getSaveFileName(self, "Salva file", "", "JSON files (*.json);;All files (*)")
            if not fname: return
            with open(fname, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Errore salvataggio", f"Errore durante il salvataggio: {e}")

    def load_from_file(self):
        try:
            fname, _ = QFileDialog.getOpenFileName(self, "Apri file", "", "JSON files (*.json);;All files (*)")
            if not fname: return
            with open(fname, "r", encoding="utf-8") as f: data = json.load(f)
            if "coeffs" in data:
                try:
                    coeffs_d = data["coeffs"]
                    self.coeffs = QuoteCoeffs(**{k: float(v) for k, v in coeffs_d.items()})
                except Exception:
                    pass
            self._robust_load_inputs(data)
        except Exception as e:
            QMessageBox.critical(self, "Errore caricamento", f"Errore durante il caricamento: {e}")

    def _robust_load_inputs(self, inp: Any):
        if isinstance(inp, dict):
            tariffs_d = inp.get("tariffs") or inp.get("tariffe") or {}
            tariffs = Tariffs(layout_eur_per_h=float(tariffs_d.get("layout_eur_per_h", tariffs_d.get("layout", 75.0))), si_pi_eur_per_h=float(tariffs_d.get("si_pi_eur_per_h", tariffs_d.get("si", 90.0))))
            buffer_pct = float(inp.get("buffer_pct", inp.get("buffer", 0.25)))
            week_hours = float(inp.get("week_hours", inp.get("week_hours", 40.0)))
            board_d = inp.get("board", {})
            width_mm = float(board_d.get("width_mm", board_d.get("width", 180.0)))
            height_mm = float(board_d.get("height_mm", board_d.get("height", 140.0)))
            holes_raw = board_d.get("holes", board_d.get("fori", []))
            keepouts_raw = board_d.get("keepouts", board_d.get("keepouts", []))
            holes_parsed = [h for h in (_parse_hole_entry(x) for x in holes_raw) if h]
            keepouts_parsed = [k for k in (_parse_keepout_entry(x) for x in keepouts_raw) if k]
            board = BoardConstraints(width_mm=width_mm, height_mm=height_mm, holes=holes_parsed, keepouts=keepouts_parsed)
            comps_d = inp.get("components", {})
            comps = ComponentsInputs(
                bga_count=int(comps_d.get("bga_count", comps_d.get("bga", 0))),
                bga_total_pins_effective=int(comps_d.get("bga_total_pins_effective", comps_d.get("bga_pins", 0))),
                min_bga_pitch_mm=float(comps_d.get("min_bga_pitch_mm", comps_d.get("pitch", 0.8))),
                passives=int(comps_d.get("passives", 0)),
                actives=int(comps_d.get("actives", 0)),
                critical=int(comps_d.get("critical", 0)),
                connectors=int(comps_d.get("connectors", 0)),
                layers=int(comps_d.get("layers", comps_d.get("layer", 12))),
                hdi=bool(comps_d.get("hdi", comps_d.get("is_hdi", False))),
                tht=bool(comps_d.get("tht", comps_d.get("is_tht", False))),
            )
            hs_raw = inp.get("highspeed", {}).get("interfaces", inp.get("highspeed", inp.get("interfaces", [])))
            hs_parsed = [h for h in (_parse_hs_entry(x) for x in hs_raw) if h]
            hs = HighSpeedInputs(interfaces=hs_parsed)
            inp_obj = LayoutQuoteInputs(board=board, components=comps, highspeed=hs, buffer_pct=buffer_pct, week_hours=week_hours, tariffs=tariffs)
        else:
            inp_obj = inp

        try:
            self.general.tar_layout.setValue(float(inp_obj.tariffs.layout_eur_per_h)); self.general.tar_si.setValue(float(inp_obj.tariffs.si_pi_eur_per_h))
            self.general.buffer.setValue(float(inp_obj.buffer_pct)); self.general.week_hours.setValue(float(inp_obj.week_hours))
        except Exception:
            pass

        try:
            self.board.w_mm.setValue(float(inp_obj.board.width_mm)); self.board.h_mm.setValue(float(inp_obj.board.height_mm))
        except Exception:
            pass

        self.board.holes_table.setRowCount(0)
        try:
            for h in getattr(inp_obj.board, "holes", []):
                hh = _parse_hole_entry(h) if not isinstance(h, HoleType) else h
                if hh: self.board.add_hole_row(hh.diameter_mm, getattr(hh, "metallization_mm", 0.0), hh.count)
        except Exception:
            pass

        self.board.keep_table.setRowCount(0)
        try:
            for k in getattr(inp_obj.board, "keepouts", []):
                kk = _parse_keepout_entry(k) if not isinstance(k, KeepoutRect) else k
                if kk: self.board.add_keepout_row(kk.side, kk.width_mm, kk.height_mm, kk.count)
        except Exception:
            pass

        self.board.update_area_summary()

        try:
            comps = inp_obj.components
            self.components.bga_count.setValue(int(comps.bga_count)); self.components.bga_pins.setValue(int(comps.bga_total_pins_effective))
            self.components.pitch.setValue(float(comps.min_bga_pitch_mm)); self.components.layers.setValue(int(comps.layers))
            self.components.hdi.setChecked(bool(comps.hdi)); self.components.tht.setChecked(bool(comps.tht))
            self.components.passives.setValue(int(comps.passives)); self.components.actives.setValue(int(comps.actives))
            self.components.critical.setValue(int(comps.critical)); self.components.connectors.setValue(int(comps.connectors))
        except Exception:
            pass

        self.hs.table.setRowCount(0)
        try:
            for it in getattr(inp_obj.highspeed, "interfaces", []):
                parsed = _parse_hs_entry(it) if not isinstance(it, HighSpeedInterface) else it
                if parsed: self.hs.add_row((parsed.name, parsed.data_rate_gbps, parsed.diff_pairs, parsed.se_lines, parsed.match_ps))
        except Exception:
            pass

        try: self.recalc()
        except Exception: pass

    def recalc(self):
        self.board.update_area_summary()
        inp = self.collect_inputs()
        res = estimate_layout_quote(inp, coeffs=self.coeffs)
        self.hs.update_from_results(res)
        self.results.set_results(res)