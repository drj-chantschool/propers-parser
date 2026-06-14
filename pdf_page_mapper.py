#!/usr/bin/env python3
"""
PDF Page Mapper

Maps PDF page indices (1-based) to printed book page numbers using a
divide-and-conquer strategy to minimize manual lookups.

Usage:
    python pdf_page_mapper.py [pdf_path] [offsets_file] [mapping_file]
"""

import sys
import json
import os
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from io import BytesIO
from collections import deque
from pathlib import Path


BASE = Path(__file__).parent

PDF_PATH     = str(BASE / "graduale" / "graduale romanum.pdf")
OFFSETS_FILE = str(BASE / "graduale" / "page_offsets.json")
MAPPING_FILE = str(BASE / "graduale" / "page_mapping.json")


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_offsets(path):
    if os.path.exists(path):
        with open(path) as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}


def save_offsets(path, offsets):
    with open(path, "w") as f:
        json.dump({str(k): v for k, v in offsets.items()}, f, indent=2)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_page(doc, page_idx, max_w, max_h):
    page = doc[page_idx]
    rect = page.rect
    scale = min(max_w / rect.width, max_h / rect.height, 1.8)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return Image.open(BytesIO(pix.tobytes("ppm")))


def render_bottom_strip(doc, page_idx, strip_fraction=0.18, zoom=3.0):
    """Return a zoomed image of the bottom strip of the page."""
    page = doc[page_idx]
    rect = page.rect
    strip_h = rect.height * strip_fraction
    clip = fitz.Rect(rect.x0, rect.y1 - strip_h, rect.x1, rect.y1)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
    return Image.open(BytesIO(pix.tobytes("ppm")))


# ---------------------------------------------------------------------------
# Divide-and-conquer mapper
# ---------------------------------------------------------------------------

class PageMapper:
    """
    Maintains the divide-and-conquer queue and the offset table.

    offsets[i]  (0-indexed pdf page i):
        int  — offset = real_page_number − (i + 1)
        None — page has no printed number
        absent — not yet visited
    """

    def __init__(self, pdf_path, offsets_file, mapping_file):
        self.doc = fitz.open(pdf_path)
        self.n = len(self.doc)
        self.offsets_file = offsets_file
        self.mapping_file = mapping_file
        self.offsets = load_offsets(offsets_file)
        self.queue = deque([(0, self.n - 1)])

    # -- public API ---------------------------------------------------------

    def next_needed(self):
        """
        Drive the queue as far as possible without new user input.

        Returns (page_idx, segments_remaining) — the next page the user must
        inspect, or (None, 0) when the mapping is complete.

        For each segment [lo, hi]:
          lo_eff: walk RIGHT from lo — ask about every unvisited page until
                  we find a numbered one (lo_src).
          hi_eff: walk LEFT from hi down to lo_src+1 — ask about every
                  unvisited page until we find a numbered one (hi_src).
        This prevents both sides from collapsing to the same source page.
        """
        while self.queue:
            lo, hi = self.queue[0]

            # --- single-page segment ---
            if lo == hi:
                if lo not in self.offsets:
                    return lo, len(self.queue)
                self.queue.popleft()
                continue

            # --- lo_eff: walk right from lo, pausing at unvisited pages ---
            lo_eff = lo_src = None
            for p in range(lo, hi + 1):
                if p not in self.offsets:
                    return p, len(self.queue)      # ask user
                if self.offsets[p] is not None:
                    lo_eff, lo_src = self.offsets[p], p
                    break

            if lo_eff is None:
                # Whole segment is no-number; nothing to do
                self.queue.popleft()
                continue

            # --- hi_eff: walk left from hi down to lo_src+1, pausing at unvisited pages ---
            hi_eff = hi_src = None
            for p in range(hi, lo_src, -1):
                if p not in self.offsets:
                    return p, len(self.queue)      # ask user
                if self.offsets[p] is not None:
                    hi_eff, hi_src = self.offsets[p], p
                    break

            if hi_eff is None:
                # No numbered page between lo_src+1 and hi; offset is uniform
                for p in range(lo, hi + 1):
                    if p not in self.offsets:
                        self.offsets[p] = lo_eff
                self.queue.popleft()
                continue

            # --- compare and decide ---
            if lo_eff == hi_eff or hi - lo <= 1:
                for p in range(lo, hi + 1):
                    if p not in self.offsets:
                        self.offsets[p] = lo_eff
                self.queue.popleft()
            else:
                mid = (lo + hi) // 2
                self.queue.popleft()
                self.queue.appendleft((mid, hi))
                self.queue.appendleft((lo, mid))

        return None, 0

    def record(self, page_idx, real_number):
        """
        Store user input for a page.
        real_number — int printed page number, or None if no number on page.
        """
        if real_number is None:
            self.offsets[page_idx] = None
        else:
            self.offsets[page_idx] = real_number - (page_idx + 1)
        save_offsets(self.offsets_file, self.offsets)

    def build_final_mapping(self):
        """
        Produce and persist {pdf_page_1indexed: real_page_number} for all pages.
        No-number pages inherit the offset of their nearest numbered neighbour.
        """
        known = {p: off for p, off in self.offsets.items() if off is not None}

        result = {}
        for p in range(self.n):
            if p in known:
                result[p + 1] = (p + 1) + known[p]
            elif known:
                nearest = min(known, key=lambda x: abs(x - p))
                result[p + 1] = (p + 1) + known[nearest]
            else:
                result[p + 1] = p + 1

        with open(self.mapping_file, "w") as f:
            json.dump(
                {"keys": "pdf_page_number_one_based",
                 "values": "printed_page_number",
                 "mapping": {str(k): v for k, v in result.items()}}
                , f, indent=2)
        return result


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

