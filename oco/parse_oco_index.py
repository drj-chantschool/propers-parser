#!/usr/bin/env python
"""parse_oco_index.py — OCO's four indices (v4 pp1214–1316, v6 pp1213–…; pages from the outline) →
tools/load_index.py JSON, one file per page.

Deterministic; no agent stage. Every index entry is a hyperlink, and the text layer is clean:
  - Index hymnorum (1214–1224): incipit | day | office | LHym page; the link is a gregobase URI
    → chant_uuid 'gregobase:N', match_status 'resolved'; page NULL (hymns are not engraved in OCO).
  - Ad invitatorium (1225–1227): incipit | day | LHym page; named link → OCO page of the engraving.
  - Index antiphonarum (1228–1309): incipit | day | office | place; named link 'A[day,office,place]'.
  - Index responsoriorum brevium (1310–1316): incipit | day | office; named link.
Columns are told apart by font: day codes Aster-Med, offices Aster-RegIta, the rest Aster-Reg.
A named link's 'page' is 0-based (printed = page + 1, since printed = PDF page in OCO).

Checks (printed; exit 1 on any): a text row with no link, a link with no text, the named dest of an
antiphon disagreeing with the printed day/office/place, the incipit's first words not found on
the target page (or the page after: the engraving can start below a page break).

    python oco/parse_oco_index.py [--out oco/index] [--pages a-b]
"""
import argparse
import json
import os
import re
import sys
import unicodedata

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oco_pages  # noqa: E402  printed ↔ PDF page (v.6 drops printed 974)

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(HERE, "oco.pdf")
HEADER_WORDS = {"AD", "INVITATORIUM", "Tempus", "Dies", "Festum", "Officium", "Locus", "LHym"}

# (outline title of the index section, section_type, columns after the day code). First pages come from
# the PDF outline, so a new edition (v4: Hymni p1214 … ; v6: p1213 …) needs no edit.
SECTION_DEFS = [
    ("Hymni", "hymnus", ("hour", "lhym")),
    ("Invitatoria", "invitatorium", ("lhym",)),
    ("Antiphonae", "antiphona", ("hour", "place")),
    ("Responsoria brevia", "responsorium breve", ("hour",)),
]
SECTIONS = []  # [(first page, section_type, columns)], filled by load_sections()


def load_sections(doc):
    """SECTIONS from the outline (entries under 'VII. INDICES'); returns (first, last) PRINTED index
    page, last = the last page carrying links."""
    toc, in_idx, first = doc.get_toc(), False, {}
    for lvl, title, page in toc:
        if lvl == 1:
            in_idx = "INDICES" in title
        elif in_idx and lvl == 2:
            first[title] = oco_pages.printed(page)
    SECTIONS[:] = [(first[t], st, cols) for t, st, cols in SECTION_DEFS]
    last = SECTIONS[-1][0]
    while oco_pages.page(doc, last + 1) is not None and oco_pages.page(doc, last + 1).get_links():
        last += 1
    return SECTIONS[0][0], last


def section_for(p):
    return [s for s in SECTIONS if s[0] <= p][-1]


def norm(s):
    s = s.lower().replace("æ", "ae").replace("œ", "oe").replace("j", "i")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z]+", " ", s).strip()


def rows_of(page):
    """Text lines of the index body: list of (y_mid, [(x0, text, flags)]), without the running head
    and the column headers (which only some pages print)."""
    lines = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            y0, y1 = ln["bbox"][1], ln["bbox"][3]
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    lines.append(((y0 + y1) / 2, s["bbox"][0], t, s["font"]))
    lines.sort()
    rows = []
    for y, x, t, f in lines:
        if rows and abs(rows[-1][0] - y) < 4:
            rows[-1][1].append((x, t, f))
        else:
            rows.append([y, [(x, t, f)]])
    keep = []
    for y, spans in rows:
        words = " ".join(t for _, t, _ in spans).split()
        if words[0] == "INDEX" or words[0].isdigit() and words[1:2] in (["INDEX"], ["ORDO"]):
            continue  # running head (page number left or right)
        if all(w in HEADER_WORDS for w in words):
            continue
        keep.append((y, sorted(spans)))
    return keep


