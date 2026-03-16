from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox, QVBoxLayout,
    QPushButton, QTabWidget, QHBoxLayout, QGroupBox, QLabel,
    QTableWidget, QTableWidgetItem, QDialog, QDialogButtonBox, QGridLayout,
    QHeaderView, QSizePolicy
)

from pcb_quote.models import (
    LayoutQuoteInputs, BoardConstraints, HoleType, KeepoutRect,
    ComponentsInputs, HighSpeedInputs, HighSpeedInterface, Tariffs
)
from pcb_quote.calculations import estimate_layout_quote, QuoteCoeffs, DEFAULT_COEFFS


def groupbox(title: str, layout) -> QGroupBox:
    box = QGroupBox(title)
    box.setLayout(layout)
    return box


def _note_label(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #5a6b7b; font-size: 9pt;")
    return lbl


def _ro_item(s: str) -> QTableWidgetItem:
    it = QTableWidgetItem(str(s))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _num_item(val: str) -> QTableWidgetItem:
    # editable numeric cell helper
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
    tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    tbl.verticalHeader().setVisible(True)
    tbl.verticalHeader().setDefaultSectionSize(28)
    tbl.verticalHeader().setMinimumSectionSize(24)

    hh = tbl.horizontalHeader()
    hh.setStretchLastSection(stretch_last)
    hh.setSectionResizeMode(QHeaderView.Interactive)

    # Keep rows tight and readable
    tbl.setWordWrap(False)


class CoeffsDialog(QDialog):
    def __init__(self, coeffs: QuoteCoeffs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coefficienti di stima (calibrabili)")
        self.coeffs = coeffs

        outer = QVBoxLayout(self)
        outer.addWidget(_note_label(
            "Modifica i coefficienti del modello.\n"
            "Calibra con consuntivi: valori più alti => più ore/costo."
        ))

        grid = QGridLayout()
        outer.addLayout(grid)
        self._fields = {}

        def add_row(r: int, key: str, label: str, desc: str, value: float, minv=0.0, maxv=1e6, step=0.01):
            lab = QLabel(label); lab.setStyleSheet("font-weight: 600;")
            sp = QDoubleSpinBox()
            sp.setRange(minv, maxv)
            sp.setDecimals(4)
            sp.setSingleStep(step)
            sp.setValue(float(value))
            note = _note_label(desc)
            grid.addWidget(lab, r, 0)
            grid.addWidget(sp, r, 1)
            grid.addWidget(note, r, 2)
            self._fields[key] = sp

        c = coeffs
        r = 0
        add_row(r, "ps_to_mil_approx", "ps→mil approx",
                "Solo visual: conversione indicativa ps→mil.", c.ps_to_mil_approx, 0.1, 50, 0.1); r += 1
        add_row(r, "k_place_bga_base_h", "Placement base (h)",
                "Overhead setup regole + iterazioni minime.", c.k_place_bga_base_h, 0, 1000, 0.5); r += 1
        add_row(r, "k_place_per_bga_h", "Placement per BGA (h)",
                "Ore add per ogni BGA.", c.k_place_per_bga_h, 0, 100, 0.25); r += 1
        add_row(r, "k_place_pins_per_100_h", "Placement per 100 pin BGA (h)",
                "Proxy breakout/escape effort.", c.k_place_pins_per_100_h, 0, 100, 0.1); r += 1

        add_row(r, "k_place_passive_h", "Passivi (h/pezzo)",
                "Effort add passivi.", c.k_place_passive_h, 0, 1, 0.001); r += 1
        add_row(r, "k_place_active_h", "Attivi (h/pezzo)",
                "Effort add attivi.", c.k_place_active_h, 0, 10, 0.01); r += 1
        add_row(r, "k_place_critical_h", "Critici (h/pezzo)",
                "Effort add critici.", c.k_place_critical_h, 0, 50, 0.05); r += 1
        add_row(r, "k_place_connector_h", "Connettori (h/pezzo)",
                "Effort add connettori.", c.k_place_connector_h, 0, 20, 0.05); r += 1

        add_row(r, "k_hdi_multiplier", "Moltiplicatore HDI",
                "Aumenta complessità globale se HDI.", c.k_hdi_multiplier, 1.0, 5.0, 0.05); r += 1

        add_row(r, "k_route_std_base_h", "Routing STD base (h)",
                "Ore base routing non-HS.", c.k_route_std_base_h, 0, 2000, 0.5); r += 1
        add_row(r, "k_route_density_scale_h", "Routing STD densità (h)",
                "Scala routing STD con densità effettiva (max TOP/BOTTOM).", c.k_route_density_scale_h, 0, 2000, 0.5); r += 1

        add_row(r, "k_route_diff_pair_h", "Diff pair (h/coppia)",
                "Ore per coppia diff * severità.", c.k_route_diff_pair_h, 0, 50, 0.05); r += 1
        add_row(r, "k_route_se_h", "SE (h/linea)",
                "Ore per linea SE * severità.", c.k_route_se_h, 0, 50, 0.02); r += 1

        add_row(r, "k_si_base_h", "SI/PI base (h)",
                "Quick SI/PI base.", c.k_si_base_h, 0, 2000, 0.5); r += 1
        add_row(r, "k_si_per_interface_h", "SI per interfaccia (h)",
                "Ore add per interfaccia (scalate col data-rate).", c.k_si_per_interface_h, 0, 200, 0.25); r += 1
        add_row(r, "k_si_rate_multiplier", "SI rate multiplier",
                "Moltiplicatore globale della parte SI legata al data-rate.",
                c.k_si_rate_multiplier, 0.0, 10.0, 0.05); r += 1

        add_row(r, "k_dfm_pct", "DFM % (0.12=12%)",
                "Percentuale di (placement+routing) per DFM/cleanup.", c.k_dfm_pct, 0, 1.0, 0.01); r += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def get_coeffs(self) -> QuoteCoeffs:
        d = {k: float(w.value()) for k, w in self._fields.items()}
        return QuoteCoeffs(**d)


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


class BoardTab(QWidget):
    """
    Layout: sopra dimensioni.
    Sotto: 2 colonne affiancate:
      - sinistra: FORI table + buttons
      - destra: KEEP-OUT table + buttons
    In basso: RIEPILOGO a piena larghezza.
    """
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        # --- Dimensioni (compatte) ---
        dim_form = QFormLayout()
        dim_form.setLabelAlignment(Qt.AlignRight)
        dim_form.setFormAlignment(Qt.AlignTop)
        self.w_mm = QDoubleSpinBox(); self.w_mm.setRange(1, 5000); self.w_mm.setValue(180); self.w_mm.setSuffix(" mm")
        self.h_mm = QDoubleSpinBox(); self.h_mm.setRange(1, 5000); self.h_mm.setValue(140); self.h_mm.setSuffix(" mm")
        dim_form.addRow("PCB Width", self.w_mm)
        dim_form.addRow("PCB Height", self.h_mm)
        outer.addWidget(groupbox("Dimensioni", dim_form))

        # --- Tables row (holes + keepout side-by-side) ---
        row = QHBoxLayout()
        row.setSpacing(12)

        # Holes
        holes_box = QGroupBox("Fori (per tipo)")
        holes_layout = QVBoxLayout(holes_box)
        holes_btn = QHBoxLayout()
        self.hole_add = QPushButton("Aggiungi")
        self.hole_del = QPushButton("Rimuovi")
        holes_btn.addWidget(self.hole_add)
        holes_btn.addWidget(self.hole_del)
        holes_btn.addStretch()

        self.holes_table = QTableWidget(0, 2)
        self.holes_table.setHorizontalHeaderLabels(["Diametro (mm)", "Quantità"])
        _configure_table(self.holes_table, stretch_last=True)
        self.holes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.holes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        holes_layout.addLayout(holes_btn)
        holes_layout.addWidget(self.holes_table)

        # Keepouts
        keep_box = QGroupBox("Keep-out (rettangoli)")
        keep_layout = QVBoxLayout(keep_box)
        keep_btn = QHBoxLayout()
        self.keep_add = QPushButton("Aggiungi")
        self.keep_del = QPushButton("Rimuovi")
        keep_btn.addWidget(self.keep_add)
        keep_btn.addWidget(self.keep_del)
        keep_btn.addStretch()

        self.keep_table = QTableWidget(0, 4)
        self.keep_table.setHorizontalHeaderLabels(["Lato", "W (mm)", "H (mm)", "Qty"])
        _configure_table(self.keep_table, stretch_last=True)
        self.keep_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.keep_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.keep_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.keep_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        keep_layout.addLayout(keep_btn)
        keep_layout.addWidget(self.keep_table)

        row.addWidget(holes_box, 1)
        row.addWidget(keep_box, 2)  # keepout typically needs more width
        outer.addLayout(row)

        # --- Summary full width ---
        summary_box = QGroupBox("Riepilogo Area (calcolato)")
        summary_layout = QVBoxLayout(summary_box)
        self.summary_table = QTableWidget(4, 3)
        self.summary_table.setHorizontalHeaderLabels(["Voce", "TOP", "BOTTOM"])
        self.summary_table.verticalHeader().setVisible(False)
        _configure_table(self.summary_table, stretch_last=True)
        self.summary_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.summary_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.summary_table.setMaximumHeight(170)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        summary_layout.addWidget(self.summary_table)
        outer.addWidget(summary_box)

        outer.addStretch()

        # --- Signals ---
        self.hole_add.clicked.connect(lambda: self.add_hole_row(diameter=3.2, count=1))
        self.hole_del.clicked.connect(self.del_hole_row)
        self.keep_add.clicked.connect(lambda: self.add_keepout_row(side="TOP", w=10, h=10, count=1))
        self.keep_del.clicked.connect(self.del_keepout_row)

        # dynamic updates: debounce to avoid recompute on every keystroke
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self.update_area_summary)

        self.w_mm.valueChanged.connect(self._schedule_update)
        self.h_mm.valueChanged.connect(self._schedule_update)
        self.holes_table.itemChanged.connect(self._schedule_update)
        self.keep_table.itemChanged.connect(self._schedule_update)

        # defaults
        self.add_hole_row(diameter=3.2, count=4)
        self.add_keepout_row(side="TOP", w=20, h=10, count=2)
        self.add_keepout_row(side="BOTTOM", w=15, h=8, count=2)
        self.update_area_summary()

    def _schedule_update(self):
        self._debounce.start()

    def add_hole_row(self, diameter: float = 3.2, count: int = 1):
        r = self.holes_table.rowCount()
        self.holes_table.insertRow(r)
        self.holes_table.setItem(r, 0, _num_item(f"{diameter:.2f}"))
        self.holes_table.setItem(r, 1, _num_item(str(int(count))))

    def del_hole_row(self):
        r = self.holes_table.currentRow()
        if r >= 0:
            self.holes_table.removeRow(r)
            self._schedule_update()

    def add_keepout_row(self, side: str = "TOP", w: float = 10.0, h: float = 10.0, count: int = 1):
        r = self.keep_table.rowCount()
        self.keep_table.insertRow(r)
        self.keep_table.setItem(r, 0, _text_item(side))
        self.keep_table.setItem(r, 1, _num_item(f"{float(w):.2f}"))
        self.keep_table.setItem(r, 2, _num_item(f"{float(h):.2f}"))
        self.keep_table.setItem(r, 3, _num_item(str(int(count))))

    def del_keepout_row(self):
        r = self.keep_table.currentRow()
        if r >= 0:
            self.keep_table.removeRow(r)
            self._schedule_update()

    def collect_holes(self):
        holes = []
        for r in range(self.holes_table.rowCount()):
            d_txt = self.holes_table.item(r, 0).text().strip() if self.holes_table.item(r, 0) else ""
            c_txt = self.holes_table.item(r, 1).text().strip() if self.holes_table.item(r, 1) else ""
            try:
                d = float(d_txt); c = int(float(c_txt))
            except Exception:
                continue
            if d > 0 and c > 0:
                holes.append(HoleType(diameter_mm=d, count=c))
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
        board = BoardConstraints(
            width_mm=float(self.w_mm.value()),
            height_mm=float(self.h_mm.value()),
            holes=self.collect_holes(),
            keepouts=self.collect_keepouts(),
        )

        def set_row(row: int, label: str, top: str, bottom: str):
            self.summary_table.setItem(row, 0, _ro_item(label))
            self.summary_table.setItem(row, 1, _ro_item(top))
            self.summary_table.setItem(row, 2, _ro_item(bottom))

        holes_cm2 = board.holes_area_mm2 / 100.0
        set_row(0, "Area lorda (cm²)", f"{board.gross_cm2:.1f}", f"{board.gross_cm2:.1f}")
        set_row(1, "Area fori (cm²)", f"{holes_cm2:.1f}", f"{holes_cm2:.1f}")
        set_row(2, "Keep-out (cm²)", f"{board.keepout_top_mm2/100.0:.1f}", f"{board.keepout_bottom_mm2/100.0:.1f}")
        set_row(
            3,
            "Utile / occ% / free%",
            f"{board.usable_top_cm2:.1f} / {board.occupied_top_pct:.1f}% / {board.free_top_pct:.1f}%",
            f"{board.usable_bottom_cm2:.1f} / {board.occupied_bottom_pct:.1f}% / {board.free_bottom_pct:.1f}%",
        )
        self.summary_table.resizeRowsToContents()


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
        self.hdi = QCheckBox("HDI"); self.hdi.setChecked(True)
        self.tht = QCheckBox("THT presente"); self.tht.setChecked(False)

        flags = QWidget()
        hb = QHBoxLayout(flags)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.addWidget(self.hdi); hb.addWidget(self.tht); hb.addStretch()

        form.addRow("Numero BGA", self.bga_count)
        form.addRow("Pin BGA totali (effettivi)", self.bga_pins)
        form.addRow("Pitch minimo BGA", self.pitch)
        form.addRow("Layers", self.layers)
        form.addRow("Tecnologia", flags)

        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight)
        form2.setFormAlignment(Qt.AlignTop)
        self.passives = QSpinBox(); self.passives.setRange(0, 500000); self.passives.setValue(800)
        self.actives = QSpinBox(); self.actives.setRange(0, 200000); self.actives.setValue(40)
        self.critical = QSpinBox(); self.critical.setRange(0, 200000); self.critical.setValue(6)
        self.connectors = QSpinBox(); self.connectors.setRange(0, 200000); self.connectors.setValue(12)
        form2.addRow("Passivi (n)", self.passives)
        form2.addRow("Attivi (n)", self.actives)
        form2.addRow("Critici (n)", self.critical)
        form2.addRow("Connettori (n)", self.connectors)

        outer.addWidget(groupbox("BGA / Stack", form))
        outer.addWidget(groupbox("Conteggi componenti", form2))
        outer.addStretch()


class HighSpeedTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.addWidget(_note_label(
            "Ogni riga = una interfaccia (JESD, DDR, Ethernet...).\n"
            "Matching ps: più basso = più complesso. Data-rate per interfaccia."
        ))

        box = QGroupBox("Interfacce High-speed")
        v = QVBoxLayout(box)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nome", "Gbps", "Diff pairs", "SE lines", "Match (ps)"])
        _configure_table(self.table, stretch_last=True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        btn = QHBoxLayout()
        self.add_btn = QPushButton("Aggiungi")
        self.del_btn = QPushButton("Rimuovi")
        btn.addWidget(self.add_btn); btn.addWidget(self.del_btn); btn.addStretch()
        v.addLayout(btn)
        v.addWidget(self.table)
        outer.addWidget(box)
        outer.addStretch()

        self.add_btn.clicked.connect(lambda: self.add_row(("Interface", 10.0, 0, 0, 10.0)))
        self.del_btn.clicked.connect(self.del_row)

        self.add_row(("JESD204", 10.0, 32, 0, 10.0))

    def add_row(self, defaults=("Interface", 10.0, 0, 0, 10.0)):
        r = self.table.rowCount()
        self.table.insertRow(r)
        name, gbps, dp, se, ps = defaults
        self.table.setItem(r, 0, _text_item(str(name)))
        self.table.setItem(r, 1, _num_item(f"{float(gbps):.2f}"))
        self.table.setItem(r, 2, _num_item(str(int(dp))))
        self.table.setItem(r, 3, _num_item(str(int(se))))
        self.table.setItem(r, 4, _num_item(f"{float(ps):.2f}"))

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def collect_interfaces(self):
        itfs = []
        for r in range(self.table.rowCount()):
            def cell(c: int) -> str:
                return self.table.item(r, c).text().strip() if self.table.item(r, c) else ""
            name = cell(0) or f"IF{r+1}"
            try:
                gbps = float(cell(1) or 0.0)
                dp = int(float(cell(2) or 0))
                se = int(float(cell(3) or 0))
                ps = float(cell(4) or 50.0)
            except ValueError:
                continue
            itfs.append(HighSpeedInterface(name=name, data_rate_gbps=gbps, diff_pairs=dp, se_lines=se, match_ps=ps))
        return itfs


class ResultsTab(QWidget):
    """
    Grid layout 2x2 to avoid huge unused space:
      [Board]   [Factors]
      [HS]      [Breakdown]
    Totals below.
    """
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        top_row = QHBoxLayout()
        bot_row = QHBoxLayout()
        top_row.setSpacing(12)
        bot_row.setSpacing(12)

        # Board table
        board_box = QGroupBox("Board / Meccanica")
        vb = QVBoxLayout(board_box)
        self.board_tbl = QTableWidget(0, 2)
        self.board_tbl.setHorizontalHeaderLabels(["Campo", "Valore"])
        _configure_table(self.board_tbl, stretch_last=True)
        self.board_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.board_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        vb.addWidget(self.board_tbl)

        # Factors table
        factors_box = QGroupBox("Fattori")
        vf = QVBoxLayout(factors_box)
        self.factors_tbl = QTableWidget(0, 2)
        self.factors_tbl.setHorizontalHeaderLabels(["Fattore", "Valore"])
        _configure_table(self.factors_tbl, stretch_last=True)
        self.factors_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.factors_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        vf.addWidget(self.factors_tbl)

        top_row.addWidget(board_box, 1)
        top_row.addWidget(factors_box, 1)

        # HS table
        hs_box = QGroupBox("High-speed")
        vh = QVBoxLayout(hs_box)
        self.hs_tbl = QTableWidget(0, 6)
        self.hs_tbl.setHorizontalHeaderLabels(["Interfaccia", "Gbps", "Match(ps)", "DP", "SE", "Hours"])
        _configure_table(self.hs_tbl, stretch_last=True)
        self.hs_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4, 5):
            self.hs_tbl.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        vh.addWidget(self.hs_tbl)

        # Breakdown table
        br_box = QGroupBox("Breakdown (con buffer)")
        vbr = QVBoxLayout(br_box)
        self.break_tbl = QTableWidget(0, 5)
        self.break_tbl.setHorizontalHeaderLabels(["Attività", "Ore", "Weeks", "Rate €/h", "Costo €"])
        _configure_table(self.break_tbl, stretch_last=True)
        self.break_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            self.break_tbl.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        vbr.addWidget(self.break_tbl)

        bot_row.addWidget(hs_box, 1)
        bot_row.addWidget(br_box, 1)

        self.totals_lbl = QLabel("")
        self.totals_lbl.setStyleSheet("font-weight: 700; font-size: 11pt;")

        outer.addLayout(top_row)
        outer.addLayout(bot_row)
        outer.addWidget(self.totals_lbl)

    def _set_kv(self, tbl: QTableWidget, rows: list[tuple[str, str]]):
        tbl.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            tbl.setItem(r, 0, _ro_item(k))
            tbl.setItem(r, 1, _ro_item(v))
        tbl.resizeRowsToContents()

    def set_results(self, res: dict):
        b = res["board"]
        f = res["factors"]
        hs = res["highspeed"]["interfaces"]
        bd = res["breakdown"]

        self._set_kv(self.board_tbl, [
            ("Area lorda (cm²)", f"{b['gross_cm2']:.1f}"),
            ("Area fori (cm²)", f"{b['holes_area_cm2']:.1f}"),
            ("Keep-out TOP (cm²)", f"{b['keepout_top_cm2']:.1f}"),
            ("Keep-out BOTTOM (cm²)", f"{b['keepout_bottom_cm2']:.1f}"),
            ("Area utile TOP (cm²)", f"{b['usable_top_cm2']:.1f}"),
            ("Area utile BOTTOM (cm²)", f"{b['usable_bottom_cm2']:.1f}"),
            ("TOP occ/free (%)", f"{b['occupied_top_pct']:.1f} / {b['free_top_pct']:.1f}"),
            ("BOTTOM occ/free (%)", f"{b['occupied_bottom_pct']:.1f} / {b['free_bottom_pct']:.1f}"),
        ])

        self._set_kv(self.factors_tbl, [
            ("Density TOP pin/(cm²*layer)", f"{f['density_top_pin_per_cm2_layer']:.3f}"),
            ("Density BOTTOM pin/(cm²*layer)", f"{f['density_bottom_pin_per_cm2_layer']:.3f}"),
            ("Density effective (max)", f"{f['density_effective']:.3f}"),
            ("f_pitch", f"{f['f_pitch']:.2f}"),
            ("f_density", f"{f['f_density']:.2f}"),
            ("f_hdi", f"{f['f_hdi']:.2f}"),
        ])

        self.hs_tbl.setRowCount(len(hs))
        for r, it in enumerate(hs):
            self.hs_tbl.setItem(r, 0, _ro_item(it["name"]))
            self.hs_tbl.setItem(r, 1, _ro_item(f"{it['data_rate_gbps']:.2f}"))
            self.hs_tbl.setItem(r, 2, _ro_item(f"{it['match_ps']:.2f}"))
            self.hs_tbl.setItem(r, 3, _ro_item(str(int(it["diff_pairs"]))))
            self.hs_tbl.setItem(r, 4, _ro_item(str(int(it["se_lines"]))))
            self.hs_tbl.setItem(r, 5, _ro_item(f"{it['hours_total']:.1f}"))
        self.hs_tbl.resizeRowsToContents()

        hours = bd["hours_with_buffer"]
        weeks = bd["weeks_with_buffer"]
        costs = bd["costs_with_buffer"]
        rates = bd["rates"]

        order = ["Placement", "Routing HS", "Routing STD", "SI/PI", "DFM/Cleanup"]
        self.break_tbl.setRowCount(len(order))
        for r, k in enumerate(order):
            rate = rates["si_pi"] if k == "SI/PI" else rates["layout"]
            self.break_tbl.setItem(r, 0, _ro_item(k))
            self.break_tbl.setItem(r, 1, _ro_item(f"{hours[k]:.1f}"))
            self.break_tbl.setItem(r, 2, _ro_item(f"{weeks[k]:.2f}"))
            self.break_tbl.setItem(r, 3, _ro_item(f"{rate:.0f}"))
            self.break_tbl.setItem(r, 4, _ro_item(f"{costs[k]:.0f}"))
        self.break_tbl.resizeRowsToContents()

        t = bd["totals"]
        self.totals_lbl.setText(f"TOTAL: {t['hours']:.1f} h  |  {t['weeks']:.2f} weeks  |  €{t['cost']:.0f}")