PAGE_W  = 660   # canvas width for full page
PAGE_H  = 860   # canvas height for full page
STRIP_W = 660   # canvas width for bottom-strip zoom
STRIP_H = 130   # canvas height for bottom-strip zoom


class App:
    def __init__(self, mapper: PageMapper):
        self.mapper = mapper
        self.current_page = None
        self._photo_page  = None
        self._photo_strip = None

        self.root = tk.Tk()
        self.root.title("PDF Page Mapper — Graduale Romanum")
        self._build_ui()

    # -- layout -------------------------------------------------------------

    def _build_ui(self):
        root = self.root

        # Left column: page image + strip zoom
        left = tk.Frame(root, bg="black")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_page = tk.Canvas(left, width=PAGE_W, height=PAGE_H, bg="#333", highlightthickness=0)
        self.canvas_page.pack()

        tk.Label(left, text="Bottom strip (zoomed)", bg="#222", fg="#aaa",
                 font=("Helvetica", 9)).pack(fill=tk.X)

        self.canvas_strip = tk.Canvas(left, width=STRIP_W, height=STRIP_H, bg="#111", highlightthickness=0)
        self.canvas_strip.pack()

        # Right column: controls
        right = tk.Frame(root, padx=14, pady=14, bg="#f0f0f0")
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self.lbl_page = tk.Label(right, text="PDF page: —",
                                  font=("Helvetica", 15, "bold"), bg="#f0f0f0")
        self.lbl_page.pack(anchor="w")

        self.lbl_segments = tk.Label(right, text="Segments left: —",
                                      font=("Helvetica", 11), bg="#f0f0f0", fg="#555")
        self.lbl_segments.pack(anchor="w", pady=(2, 16))

        tk.Label(right, text="Printed page number:", font=("Helvetica", 11),
                 bg="#f0f0f0").pack(anchor="w")

        self.entry = tk.Entry(right, font=("Helvetica", 16), width=10)
        self.entry.pack(anchor="w", pady=6)
        self.entry.bind("<Return>", lambda e: self._submit_number())

        self.btn_submit = tk.Button(
            right, text="Submit  [Enter]", font=("Helvetica", 11),
            bg="#2e7de0", fg="white", activebackground="#1a5db5",
            padx=8, pady=6, relief=tk.FLAT,
            command=self._submit_number,
        )
        self.btn_submit.pack(fill=tk.X, pady=4)

        self.btn_none = tk.Button(
            right, text="No page number  [N]", font=("Helvetica", 11),
            bg="#777", fg="white", activebackground="#555",
            padx=8, pady=6, relief=tk.FLAT,
            command=self._submit_none,
        )
        self.btn_none.pack(fill=tk.X, pady=4)

        tk.Frame(right, height=1, bg="#ccc").pack(fill=tk.X, pady=14)

        self.lbl_known = tk.Label(right, text="Pages visited: 0",
                                   font=("Helvetica", 10), bg="#f0f0f0", fg="#888")
        self.lbl_known.pack(anchor="w")

        self.lbl_total = tk.Label(right,
                                   text=f"Total PDF pages: {self.mapper.n}",
                                   font=("Helvetica", 10), bg="#f0f0f0", fg="#888")
        self.lbl_total.pack(anchor="w")

        tk.Frame(right, height=1, bg="#ccc").pack(fill=tk.X, pady=14)

        tk.Label(right, text="Keyboard shortcuts:", font=("Helvetica", 9, "bold"),
                 bg="#f0f0f0", fg="#666").pack(anchor="w")
        tk.Label(right, text="Enter — submit number\nN — no page number",
                 font=("Helvetica", 9), bg="#f0f0f0", fg="#888", justify=tk.LEFT).pack(anchor="w")

        root.bind("n", lambda e: self._submit_none())
        root.bind("N", lambda e: self._submit_none())

    # -- rendering ----------------------------------------------------------

    def _show_page(self, page_idx):
        self.current_page = page_idx
        self.lbl_page.config(text=f"PDF page: {page_idx + 1}")

        # Full page
        img = render_page(self.mapper.doc, page_idx, PAGE_W, PAGE_H)
        # Centre in canvas
        x = PAGE_W // 2
        y = PAGE_H // 2
        self._photo_page = ImageTk.PhotoImage(img)
        self.canvas_page.delete("all")
        self.canvas_page.create_image(x, y, anchor=tk.CENTER, image=self._photo_page)

        # Bottom strip zoom
        try:
            strip = render_bottom_strip(self.mapper.doc, page_idx)
            # Fit to strip canvas width
            ratio = STRIP_W / strip.width
            sh = max(1, int(strip.height * ratio))
            strip = strip.resize((STRIP_W, sh), Image.LANCZOS)
            self._photo_strip = ImageTk.PhotoImage(strip)
            self.canvas_strip.config(height=min(sh, 200))
            self.canvas_strip.delete("all")
            self.canvas_strip.create_image(0, 0, anchor=tk.NW, image=self._photo_strip)
        except Exception:
            pass

        self.entry.delete(0, tk.END)
        self.entry.focus_set()

    # -- state updates ------------------------------------------------------

    def _update_labels(self, n_segs):
        self.lbl_segments.config(text=f"Segments left: {n_segs}")
        visited = len(self.mapper.offsets)
        self.lbl_known.config(text=f"Pages visited: {visited}")

    def _advance(self):
        page_idx, n_segs = self.mapper.next_needed()
        self._update_labels(n_segs)
        if page_idx is not None:
            self._show_page(page_idx)
        else:
            self._finish()

    # -- user input handlers ------------------------------------------------

    def _submit_number(self):
        txt = self.entry.get().strip()
        try:
            n = int(txt)
        except ValueError:
            self.entry.config(bg="#ffcccc")
            self.root.after(400, lambda: self.entry.config(bg="white"))
            return
        self.mapper.record(self.current_page, n)
        self._advance()

    def _submit_none(self):
        if self.current_page is None:
            return
        self.mapper.record(self.current_page, None)
        self._advance()

    def _finish(self):
        mapping = self.mapper.build_final_mapping()
        messagebox.showinfo(
            "Complete!",
            f"All {len(mapping)} pages mapped.\nSaved to:\n{self.mapper.mapping_file}",
        )
        self.root.quit()

    # -- entry point --------------------------------------------------------

    def run(self):
        self._advance()
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pdf_path     = sys.argv[1] if len(sys.argv) > 1 else PDF_PATH
    offsets_file = sys.argv[2] if len(sys.argv) > 2 else OFFSETS_FILE
    mapping_file = sys.argv[3] if len(sys.argv) > 3 else MAPPING_FILE

    mapper = PageMapper(pdf_path, offsets_file, mapping_file)
    App(mapper).run()