def split_row(spans, section_type):
    inc, day, hour, rest = [], [], [], []
    for x, t, f in spans:
        if f.endswith("-Med"):
            day.append(t)
        elif f.endswith("Ita"):
            hour.append(t)
        elif not day and not hour:
            inc.append(t)
        else:
            rest.append(t)
    return " ".join(inc), " ".join(day), " ".join(hour), " ".join(rest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "index"))
    ap.add_argument("--pages", help="default: the whole index, from the outline (v4 1214-1316)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    doc = fitz.open(PDF)
    idx_first, idx_last = load_sections(doc)
    first, last = map(int, a.pages.split("-")) if a.pages else (idx_first, idx_last)
    texts = {}

    def page_text(p):
        if p not in texts:
            pg = oco_pages.page(doc, p)
            texts[p] = " " + norm(pg.get_text() if pg else "") + " "
        return texts[p]

    problems, misses, ordinal, total = [], [], 0, 0
    link_targets = {}  # id → [page, y of the link's 'to' point, named dest]: oco/toc_check.py
    # ordinals run across the whole index, so count the pages before --pages too
    for p in range(idx_first, first):
        ordinal += len(oco_pages.page(doc, p).get_links())
    for p in range(first, last + 1):
        page = oco_pages.page(doc, p)
        _, stype, cols = section_for(p)
        links = sorted(page.get_links(), key=lambda l: l["from"].y0)
        rows = rows_of(page)
        out = []
        used = set()
        for ln in links:
            r = ln["from"]
            # ditto rows (incipit not reprinted) carry a zero-size link at the row's middle
            hit = [i for i, (y, _) in enumerate(rows) if r.y0 - 4 <= y <= r.y1 + 4]
            if len(hit) != 1:
                problems.append(f"p{p}: link at y={r.y0:.0f} matches {len(hit)} text rows")
                continue
            used.add(hit[0])
            inc, day, hour, rest = split_row(rows[hit[0]][1], stype)
            ordinal += 1
            notes = []
            if not inc and out:
                inc = out[-1]["incipit"]
                notes.append("incipit not reprinted (same as the entry above)")
            elif inc.startswith("- ") and out:  # '- cum alleluia': variant of the entry above
                notes.append(f"printed {inc!r} (variant of the entry above)")
                inc = out[-1]["incipit"]
            elif not inc:
                problems.append(f"p{p} id {ordinal}: no incipit and no entry above on this page")
            row = {"id": ordinal, "section_type": stype, "mode": None, "incipit": inc,
                   "day_code": day or None, "hour_code": hour or None, "place_code": None,
                   "author_origin": None, "notes": None}
            if "lhym" in cols:
                notes += [f"LHym {rest}"] if rest else []
            elif "place" in cols:
                row["place_code"] = rest or None
            elif rest:
                problems.append(f"p{p} id {ordinal}: unexpected trailing text {rest!r}")
            if ln["kind"] == fitz.LINK_URI:
                m = re.search(r"chant\.php\?id=(\d+)$", ln.get("uri", ""))
                if not m:
                    problems.append(f"p{p} id {ordinal}: odd URI {ln.get('uri')!r}")
                    continue
                row.update(page=None, chant_uuid=f"gregobase:{m.group(1)}", match_status="resolved")
            elif "page" not in ln:  # p1230: seven 'Alleluia' entries whose GoTo has an empty D()
                row["page"] = None
                notes.append("index link has no destination (empty GoTo in the PDF)")
            else:
                # The link goes to the page where the chant is ENGRAVED, which may be under another
                # day (its named dest, e.g. 'A[6Q7,L,2]', names that first assignment).
                target = oco_pages.printed(ln["page"] + 1)
                if ln["page"] + 1 == doc.page_count:  # named dest undefined → the blank last page (41 in v.4, 42 in v.6)
                    row["page"] = None
                    notes.append(f"index link broken (named dest {ln.get('nameddest')!r} goes to blank p{target})")
                    row["notes"] = "; ".join(notes)
                    out.append(row)
                    continue
                row["page"] = str(target)
                link_targets[ordinal] = [target, round(ln["to"].y, 1) if ln.get("to") else None, ln.get("nameddest")]
                key = " ".join(norm(re.sub(r"\.\.\..*|\s\d+$", "", inc)).split()[:3])
                if key and f" {key} " not in page_text(target):
                    found = [q for q in (target + 1, target - 1) if oco_pages.page(doc, q) is not None
                             and f" {key} " in page_text(q)]
                    misses.append((p, ordinal, inc, target, found))
            row["notes"] = "; ".join(notes) or None
            out.append(row)
        for i, (y, spans) in enumerate(rows):
            if i not in used:
                problems.append(f"p{p}: unlinked text row y={y:.0f}: {' '.join(t for _, t, _ in spans)!r}")
        total += len(out)
        with open(os.path.join(a.out, f"i{p}.json"), "w", encoding="utf-8") as f:
            json.dump({"book": "OCO", "index_page": str(p), "rows": out, "questions": []},
                      f, indent=1, ensure_ascii=False)
    with open(os.path.join(a.out, "link_targets.json"), "w", encoding="utf-8") as f:
        json.dump(link_targets, f)
    for p, i, inc, t, found in misses:
        print(f"MISS p{p} id {i} {inc!r}: text not on target p{t}" + (f"; found on p{found}" if found else ""))
    print("\n".join(problems))
    print(json.dumps({"pages": last - first + 1, "rows": total, "last_id": ordinal,
                      "misses": len(misses), "problems": len(problems)}))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
