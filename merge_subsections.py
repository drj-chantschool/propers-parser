"""
Merge subsection headings for GR chapter 1 into a single flat JSON.

Output: graduale/1/all_subsections.json

Entry levels:
  -2  chapter  (from graduale/1/meta.json)
  -1  section  (from graduale/1/<n>_*/meta.json)
   0  sub-heading, first level  (from subsections.json)
   1  sub-heading, second level (from subsections.json)

Each entry: level, text, pdf_page, printed_page, y
  (plus section_num and section on level >= 0 entries)

pdf_page is a 1-indexed page number in graduale romanum.pdf.
printed_page is the page number printed on the physical page
  (looked up via graduale/page_mapping.json), or null if pdf_page
  is unset or maps to a page with no printed number.
"""

import json
import shutil
from pathlib import Path

BASE = Path(__file__).parent
CHAP_DIR = BASE / "graduale" / "1"
OUT_PATH = CHAP_DIR / "all_subsections.json"
PAGE_MAPPING_PATH = BASE / "graduale" / "page_mapping.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def backup(path):
    bak = path.with_suffix(".json.bak")
    shutil.copy2(path, bak)
    return bak


def main():
    page_mapping = load_json(PAGE_MAPPING_PATH)["mapping"]

    def printed_page_for(pdf_page):
        if pdf_page is None:
            return None
        printed = page_mapping.get(str(pdf_page))
        return printed if printed else None

    chap_meta = load_json(CHAP_DIR / "meta.json")
    chapter_pdf_page = chap_meta["page_offset"]
    chapter_title = chap_meta.get("title", CHAP_DIR.name)
    print(f"Chapter: {chapter_title}  pdf_page={chapter_pdf_page}")

    results = []
    backed_up = []

    # Chapter entry
    results.append({
        "level":        -2,
        "text":         chapter_title,
        "pdf_page":     chapter_pdf_page,
        "printed_page": printed_page_for(chapter_pdf_page),
        "y":            0,
    })

    for section_dir in sorted(CHAP_DIR.iterdir()):
        if not section_dir.is_dir():
            continue

        section_meta_path = section_dir / "meta.json"
        if not section_meta_path.exists():
            print(f"  SKIP {section_dir.name} — no meta.json")
            continue

        try:
            section_num = int(section_dir.name.split("_")[0])
        except ValueError:
            continue

        section_meta = load_json(section_meta_path)
        section_offset = section_meta["page_offset"]
        section_title = section_meta.get("title", section_dir.name)
        section_pdf_page = chapter_pdf_page + section_offset - 1

        # Section entry
        results.append({
            "section_num":  section_num,
            "level":        -1,
            "text":         section_title,
            "pdf_page":     section_pdf_page,
            "printed_page": printed_page_for(section_pdf_page),
            "y":            0,
        })

        subsections_json = section_dir / "subsections.json"
        if not subsections_json.exists():
            if (section_dir / "subsections_raw.json").exists():
                print(f"  WARNING {section_dir.name}: subsections_raw.json not yet reviewed")
            else:
                print(f"  {section_dir.name}: no sub-headings (offset={section_offset})")
            continue

        entries = load_json(subsections_json)
        current_subsection = None
        for entry in entries:
            text = entry.get("text") or entry.get("heading", "")
            if isinstance(text, list):
                text = " / ".join(str(t) for t in text)
            level = entry.get("level", 0)
            if level == 0:
                current_subsection = text
            page = entry.get("page")
            pdf_page = None
            if page is not None:
                pdf_page = chapter_pdf_page + section_offset + page - 2
            row = {
                "section_num":  section_num,
                "section":      section_title,
                "level":        level,
                "text":         text,
                "pdf_page":     pdf_page,
                "printed_page": printed_page_for(pdf_page),
                "y":            entry.get("y"),
            }
            if level >= 1 and current_subsection is not None:
                row["subsection"] = current_subsection
            results.append(row)

        bak = backup(subsections_json)
        backed_up.append(bak)
        print(f"  {section_dir.name}: {len(entries)} sub-headings "
              f"(offset={section_offset})")

    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nWrote {len(results)} total entries to {OUT_PATH}")
    if backed_up:
        print(f"Backed up {len(backed_up)} subsections.json files")


if __name__ == "__main__":
    main()
