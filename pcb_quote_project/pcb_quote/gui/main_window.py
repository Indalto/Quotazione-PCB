from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QStatusBar, QLabel

from pcb_quote.gui.forms import QuoteForm
from pcb_quote import io_utils


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCB Layout Quote Estimator")

        self.form = QuoteForm(parent=self)
        self.setCentralWidget(self.form)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_msg = QLabel("Pronto")
        self.status.addWidget(self.status_msg)

        self.form.refreshRequested.connect(self.on_refresh)
        self.form.saveRequested.connect(self.on_save)
        self.form.loadRequested.connect(self.on_load)
        self.form.editCoeffsRequested.connect(self.on_edit_coeffs)

        self.on_refresh()

    def on_refresh(self):
        try:
            self.form.recalc()
            self.status_msg.setText("Riepilogo aggiornato")
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))
            self.status_msg.setText("Errore")

    def on_edit_coeffs(self):
        try:
            self.form.open_coeffs_dialog()
            self.on_refresh()
            self.status_msg.setText("Coefficienti aggiornati")
        except Exception as e:
            QMessageBox.critical(self, "Errore coefficienti", str(e))
            self.status_msg.setText("Errore")

    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salva progetto", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            inp = self.form.collect_inputs()
            payload = io_utils.inputs_to_dict(inp, self.form.coeffs)
            io_utils.save_json(path, payload)
            self.status_msg.setText("Progetto salvato")
        except Exception as e:
            QMessageBox.critical(self, "Errore salvataggio", str(e))
            self.status_msg.setText("Errore")

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica progetto", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            d = io_utils.load_json(path)
            inp, coeffs = io_utils.dict_to_inputs(d)
            self.form.coeffs = coeffs

            # ora esiste sempre (fixato in forms.py)
            self.form.load_inputs(inp)

            self.on_refresh()
            self.status_msg.setText("Progetto caricato")
        except Exception as e:
            QMessageBox.critical(self, "Errore caricamento", str(e))
            self.status_msg.setText("Errore")