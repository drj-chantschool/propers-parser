"""
Render all_subsections.json as a table-of-contents text file for visual validation.

Indentation = (level - min_level) spaces, one space per level.
Each line also shows pdf_page / printed_page for cross-checking.

Usage:
  python validate_toc.py [path/to/all_subsections.json]
  (defaults to graduale/1/all_subsections.json)

Output: tmp_validate_allsubsections_toc.txt (delete when done validating)
"""

import sys
import json
from pathlib import Path

BASE = Path(__file__).parent
DEFAULT_IN = BASE / "graduale" / "1" / "all_subsections.json"
OUT_PATH = BASE / "tmp_validate_allsubsections_toc.txt"


def page_info(entry):
    pdf_page = entry.get("pdf_page")
    printed_page = entry.get("printed_page")
    pdf_str = str(pdf_page) if pdf_page is not None else "-"
    printed_str = str(printed_page) if printed_page is not None else "-"
    return f"pdf {pdf_str}  p.{printed_str}"


def main():
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    entries = json.loads(in_path.read_text(encoding="utf-8"))

    min_level = min(e["level"] for e in entries)

    lines = []
    for entry in entries:
        indent = " " * (entry["level"] - min_level)
        text = f"{indent}{entry.get('text', '')}"
        lines.append(f"{text:<60} {page_info(entry)}")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {OUT_PATH}")


if __name__ == "__main__":
    main()
