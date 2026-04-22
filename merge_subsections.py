"""
Merge all subsections.json files for GR chapter 1 into a single flat JSON,
computing the absolute page number in graduale romanum.pdf for each entry.

Offset chain:
  graduale_page = chapter_offset + section_offset + entry_page - 2
  (all offsets are 1-indexed; the -2 corrects for double-counting the base)

Also backs up each subsections.json → subsections.json.bak before writing
the merged output.

Output: graduale/1/all_subsections.json
"""

import json
import shutil
from pathlib import Path

BASE = Path(__file__).parent
CHAP_DIR = BASE / "graduale" / "1"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def backup(path):
    bak = path.with_suffix(".json.bak")
    shutil.copy2(path, bak)
    return bak


def collect(entries, section_title, section_num,
            chapter_offset, section_offset, results):
    """Flatten entries (already in level-based flat format) into results."""
    for entry in entries:
        text = entry.get("text") or entry.get("heading", "")
        # Skip entries where text is a list (shouldn't occur in flat JSONs,
        # but guard against old path-array format)
        if isinstance(text, list):
            text = " / ".join(str(t) for t in text)

        page = entry.get("page")
        graduale_page = None
        if page is not None:
            graduale_page = chapter_offset + section_offset + page - 2

        results.append({
            "section_num":    section_num,
            "section":        section_title,
            "level":          entry.get("level", 0),
            "text":           text,
            "page_in_section": page,
            "section_offset": section_offset,
            "chapter_offset": chapter_offset,
            "graduale_page":  graduale_page,
            "y":              entry.get("y"),
        })


def main():
    chap_meta = load_json(CHAP_DIR / "meta.json")
    chapter_offset = chap_meta["page_offset"]   # 1-indexed page in graduale romanum.pdf
    print(f"Chapter offset in graduale romanum.pdf: {chapter_offset}")

    results = []
    backed_up = []

    for section_dir in sorted(CHAP_DIR.iterdir()):
        if not section_dir.is_dir():
            continue

        subsections_json = section_dir / "subsections.json"
        if not subsections_json.exists():
            print(f"  SKIP {section_dir.name} — no subsections.json")
            continue

        section_meta_path = section_dir / "meta.json"
        if not section_meta_path.exists():
            print(f"  SKIP {section_dir.name} — no meta.json")
            continue

        section_meta = load_json(section_meta_path)
        section_offset = section_meta["page_offset"]
        section_title  = section_meta.get("title", section_dir.name)
        section_num    = int(section_dir.name.split("_")[0])

        entries = load_json(subsections_json)
        collect(entries, section_title, section_num,
                chapter_offset, section_offset, results)

        bak = backup(subsections_json)
        backed_up.append(bak)
        print(f"  {section_dir.name}: {len(entries)} entries  "
              f"(offset={section_offset}, backed up to {bak.name})")

    out_path = CHAP_DIR / "all_subsections.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nWrote {len(results)} total entries to {out_path}")
    print(f"Backed up {len(backed_up)} subsections.json files")


if __name__ == "__main__":
    main()
