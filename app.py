#!/usr/bin/env python3
"""File Converter - simple desktop app. Pick files, pick format, convert."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from converter import convert, valid_targets, category_of, ALL_KNOWN

BG = "#1a1d24"
PANEL = "#242832"
FG = "#e8eaf0"
MUTED = "#8b93a7"
ACCENT = "#2e7cf6"
GOOD = "#17b26a"


class App:
    def __init__(self, root):
        self.root = root
        root.title("File Converter")
        root.geometry("620x560")
        root.configure(bg=BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG,
                        font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("TCombobox", fieldbackground=PANEL,
                        background=PANEL, foreground=FG)
        style.configure("Horizontal.TProgressbar", background=ACCENT)

        top = ttk.Frame(root)
        top.pack(fill="x", padx=20, pady=(15, 5))
        ttk.Label(top, text="File Converter",
                  font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(top, text="runs 100% locally",
                  foreground=MUTED).pack(side="left", padx=(10, 0))

        # file list
        list_frame = ttk.Frame(root)
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)
        self.listbox = tk.Listbox(list_frame, bg=PANEL, fg=FG,
                                  font=("Segoe UI", 9), height=10,
                                  relief="flat", selectmode="extended")
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(list_frame, command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        btn_row = ttk.Frame(root)
        btn_row.pack(fill="x", padx=20, pady=5)
        ttk.Button(btn_row, text="Add files",
                   command=self.add_files).pack(side="left")
        ttk.Button(btn_row, text="Remove selected",
                   command=self.remove_selected).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Clear",
                   command=self.clear).pack(side="left", padx=(8, 0))

        # format picker
        fmt_row = ttk.Frame(root)
        fmt_row.pack(fill="x", padx=20, pady=5)
        ttk.Label(fmt_row, text="Convert to:").pack(side="left")
        self.fmt_var = tk.StringVar()
        self.fmt_box = ttk.Combobox(fmt_row, textvariable=self.fmt_var,
                                    state="readonly", width=12)
        self.fmt_box.pack(side="left", padx=(8, 0))
        self.fmt_box.bind("<<ComboboxSelected>>", lambda e: None)
        ttk.Label(fmt_row, text="",
                  textvariable=self._hint_var(),
                  foreground=MUTED).pack(side="left", padx=(10, 0))

        # output folder
        out_row = ttk.Frame(root)
        out_row.pack(fill="x", padx=20, pady=5)
        ttk.Label(out_row, text="Save to:").pack(side="left")
        self.out_var = tk.StringVar(value="(same folder as input)")
        ttk.Label(out_row, textvariable=self.out_var,
                  foreground=MUTED).pack(side="left", padx=(8, 0))
        ttk.Button(out_row, text="Choose...",
                   command=self.choose_out).pack(side="right")

        # progress + status
        self.progress = ttk.Progressbar(root, mode="determinate",
                                        style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=20, pady=(8, 0))
        self.status = tk.StringVar(value="Add some files to get started")
        ttk.Label(root, textvariable=self.status,
                  foreground=MUTED).pack(anchor="w", padx=20, pady=5)

        ttk.Button(root, text="Convert",
                   command=self.start).pack(pady=8)

        self.files = []
        self.out_dir = None
        self.working = False
        self.listbox.bind("<<ListboxSelect>>", self._refresh_formats)

    def _hint_var(self):
        if not hasattr(self, "_hint"):
            self._hint = tk.StringVar(value="")
        return self._hint

    # -- file management -------------------------------------------------
    def add_files(self):
        paths = filedialog.askopenfilenames(title="Select files")
        for p in paths:
            if p not in self.files:
                ext = os.path.splitext(p)[1].lower().lstrip(".")
                if ext in ALL_KNOWN:
                    self.files.append(p)
                    self.listbox.insert("end", os.path.basename(p))
                else:
                    messagebox.showwarning(
                        "Skipped",
                        f"Don't know how to convert .{ext} yet:\n"
                        f"{os.path.basename(p)}")
        self._refresh_formats()

    def remove_selected(self):
        for i in sorted(self.listbox.curselection(), reverse=True):
            self.listbox.delete(i)
            del self.files[i]
        self._refresh_formats()

    def clear(self):
        self.listbox.delete(0, "end")
        self.files = []
        self._refresh_formats()

    def choose_out(self):
        d = filedialog.askdirectory(title="Output folder")
        if d:
            self.out_dir = d
            self.out_var.set(d)

    def _refresh_formats(self, _=None):
        sel = self.listbox.curselection()
        idx = sel[0] if sel else (0 if self.files else None)
        if idx is None:
            self.fmt_box["values"] = []
            self.fmt_var.set("")
            self._hint.set("")
            return
        ext = os.path.splitext(self.files[idx])[1]
        targets = valid_targets(ext)
        cat = category_of(ext) or "file"
        self.fmt_box["values"] = targets
        if targets and self.fmt_var.get() not in targets:
            # smart default: mp4->mp3 is the classic
            default = "mp3" if "mp3" in targets else targets[0]
            self.fmt_var.set(default)
        self._hint.set(f"{os.path.basename(self.files[idx])} "
                       f"({cat}, .{ext.lstrip('.')})")

    # -- conversion ------------------------------------------------------
    def start(self):
        if self.working or not self.files:
            return
        if not self.fmt_var.get():
            messagebox.showwarning("No format", "Pick an output format first.")
            return
        self.working = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        total = len(self.files)
        target = self.fmt_var.get()
        ok, fail = 0, 0
        for i, src in enumerate(list(self.files)):
            name = os.path.basename(src)
            self._status(f"[{i+1}/{total}] Converting {name} -> {target}...")
            try:
                # sanity: target must make sense for this file
                ext = os.path.splitext(src)[1]
                if target not in valid_targets(ext):
                    raise ValueError(
                        f".{target} isn't a valid target for this file type")
                out = convert(src, target, self.out_dir)
                if isinstance(out, list):
                    self._mark(i, f"[OK] {name} -> {len(out)} files")
                else:
                    self._mark(i, f"[OK] {name} -> {os.path.basename(out)}")
                ok += 1
            except Exception as e:
                self._mark(i, f"[FAIL] {name}: {e}")
                fail += 1
            self._progress((i + 1) / total * 100)
        self._status(f"Done: {ok} converted, {fail} failed")
        self._progress(100)
        self.working = False

    # -- thread-safe UI --------------------------------------------------
    def _status(self, t):
        self.root.after(0, self.status.set, t)

    def _progress(self, v):
        self.root.after(0, self.progress.configure, {"value": v})

    def _mark(self, idx, text):
        def _do():
            self.listbox.delete(idx)
            self.listbox.insert(idx, text)
        self.root.after(0, _do)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
