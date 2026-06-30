"""A small local Tkinter GUI: pick report files, choose an output folder, Process.

Tkinter ships with the standard Python installers on Windows and macOS. On
Linux, install it via your package manager (e.g. `sudo apt install python3-tk`).
"""

from __future__ import annotations

import os
import threading
from typing import List

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import load_config
from .pipeline import process_file


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Cerner TAT Scraper")
        root.geometry("720x520")
        root.minsize(640, 460)

        self.files: List[str] = []
        self.output_dir = tk.StringVar(value=os.path.abspath("output"))
        self.config_path = tk.StringVar(value="")

        self._build()

    # --- UI construction ---------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Cerner TAT Scraper", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            top,
            text="Reads Cerner HTML/PDF reports and writes a TAT spreadsheet. "
            "Runs entirely on this computer.",
            foreground="#555",
        ).pack(anchor="w")

        # file list
        files_frame = ttk.LabelFrame(self.root, text="Report files")
        files_frame.pack(fill="both", expand=True, **pad)

        self.listbox = tk.Listbox(files_frame, selectmode=tk.EXTENDED)
        self.listbox.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.listbox.yview)
        sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        btns = ttk.Frame(files_frame)
        btns.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Button(btns, text="Add files…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Clear", command=self.clear_files).pack(fill="x", pady=2)

        # output folder
        out_frame = ttk.Frame(self.root)
        out_frame.pack(fill="x", **pad)
        ttk.Label(out_frame, text="Output folder:").pack(side="left")
        ttk.Entry(out_frame, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(out_frame, text="Browse…", command=self.choose_output).pack(side="left")

        # optional config
        cfg_frame = ttk.Frame(self.root)
        cfg_frame.pack(fill="x", **pad)
        ttk.Label(cfg_frame, text="Config (optional):").pack(side="left")
        ttk.Entry(cfg_frame, textvariable=self.config_path).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(cfg_frame, text="Browse…", command=self.choose_config).pack(side="left")

        # process + log
        action = ttk.Frame(self.root)
        action.pack(fill="x", **pad)
        self.process_btn = ttk.Button(action, text="Process", command=self.process)
        self.process_btn.pack(side="left")
        self.progress = ttk.Progressbar(action, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=6, pady=6)

    # --- actions -----------------------------------------------------------
    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Cerner report files",
            filetypes=[
                ("Reports", "*.html *.htm *.pdf"),
                ("HTML", "*.html *.htm"),
                ("PDF", "*.pdf"),
                ("All files", "*.*"),
            ],
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert(tk.END, p)

    def remove_selected(self) -> None:
        for idx in reversed(self.listbox.curselection()):
            self.listbox.delete(idx)
            del self.files[idx]

    def clear_files(self) -> None:
        self.listbox.delete(0, tk.END)
        self.files.clear()

    def choose_output(self) -> None:
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.output_dir.set(d)

    def choose_config(self) -> None:
        f = filedialog.askopenfilename(
            title="Choose config.yaml", filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")]
        )
        if f:
            self.config_path.set(f)

    def _log(self, msg: str) -> None:
        self.log.config(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def process(self) -> None:
        if not self.files:
            messagebox.showinfo("No files", "Add at least one report file first.")
            return
        self.process_btn.config(state="disabled")
        self.progress.start(12)
        thread = threading.Thread(target=self._process_worker, daemon=True)
        thread.start()

    def _process_worker(self) -> None:
        try:
            cfg_path = self.config_path.get().strip() or None
            config = load_config(cfg_path)
            out_dir = self.output_dir.get().strip() or "output"
            ok, fail = 0, 0
            for path in list(self.files):
                self.root.after(0, self._log, f"Processing {os.path.basename(path)}…")
                result = process_file(path, out_dir, config)
                if result.error:
                    fail += 1
                    self.root.after(0, self._log, f"   ERROR: {result.error}")
                else:
                    ok += 1
                    self.root.after(
                        0,
                        self._log,
                        f"   {result.record_count} tests → {result.output_path}",
                    )
            self.root.after(0, self._log, f"Done. {ok} succeeded, {fail} failed.")
        except Exception as exc:  # noqa: BLE001 — show any unexpected error
            self.root.after(0, self._log, f"Unexpected error: {exc}")
        finally:
            self.root.after(0, self._finish)

    def _finish(self) -> None:
        self.progress.stop()
        self.process_btn.config(state="normal")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
