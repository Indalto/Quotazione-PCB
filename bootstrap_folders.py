from pathlib import Path

ROOT = Path("pcb_quote_project")

DIRS = [
    ROOT / "pcb_quote",
    ROOT / "pcb_quote" / "gui",
]

FILES = [
    ROOT / "run.py",
    ROOT / "requirements.txt",
    ROOT / "make_structure.py",
    ROOT / "pcb_quote" / "__init__.py",
    ROOT / "pcb_quote" / "models.py",
    ROOT / "pcb_quote" / "calculations.py",
    ROOT / "pcb_quote" / "io_utils.py",
    ROOT / "pcb_quote" / "gui" / "__init__.py",
    ROOT / "pcb_quote" / "gui" / "app.py",
    ROOT / "pcb_quote" / "gui" / "main_window.py",
    ROOT / "pcb_quote" / "gui" / "forms.py",
    ROOT / "pcb_quote" / "gui" / "styles.py",
]

def main():
    for d in DIRS:
        d.mkdir(parents=True, exist_ok=True)

    # solo placeholder vuoti, così poi incolli tu i contenuti
    for f in FILES:
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text("", encoding="utf-8")

    print("Struttura creata in:", ROOT.resolve())

if __name__ == "__main__":
    main()