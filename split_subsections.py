"""
Phase 3: Split each section PDF into subsection PDFs.

Reads a subsections.json file (produced by detect_subsections.py + manual
review) and splits the section PDF at page boundaries.

Entry format in subsections.json:
  {"page": N, "y": Y, "text": "HEADING"}          # leaf → flat PDF file
  {"page": N, "y": Y, "text": ["GROUP NAME",       # group → subdirectory
    {"page": N1, "y": Y1, "text": "CHILD"},         #   first element = group name (string)
    {"page": N2, "y": Y2, "text": "CHILD"},         #   remaining = child entries (recursive)
    ...
  ]}

Groups produce:
  {n}_{slug}/
    meta.json
    0_{slug}.pdf          — full page range of the group
    1_{slug}.pdf, ...     — individual children (or further subdirs if nested)

The y-position of each heading is recorded for Phase 4 (widow/orphan trim);
this script splits at whole-page boundaries only.

Usage:
  python split_subsections.py <section_dir>
  python split_subsections.py graduale/1/1_tempus-adventus
"""

import sys
import re
import json
import fitz
from pathlib import Path

BASE = Path(__file__).parent


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def save_pdf(doc: fitz.Document, start: int, end: int, out_path: Path) -> None:
    """Save pages [start, end) (0-indexed) from doc to out_path."""
    out = fitz.open()
    out.insert_pdf(doc, from_page=start, to_page=end - 1)
    out.set_pagelayout("SinglePage")
    out.save(str(out_path))
    out.close()


def write_meta(path: Path, meta: dict) -> None:
    path.write_text(json.dumps(meta, indent=2))


def process_entries(doc, entries, out_dir, group_end, chapter_page_offset,
                    parent_pdf_name, indent=2):
    """
    Recursively split entries into PDFs under out_dir.

    doc                  — fitz.Document (always the original section PDF)
    entries              — list of entry dicts for this level
    out_dir              — directory to write output into
    group_end            — 0-indexed exclusive end page for the last entry
    chapter_page_offset  — 1-indexed page in the chapter PDF where out_dir starts
    parent_pdf_name      — name of the parent PDF (for meta records)
    """
    # Y threshold: if the next heading's y is below this the new section starts
    # at the very top of the page and the current section has no widow there.
    # Above this threshold the current section has content on the next page too.
    Y_TOP_THRESHOLD = 60

    pad = " " * indent

    for idx, entry in enumerate(entries):
        start = entry["page"] - 1          # 0-indexed in section PDF
        if idx + 1 < len(entries):
            next_e = entries[idx + 1]
            next_page = next_e["page"] - 1  # 0-indexed
            next_y = next_e.get("y") or 0
            # Include the next entry's page if its heading is mid-page (widow)
            end = next_page if next_y < Y_TOP_THRESHOLD else next_page + 1
        else:
            end = group_end
        num = idx + 1
        text = entry["text"]

        if isinstance(text, str):
            # ── Leaf: save as a flat numbered PDF ──────────────────────────
            slug = slugify(text)
            out_path = out_dir / f"{num}_{slug}.pdf"
            save_pdf(doc, start, end, out_path)

            chap_p = chapter_page_offset + start
            page_in_parent = start - (entries[0]["page"] - 1) + 1
            meta = {
                "heading": text,
                "heading_y": entry.get("y"),
                "source_pdf": parent_pdf_name,
                "page_offset": page_in_parent,
                "chapter_page_offset": chap_p,
            }
            write_meta(out_path.with_suffix(".meta.json"), meta)
            print(f"{pad}{num}. {text:<45} p{start+1}–{end}  chap_p={chap_p}  y={entry.get('y', '?'):.0f}")

        else:
            # ── Group: text is a list; first element is the group name ──────
            group_name = text[0]
            children = text[1:]
            slug = slugify(group_name)
            sub_dir = out_dir / f"{num}_{slug}"
            sub_dir.mkdir(exist_ok=True)

            # Save full group range as 0_*.pdf
            group_pdf = sub_dir / f"0_{slug}.pdf"
            save_pdf(doc, start, end, group_pdf)

            chap_p = chapter_page_offset + start
            group_meta = {
                "title": group_name,
                "source_pdf": parent_pdf_name,
                "page_offset": start - (entries[0]["page"] - 1) + 1,
                "chapter_page_offset": chap_p,
            }
            write_meta(sub_dir / "meta.json", group_meta)
            print(f"{pad}{num}. [{group_name}]  p{start+1}–{end}  chap_p={chap_p}")

            if children:
                process_entries(
                    doc, children, sub_dir,
                    group_end=end,
                    chapter_page_offset=chapter_page_offset,
                    parent_pdf_name=group_pdf.name,
                    indent=indent + 5,
                )


def split(section_dir: Path) -> None:
    subsections_json = section_dir / "subsections.json"
    if not subsections_json.exists():
        print(f"ERROR: {subsections_json} not found")
        sys.exit(1)

    entries = json.loads(subsections_json.read_text())

    def normalise(entry):
        """Support legacy 'heading' field name → rename to 'text'."""
        if "text" not in entry and "heading" in entry:
            entry["text"] = entry["heading"]
        return entry

    entries = [normalise(e) for e in entries]

    def unflatten(flat, parent_level=0):
        """Convert flat entries with 'level' fields into nested structure.

        Entries at parent_level become nodes; consecutive entries at
        parent_level+1 (or deeper) are collected as children of the
        preceding parent_level node and recursed into.

        A node with children becomes a group:
          {"page": ..., "text": ["GROUP NAME", child1, child2, ...]}
        A node with no children stays a leaf:
          {"page": ..., "text": "LEAF NAME"}
        """
        result = []
        i = 0
        while i < len(flat):
            e = flat[i]
            lvl = e.get("level", 0)
            if lvl != parent_level:
                # Deeper entry encountered without a parent — treat as leaf at this level
                result.append(e)
                i += 1
                continue
            # Collect any immediately following deeper entries as children
            children_raw = []
            i += 1
            while i < len(flat) and flat[i].get("level", 0) > parent_level:
                children_raw.append(flat[i])
                i += 1
            if not children_raw:
                result.append(e)
            else:
                result.append({
                    "page": e["page"],
                    "y":    e.get("y"),
                    "text": [e["text"]] + unflatten(children_raw, parent_level + 1),
                })
        return result

    entries = unflatten(entries)

    # Load section meta for offset chain
    section_meta_path = section_dir / "meta.json"
    section_page_offset = 1
    source_pdf_name = None
    if section_meta_path.exists():
        section_meta = json.loads(section_meta_path.read_text())
        section_page_offset = section_meta.get("page_offset", 1)
        source_pdf_name = section_meta.get("source_pdf")

    # Find the section PDF (0_*.pdf)
    candidates = sorted(section_dir.glob("0_*.pdf"))
    if not candidates:
        print(f"ERROR: no 0_*.pdf found in {section_dir}")
        sys.exit(1)
    section_pdf = candidates[0]

    doc = fitz.open(str(section_pdf))
    n = len(doc)
    print(f"Splitting {section_pdf.name} ({n} pages)")
    if source_pdf_name:
        print(f"  Section starts at page {section_page_offset} of {source_pdf_name}")

    process_entries(
        doc, entries, section_dir,
        group_end=n,
        chapter_page_offset=section_page_offset,
        parent_pdf_name=section_pdf.name,
        indent=2,
    )

    doc.close()


if __name__ == "__main__":
    section_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not section_dir or not section_dir.is_dir():
        print(f"Usage: python {Path(__file__).name} <section_dir>")
        sys.exit(1)
    split(section_dir)
