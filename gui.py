#!/usr/bin/env python3
"""FolderKnowledgeSiteGeneratorForAI — GUI entry point."""

import os
import sys
import pathlib
import tkinter as tk

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from src.ui.app import App


def main():
    drag_enabled = False
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        drag_enabled = True
    except ImportError:
        root = tk.Tk()
        # Print warning so user knows drag-and-drop is unavailable
        print("\n[WARN] tkinterdnd2 not installed — drag-and-drop disabled.")
        print("       To enable: pip install tkinterdnd2")
        print("       You can still Browse or Paste folders manually.\n")
    app = App(root)
    if len(sys.argv) > 1:
        f = sys.argv[1]
        if os.path.isdir(f):
            root.after(100, lambda: app.load_folder(f))
    root.mainloop()


if __name__ == "__main__":
    main()