class QuoteForm(QWidget):
    refreshRequested = Signal()
    saveRequested = Signal()
    loadRequested = Signal()
    editCoeffsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        vbox = QVBoxLayout(self)
        self.coeffs: QuoteCoeffs = DEFAULT_COEFFS

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
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.coeffs_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.refresh_btn)
        vbox.addLayout(btn_row)

        self.refresh_btn.clicked.connect(self.refreshRequested.emit)
        self.save_btn.clicked.connect(self.saveRequested.emit)
        self.load_btn.clicked.connect(self.loadRequested.emit)
        self.coeffs_btn.clicked.connect(self.editCoeffsRequested.emit)

    def open_coeffs_dialog(self):
        dlg = CoeffsDialog(self.coeffs, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.coeffs = dlg.get_coeffs()

    def collect_inputs(self) -> LayoutQuoteInputs:
        tariffs = Tariffs(
            layout_eur_per_h=float(self.general.tar_layout.value()),
            si_pi_eur_per_h=float(self.general.tar_si.value()),
        )
        board = BoardConstraints(
            width_mm=float(self.board.w_mm.value()),
            height_mm=float(self.board.h_mm.value()),
            holes=self.board.collect_holes(),
            keepouts=self.board.collect_keepouts(),
        )
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

        return LayoutQuoteInputs(
            board=board,
            components=comps,
            highspeed=hs,
            buffer_pct=float(self.general.buffer.value()),
            week_hours=float(self.general.week_hours.value()),
            tariffs=tariffs,
        )

    def load_inputs(self, inp: LayoutQuoteInputs):
        self.general.tar_layout.setValue(float(inp.tariffs.layout_eur_per_h))
        self.general.tar_si.setValue(float(inp.tariffs.si_pi_eur_per_h))
        self.general.buffer.setValue(float(inp.buffer_pct))
        self.general.week_hours.setValue(float(inp.week_hours))

        self.board.w_mm.setValue(float(inp.board.width_mm))
        self.board.h_mm.setValue(float(inp.board.height_mm))

        self.board.holes_table.setRowCount(0)
        for h in inp.board.holes:
            self.board.add_hole_row(h.diameter_mm, h.count)

        self.board.keep_table.setRowCount(0)
        for k in inp.board.keepouts:
            self.board.add_keepout_row(k.side, k.width_mm, k.height_mm, k.count)

        self.board.update_area_summary()

        self.components.bga_count.setValue(int(inp.components.bga_count))
        self.components.bga_pins.setValue(int(inp.components.bga_total_pins_effective))
        self.components.pitch.setValue(float(inp.components.min_bga_pitch_mm))
        self.components.layers.setValue(int(inp.components.layers))
        self.components.hdi.setChecked(bool(inp.components.hdi))
        self.components.tht.setChecked(bool(inp.components.tht))
        self.components.passives.setValue(int(inp.components.passives))
        self.components.actives.setValue(int(inp.components.actives))
        self.components.critical.setValue(int(inp.components.critical))
        self.components.connectors.setValue(int(inp.components.connectors))

        self.hs.table.setRowCount(0)
        for it in inp.highspeed.interfaces:
            self.hs.add_row((it.name, it.data_rate_gbps, it.diff_pairs, it.se_lines, it.match_ps))

    def recalc(self):
        self.board.update_area_summary()
        inp = self.collect_inputs()
        res = estimate_layout_quote(inp, coeffs=self.coeffs)
        self.results.set_results(res)