"""review_gr_index.py: Two-phase interactive review workflow for the GR index.

Usage:
  python review_gr_index.py --generate   # detect entries, save bbox images + JSON state
  python review_gr_index.py --review     # interactive tkinter review GUI
"""

import re
import csv
import io
import json
import sys
import argparse
from pathlib import Path

import fitz
import pytesseract
from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
from tkinter import messagebox

from ocr_gr_index import (
    parse_line, match_section,
    INDEX_PDF, IMAGE_PAGES, FITZ_PAGES, STOP_SECTIONS,
    _IS_MODE, _EXT_TRANS,
)

# Section headers not in ocr_gr_index (sub-headings found in the index)
_EXTRA_HEADERS = {
    "sequenti": "sequentia",
    "responsa":   "responsorium",
}

def match_section_extended(line: str) -> str | None:
    result = match_section(line)
    if result:
        return result
    t = re.sub(r"[^\x00-\x7f]", "", line.strip().lower()).strip()
    t = re.sub(r"^[|.\s]+", "", t)
    return next((v for k, v in _EXTRA_HEADERS.items() if t.startswith(k)), None)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

BBOX_DIR     = Path(__file__).parent / "bbox_review"
ENTRIES_JSON = Path(__file__).parent / "gr_index_entries.json"
REVIEWED_CSV = Path(__file__).parent / "gr_chant_index_reviewed.csv"

CROP_PAD = 10    # pixels of padding above/below each bbox crop
MIN_CONF      = 20    # minimum Tesseract word confidence to include


# ---------------------------------------------------------------------------
# --generate
# ---------------------------------------------------------------------------

def get_line_bboxes(col_img: Image.Image) -> list[dict]:
    """Run image_to_data on a column image; return one dict per detected line."""
    data = pytesseract.image_to_data(
        col_img, lang="lat", config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )
    lines: dict = {}
    n = len(data["text"])
    for i in range(n):
        if data["level"][i] != 5:   # word level only
            continue
        word = data["text"][i].strip()
        if not word:
            continue
        if int(data["conf"][i]) < MIN_CONF:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        l = data["left"][i]
        t = data["top"][i]
        r = l + data["width"][i]
        b = t + data["height"][i]
        if key not in lines:
            lines[key] = {"words": [word], "left": l, "top": t, "right": r, "bottom": b}
        else:
            lines[key]["left"]   = min(lines[key]["left"], l)
            lines[key]["top"]    = min(lines[key]["top"], t)
            lines[key]["right"]  = max(lines[key]["right"], r)
            lines[key]["bottom"] = max(lines[key]["bottom"], b)
            lines[key]["words"].append(word)

    return [
        {
            "text":   " ".join(v["words"]),
            "left":   v["left"],
            "top":    v["top"],
            "right":  v["right"],
            "bottom": v["bottom"],
        }
        for k, v in sorted(lines.items())
    ]


