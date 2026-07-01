"""A small local Tkinter GUI for the Cerner TAT Scraper.

Two ways to feed it a report:
  * "Report files" tab — pick one or more .html / .pdf / .txt files.
  * "Paste text" tab   — paste the report text copied out of Cerner (the most
                          reliable option when the PDFs are scanned images).

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
from .pipeline import process_file, process_text


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Cerner TAT Scraper")
        root.geometry("760x600")
        root.minsize(680, 540)

        self.files: List[str] = []
        self.output_dir = tk.StringVar(value=os.path.abspath("output"))
        self.config_path = tk.StringVar(value="")
        self.paste_name = tk.StringVar(value="pasted_report")
        self.master_path = tk.StringVar(value="")

        self._build()

    # --- UI construction ---------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Cerner TAT Scraper", font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            top,
            text="Reads Cerner HTML/PDF reports or pasted report text and writes a "
            "TAT spreadsheet. Runs entirely on this computer.",
            foreground="#555",
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, **pad)
        self._build_files_tab()
        self._build_paste_tab()

        # output folder
        out_frame = ttk.Frame(self.root)
        out_frame.pack(fill="x", **pad)
        ttk.Label(out_frame, text="Output folder:").pack(side="left")
        ttk.Entry(out_frame, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(out_frame, text="Browse…", command=self.choose_output).pack(side="left")

        # optional running master workbook
        master_frame = ttk.Frame(self.root)
        master_frame.pack(fill="x", **pad)
        ttk.Label(master_frame, text="Master file (optional):").pack(side="left")
        ttk.Entry(master_frame, textvariable=self.master_path).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(master_frame, text="Browse…", command=self.choose_master).pack(side="left")

        # optional config
        cfg_frame = ttk.Frame(self.root)
        cfg_frame.pack(fill="x", **pad)
        ttk.Label(cfg_frame, text="Config (optional):").pack(side="left")
        ttk.Entry(cfg_frame, textvariable=self.config_path).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(cfg_frame, text="Browse…", command=self.choose_config).pack(side="left")

        # process + progress
        action = ttk.Frame(self.root)
        action.pack(fill="x", **pad)
        self.process_btn = ttk.Button(action, text="Process", command=self.process)
        self.process_btn.pack(side="left")
        self.progress = ttk.Progressbar(action, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, height=7, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_files_tab(self) -> None:
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Report files")

        self.listbox = tk.Listbox(tab, selectmode=tk.EXTENDED)
        self.listbox.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.listbox.yview)
        sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        btns = ttk.Frame(tab)
        btns.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Button(btns, text="Add files…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Clear", command=self.clear_files).pack(fill="x", pady=2)

    def _build_paste_tab(self) -> None:
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Paste text")

        ttk.Label(
            tab,
            text="Paste the report text copied from Cerner below, then click Process.",
            foreground="#555",
        ).pack(anchor="w", padx=6, pady=(6, 0))

        name_row = ttk.Frame(tab)
        name_row.pack(fill="x", padx=6, pady=4)
        ttk.Label(name_row, text="Output name:").pack(side="left")
        ttk.Entry(name_row, textvariable=self.paste_name, width=30).pack(side="left", padx=6)
        ttk.Button(name_row, text="Clear", command=lambda: self.paste_box.delete("1.0", tk.END)).pack(side="right")

        self.paste_box = tk.Text(tab, wrap="none", height=12)
        self.paste_box.pack(fill="both", expand=True, padx=6, pady=6)

    # --- file actions ------------------------------------------------------
    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Cerner report files",
            filetypes=[
                ("Reports", "*.html *.htm *.pdf *.txt"),
                ("HTML", "*.html *.htm"),
                ("PDF", "*.pdf"),
                ("Text", "*.txt"),
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

    def choose_master(self) -> None:
        f = filedialog.asksaveasfilename(
            title="Choose or create a master workbook",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("All", "*.*")],
            confirmoverwrite=False,
        )
        if f:
            self.master_path.set(f)

    def _log(self, msg: str) -> None:
        self.log.config(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    # --- processing --------------------------------------------------------
    def process(self) -> None:
        active = self.tabs.index(self.tabs.select())
        if active == 0:  # files tab
            if not self.files:
                messagebox.showinfo("No files", "Add at least one report file first.")
                return
            payload = ("files", list(self.files))
        else:  # paste tab
            text = self.paste_box.get("1.0", tk.END).strip()
            if not text:
                messagebox.showinfo("No text", "Paste some report text first.")
                return
            payload = ("text", text)

        self.process_btn.config(state="disabled")
        self.progress.start(12)
        threading.Thread(target=self._worker, args=(payload,), daemon=True).start()

    def _worker(self, payload) -> None:
        try:
            cfg_path = self.config_path.get().strip() or None
            config = load_config(cfg_path)
            out_dir = self.output_dir.get().strip() or "output"
            master = self.master_path.get().strip() or None
            kind, data = payload

            if kind == "files":
                ok, fail = 0, 0
                for path in data:
                    self.root.after(0, self._log, f"Processing {os.path.basename(path)}…")
                    result = process_file(path, out_dir, config, master_path=master)
                    if result.error:
                        fail += 1
                        self.root.after(0, self._log, f"   ERROR: {result.error}")
                    else:
                        ok += 1
                        self.root.after(
                            0, self._log,
                            f"   {result.record_count} tests → {result.output_path}",
                        )
                self.root.after(0, self._log, f"Done. {ok} succeeded, {fail} failed.")
            else:
                name = self.paste_name.get().strip() or "pasted_report"
                self.root.after(0, self._log, "Processing pasted text…")
                result = process_text(data, out_dir, name, config, master_path=master)
                if result.error:
                    self.root.after(0, self._log, f"   ERROR: {result.error}")
                else:
                    self.root.after(
                        0, self._log,
                        f"   {result.record_count} tests → {result.output_path}",
                    )
        except Exception as exc:  # noqa: BLE001
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
