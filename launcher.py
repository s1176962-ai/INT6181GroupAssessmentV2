"""Validate the local runtime before opening the desktop application."""

import sys
from pathlib import Path


def main():
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or later is required.")
    import tkinter as tk

    from learning_platform.gui import Application

    root = tk.Tk()
    root.withdraw()
    folder = Path(__file__).resolve().parent
    if not (folder / "data/questions").is_dir():
        raise RuntimeError("Missing data/questions. Extract the complete project folder.")
    Application(root, project_root=folder)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Startup failed:", exc)
        sys.exit(1)