def generate():
    BBOX_DIR.mkdir(exist_ok=True)
    doc = fitz.open(str(INDEX_PDF))

    entries      = []
    entry_id     = 0
    current_sec  = None
    done         = False

    for pg_idx in list(IMAGE_PAGES) + list(FITZ_PAGES):
        if done:
            break

        mat = fitz.Matrix(3, 3)
        pix = doc[pg_idx].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        page_img = Image.open(io.BytesIO(pix.tobytes("png")))
        page_img.save(BBOX_DIR / f"page_{pg_idx:02d}.png")

        w, h = page_img.size
        top  = int(h * 0.05)
        rule = w // 2

        col_regions = [
            ("left",  0,        top, rule - 8, h),
            ("right", rule + 8, top, w,        h),
        ]

        annot = page_img.convert("RGB")
        draw  = ImageDraw.Draw(annot)

        for col_name, cx0, cy0, cx1, cy1 in col_regions:
            if done:
                break
            col_img    = page_img.crop((cx0, cy0, cx1, cy1))
            line_boxes = get_line_bboxes(col_img)

            for lb in line_boxes:
                ocr_text = lb["text"]
                if not ocr_text.strip():
                    continue

                # Full-page coordinates
                fl = cx0 + lb["left"]
                ft = cy0 + lb["top"]
                fr = cx0 + lb["right"]
                fb = cy0 + lb["bottom"]

                sec = match_section_extended(ocr_text)
                entry_type = "entry"
                if sec:
                    if sec in STOP_SECTIONS:
                        done = True
                        break
                    current_sec = sec
                    entry_type  = "section_header"

                parsed_result = None
                if current_sec and entry_type == "entry":
                    p = parse_line(ocr_text)
                    if p:
                        mode, inc, pages = p
                        parsed_result = {"mode": mode, "incipit": inc, "pages": pages}

                # section headers are auto-approved; everything else is pending
                status = "auto" if entry_type == "section_header" else "pending"

                entries.append({
                    "id":           entry_id,
                    "page_idx":     pg_idx,
                    "column":       col_name,
                    "bbox":         [fl, ft, fr, fb],
                    "ocr_text":     ocr_text,
                    "section_type": current_sec,
                    "type":         entry_type,
                    "parsed":       parsed_result,
                    "status":       status,
                    "final_text":   None,
                })
                entry_id += 1

                # Draw bbox: green = parsed, yellow = unparsed entry, blue = header
                if entry_type == "section_header":
                    color = (80, 80, 220)
                elif parsed_result:
                    color = (0, 200, 0)
                else:
                    color = (220, 180, 0)
                draw.rectangle([fl, ft, fr, fb], outline=color, width=2)

        annot.save(BBOX_DIR / f"annotated_page_{pg_idx:02d}.png")
        pg_count = sum(1 for e in entries if e["page_idx"] == pg_idx)
        print(f"  Page {pg_idx}: {pg_count} lines")

    doc.close()

    with open(ENTRIES_JSON, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, ensure_ascii=False, indent=2)

    pending = sum(1 for e in entries if e["status"] == "pending")
    print(f"\n{len(entries)} total lines  ({pending} pending review)")
    print(f"State  → {ENTRIES_JSON}")
    print(f"Images → {BBOX_DIR}/")
    print()
    print("Bbox colors:  green = parsed chant entry")
    print("              yellow = unparsed / ambiguous")
    print("              blue = section header (auto-approved)")


# ---------------------------------------------------------------------------
# --review
# ---------------------------------------------------------------------------

class ReviewApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GR Index Review")
        self.root.resizable(True, True)

        with open(ENTRIES_JSON, encoding="utf-8") as f:
            data = json.load(f)
        self.entries = data["entries"]

        self._page_cache: dict[int, Image.Image] = {}
        self._photo = None          # keep reference so GC doesn't kill it
        self._warn_eid = None       # id of entry that got a parse warning
        self._extra_eids: list[int] = []   # additional entries folded into current via two-liner
        self._current_crop: Image.Image | None = None  # raw crop for window-resize re-render

        self.pending_ids = [e["id"] for e in self.entries if e["status"] == "pending"]
        self.cursor = 0             # index into self.pending_ids

        if not self.pending_ids:
            self._write_csv()
            messagebox.showinfo("Done", f"All entries reviewed!\nCSV → {REVIEWED_CSV}")
            root.destroy()
            return

        self._build_ui()
        self._load_entry(0)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Status line
        self.status_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.status_var,
            font=("Helvetica", 10), anchor="w", padx=8, pady=4,
        ).pack(fill="x")

        # Entry image
        self.img_label = tk.Label(self.root, bg="#f0f0f0", relief="sunken",
                                  width=70, height=6)
        self.img_label.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.img_label.bind("<Configure>", self._on_img_resize)

        # Raw OCR text
        self.ocr_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.ocr_var,
            font=("Courier", 10), fg="#555", anchor="w",
            padx=8, wraplength=700, justify="left",
        ).pack(fill="x")

        # Parse status / warning
        self.info_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.info_var,
            font=("Helvetica", 9), fg="#333", anchor="w", padx=8,
        ).pack(fill="x")

        # Edit field
        ef = tk.Frame(self.root)
        ef.pack(fill="x", padx=8, pady=6)
        tk.Label(ef, text="Text:", font=("Helvetica", 10)).pack(side="left")
        self.text_var = tk.StringVar()
        self.entry_widget = tk.Entry(
            ef, textvariable=self.text_var,
            font=("Courier", 11), width=65,
        )
        self.entry_widget.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Buttons
        bf = tk.Frame(self.root)
        bf.pack(fill="x", padx=8, pady=(0, 10))
        tk.Button(bf, text="Accept  [Enter]",   command=self.accept,    width=16).pack(side="left", padx=3)
        tk.Button(bf, text="Two-liner  [t]",    command=self.two_liner, width=15).pack(side="left", padx=3)
        tk.Button(bf, text="Skip  [s]",         command=self.skip,      width=10).pack(side="left", padx=3)
        tk.Button(bf, text="Discard  [d]",      command=self.discard,   width=12).pack(side="left", padx=3)
        tk.Button(bf, text="Quit  [q]",         command=self.quit_,     width=10).pack(side="left", padx=3)

        self.root.bind("<Return>", lambda _: self.accept())
        self.root.bind("t",        lambda e: None if self._editing() else self.two_liner())
        self.root.bind("s",        lambda e: None if self._editing() else self.skip())
        self.root.bind("d",        lambda e: None if self._editing() else self.discard())
        self.root.bind("q",        lambda e: None if self._editing() else self.quit_())
        self.root.bind("e",        lambda e: None if self._editing() else self._enter_edit())
        self.root.focus_set()

    # ------------------------------------------------------------------ nav

    def _load_entry(self, cursor: int):
        if cursor >= len(self.pending_ids):
            self._finish()
            return

        self.cursor    = cursor
        self._extra_eids = []
        self._warn_eid = None

        eid   = self.pending_ids[cursor]
        entry = self.entries[eid]

        total     = len(self.pending_ids)
        remaining = total - cursor
        sec       = entry.get("section_type") or "?"
        col       = entry.get("column", "")
        pg        = entry.get("page_idx", 0)
        self.status_var.set(
            f"Entry {cursor + 1} / {total}  ·  Page {pg}  {col}  ·  [{sec}]  ·  {remaining} remaining"
        )

        self.root.focus_set()
        self._refresh_display()

    def _refresh_display(self):
        """Re-render image and labels for the current entry + any extra two-liner entries."""
        eid   = self.pending_ids[self.cursor]
        entry = self.entries[eid]
        all_eids = [eid] + self._extra_eids

        # OCR text (all lines joined)
        ocr_parts = [self.entries[e].get("ocr_text", "") for e in all_eids]
        self.ocr_var.set("OCR:  " + "  /  ".join(ocr_parts))

        # Parse info — try the combined text first, fall back to primary
        combined_ocr = " ".join(ocr_parts)
        p = parse_line(combined_ocr) or entry.get("parsed")
        if p and isinstance(p, tuple):
            mode, inc, pages = p
            p = {"mode": mode, "incipit": inc, "pages": pages}
        if p and isinstance(p, dict):
            pages_str = ", ".join(p.get("pages", []))
            self.info_var.set(
                f"Parsed:  mode={p.get('mode')}   page={pages_str}   incipit={p.get('incipit')}"
            )
            prefill = f"{p['mode']} {p['incipit']} {','.join(p['pages'])}".strip()
        else:
            suffix = "  [two-liner]" if self._extra_eids else ""
            self.info_var.set(f"Parsed:  (none — edit or skip){suffix}")
            prefill = combined_ocr

        self.text_var.set(prefill)

        # Image: union bbox across all participating entries (assumes same page)
        try:
            pg = entry["page_idx"]
            page_img = self._get_page_img(pg)
            pw, ph   = page_img.size
            all_bboxes = [self.entries[e]["bbox"] for e in all_eids]
            x0 = max(0,  min(b[0] for b in all_bboxes) - CROP_PAD)
            y0 = max(0,  min(b[1] for b in all_bboxes) - CROP_PAD)
            x1 = min(pw, max(b[2] for b in all_bboxes) + CROP_PAD)
            y1 = min(ph, max(b[3] for b in all_bboxes) + CROP_PAD)
            self._current_crop = page_img.crop((x0, y0, x1, y1))
            self._render_crop()
        except Exception as exc:
            self._current_crop = None
            self.img_label.config(image="", text=f"(image error: {exc})")

    def _get_page_img(self, pg_idx: int) -> Image.Image:
        if pg_idx not in self._page_cache:
            self._page_cache[pg_idx] = Image.open(
                BBOX_DIR / f"page_{pg_idx:02d}.png"
            ).convert("RGB")
        return self._page_cache[pg_idx]

    def _editing(self) -> bool:
        return self.root.focus_get() is self.entry_widget

    def _enter_edit(self):
        self.entry_widget.focus_set()
        self.entry_widget.select_range(0, "end")

    def _render_crop(self):
        """Scale self._current_crop to fit the label width, preserving aspect ratio."""
        if self._current_crop is None:
            return
        available_w = self.img_label.winfo_width()
        if available_w < 10:
            available_w = 800   # not yet laid out; use a sensible default
        crop = self._current_crop
        scale = available_w / crop.width
        nw = available_w
        nh = max(int(crop.height * scale), 20)
        disp = crop.resize((nw, nh), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(disp)
        self.img_label.config(image=self._photo, text="")

    def _on_img_resize(self, event):
        if self._current_crop is not None:
            self._render_crop()

    # ------------------------------------------------------------------ actions

    def two_liner(self):
        """Toggle: expand image to include the next sequential entry, or collapse."""
        if self._extra_eids:
            # Already expanded — collapse back
            self._extra_eids = []
            self._refresh_display()
            return

        eid      = self.pending_ids[self.cursor]
        next_eid = eid + 1
        if next_eid >= len(self.entries):
            self.info_var.set("No next entry to combine.")
            return
        self._extra_eids = [next_eid]
        self._refresh_display()

    def accept(self):
        if self.cursor >= len(self.pending_ids):
            return
        eid   = self.pending_ids[self.cursor]
        entry = self.entries[eid]
        text  = self.text_var.get().strip()

        p = parse_line(text)
        if not p:
            if self._warn_eid != eid:
                # First attempt: warn and let user edit
                self._warn_eid = eid
                self.info_var.set(
                    "⚠ Text doesn't parse as a chant entry (needs: <mode> <incipit> <page>). "
                    "Edit the text or press Accept again to force-save as raw, or Skip."
                )
                return
            # Second attempt: force-save as raw text with no CSV row
            entry["status"]     = "saved_raw"
            entry["final_text"] = text
        else:
            original = entry.get("ocr_text", "").strip()
            entry["status"]     = "corrected" if text != original else "approved"
            entry["final_text"] = text

        # Mark any two-liner extras as consumed so they don't appear in future sessions
        for extra_eid in self._extra_eids:
            self.entries[extra_eid]["status"] = "merged"

        self._save_json()
        self._load_entry(self.cursor + 1)

    def skip(self):
        """Defer to next session — entry stays pending."""
        if self.cursor >= len(self.pending_ids):
            return
        self._load_entry(self.cursor + 1)

    def discard(self):
        """Permanently skip — entry will not appear again."""
        if self.cursor >= len(self.pending_ids):
            return
        eid = self.pending_ids[self.cursor]
        self.entries[eid]["status"] = "skipped"
        self._save_json()
        self._load_entry(self.cursor + 1)

    def quit_(self):
        self._save_json()
        done      = self.cursor
        remaining = len(self.pending_ids) - done
        self._write_csv()
        messagebox.showinfo(
            "Saved",
            f"Reviewed {done} entries this session.\n"
            f"{remaining} still pending.\n"
            f"CSV written → {REVIEWED_CSV}",
        )
        self.root.destroy()

    def _finish(self):
        self._save_json()
        self._write_csv()
        messagebox.showinfo("Complete", f"All entries reviewed!\nCSV → {REVIEWED_CSV}")
        self.root.destroy()

    # ------------------------------------------------------------------ I/O

    def _save_json(self):
        with open(ENTRIES_JSON, "w", encoding="utf-8") as f:
            json.dump({"entries": self.entries}, f, ensure_ascii=False, indent=2)

    def _write_csv(self):
        rows = []
        for entry in self.entries:
            if entry["status"] not in ("approved", "corrected"):
                continue
            text = entry.get("final_text") or ""
            p    = parse_line(text)
            if not p:
                continue
            mode, inc, pages = p
            sec = entry.get("section_type") or ""
            for pg in pages:
                rows.append({"chant_type": sec, "mode": mode, "incipit": inc, "page": pg})
        with open(REVIEWED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["chant_type", "mode", "incipit", "page"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV written: {len(rows)} entries → {REVIEWED_CSV}")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def review():
    if not ENTRIES_JSON.exists():
        print(f"Error: {ENTRIES_JSON} not found. Run --generate first.")
        sys.exit(1)
    root = tk.Tk()
    root.geometry("820x520")
    ReviewApp(root)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="GR Index OCR review workflow")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--generate", action="store_true",
                     help="Detect entries and generate bbox images")
    grp.add_argument("--review",   action="store_true",
                     help="Interactive review GUI")
    args = ap.parse_args()

    if args.generate:
        generate()
    else:
        review()


if __name__ == "__main__":
    main()
