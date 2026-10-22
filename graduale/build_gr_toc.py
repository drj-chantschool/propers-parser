"""
Build a bookmark outline (table of contents) for graduale romanum.pdf from the
chapter/section meta.json files and the reviewed subsections*.json files.

Page arithmetic (all 1-indexed):
  chapter meta.page_offset C   = page in graduale romanum.pdf where the chapter starts
  section meta.page_offset S   = page in the chapter PDF where the section starts
  subsections.json "page" p    = page in the PDF that file describes
  -> chapter-level file:  C + p - 1
  -> section-level file:  C + S + p - 2

Usage:
  python build_gr_toc.py            # dry run: print outline
  python build_gr_toc.py --write    # write outline into the PDF (saves a .bak first)
"""

import json
import re
import shutil
import sys
from pathlib import Path

import fitz

GR = Path(__file__).parent
PDF = GR / "graduale romanum.pdf"
SPECS = GR / "specs"

# meta.json titles carry OCR noise for a few chapters
CHAPTER_TITLES = {
    "1": "PROPRIUM DE TEMPORE",
    "2": "COMMUNIA",
    "3": "PROPRIUM DE SANCTIS",
    "4": "MISSAE RITUALES AD DIVERSA ET VOTIVAE",
    "5": "LITURGIA DEFUNCTORUM",
    "6": "CANTUS IN ORDINE MISSAE OCCURRENTES",
    "7": "APPENDIX",
    "8": "INDICES",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# OCR repairs for heading text (the scans render the AE ligature as £, I as ! or l, etc.).
# Ordered: earlier rules feed later ones.
OCR_RULES = [
    (r"MAR(?:il|IJ|L!|Ji|l|L|J)[£E](?![A-Z])", "MARIAE"),
    (r"(?:il|II)£|ilE\b", "IAE"),
    (r"(?<=[A-Z])!(?:\.{1,3})?£", "IAE"),
    (r"(?: ?1|J|\.l|l|\]|\.)£", "AE"),
    (r"£", "AE"),
    (r"(?<=[A-Z])(?:lE|JE| 1E\b)", "AE"),
    (r"(?<=[A-Z])ill\b", "AE"),
    (r"(?<=[A-Z])!", "I"),
]

# Residual fixes after OCR_RULES: split words, garbled names, truncated headings.
TEXT_FIXES = {
    "HEBDOMAD A SANCTA": "HEBDOMADA SANCTA",
    "AD VIGILIAM PACHALEM": "AD VIGILIAM PASCHALEM",
    "Quando sollemnitas Ascensionis Domini zn dominicam sequentem":
        "Quando sollemnitas Ascensionis Domini in dominicam sequentem transfertur",
    "Feria 2:": "Feria 2", "Feria 3 :": "Feria 3",
    "S. ANTONII, ABBA TIS": "S. ANTONII, ABBATIS",
    "IN PRAESENT ATIONE DOMINI": "IN PRAESENTATIONE DOMINI",
    "S. POL YCARPI, EPISCOPI ET MARTYRIS": "S. POLYCARPI, EPISCOPI ET MARTYRIS",
    "SS. PERPETUAE ET FELICITATI S , MARTYRUM": "SS. PERPETUAE ET FELICITATIS, MARTYRUM",
    "S. FRANCISCAE ROMANAE, RELIGIO S AE": "S. FRANCISCAE ROMANAE, RELIGIOSAE",
    "S. CYRILLI HIEROSOL YMITANI, EPISCOPI ET ECCLESIAE DOCTORIS":
        "S. CYRILLI HIEROSOLYMITANI, EPISCOPI ET ECCLESIAE DOCTORIS",
    "S. IOANNIS BAPTISTAE D E LA SALLE, PRESBYTERI": "S. IOANNIS BAPTISTAE DE LA SALLE, PRESBYTERI",
    "S. MA TTHIAE, APOSTOLI": "S. MATTHIAE, APOSTOLI",
    "SS. CAROLI L WANG A ET SOCIORUM, MARTYRUM": "SS. CAROLI LWANGA ET SOCIORUM, MARTYRUM",
    "S. EPHR&M, DIACONI ET ECCLESIAE DOCTORIS": "S. EPHRAEM, DIACONI ET ECCLESIAE DOCTORIS",
    "IN TRANSFIGURA TIONE DOMINI": "IN TRANSFIGURATIONE DOMINI",
    "S. CAIET ANI, PRESBYTERI": "S. CAIETANI, PRESBYTERI",
    "S. MA TTHAEI, APOSTOLI ET EVANGELISTAE": "S. MATTHAEI, APOSTOLI ET EVANGELISTAE",
    "S. TERESIAE DE A VILA, VIRGINIS ET ECCLESIAE DOCTORIS":
        "S. TERESIAE DE AVILA, VIRGINIS ET ECCLESIAE DOCTORIS",
    "S. FRANCI SCI XAVIER, PRESBYTERI": "S. FRANCISCI XAVIER, PRESBYTERI",
    "S. DAMASI I, PAPAE": "S. DAMASI I, PAPAE",
    "S. IOANNAE FRANCISCAE DE CHANTAL,": "S. IOANNAE FRANCISCAE DE CHANTAL, RELIGIOSAE",
    "SS. MICHAELIS, GABRIELIS ET RAPHAELIS,": "SS. MICHAELIS, GABRIELIS ET RAPHAELIS, ARCHANGELORUM",
    "SS. SEPTEM FUNDATORUM ORDINIS SERVORUM BEATIAE MARIAE VIRGINIS":
        "SS. SEPTEM FUNDATORUM ORDINIS SERVORUM BEATAE MARIAE VIRGINIS",
    "S. FRANCISCAE ROMANAE, RELIGIO S ill": "S. FRANCISCAE ROMANAE, RELIGIOSAE",
    "IN DEDICATIONAE BASILICAE S. MARIAE": "IN DEDICATIONE BASILICAE S. MARIAE",
    "SS. XYSTI II, P A P AE , ET SOCIORUM, MARTYRUM": "SS. XYSTI II, PAPAE, ET SOCIORUM, MARTYRUM",
    "S. BARTHOLOMAE1, APOSTOLI": "S. BARTHOLOMAEI, APOSTOLI",
    "S. MARGARIT IAE SCOT IAE": "S. MARGARITAE SCOTIAE",
    "S. ELISABETH HUNGARIAE, RELIGIOSIAE": "S. ELISABETH HUNGARIAE, RELIGIOSAE",
}

# Sanctorale days whose feast heading the extraction missed or truncated (the
# printed title spans several lines). Checked against the page text.
FEAST_TITLES = {
    "Die 11 februarii": "B. MARIAE VIRGINIS DE LOURDES",
    "Die 15 augusti": "IN ASSUMPTIONE B. MARIAE VIRGINIS",
    "Die 14 septembris": "IN EXALTATIONE SANCTAE CRUCIS",
    "Die 16 octobris": "S. HEDVIGIS, RELIGIOSAE",
    "Die 1 novembris": "OMNIUM SANCTORUM",
    "Die 2 novembris": "IN COMMEMORATIONE OMNIUM FIDELIUM DEFUNCTORUM",
    "Die 9 novembris": "IN DEDICATIONE BASILICAE LATERANENSIS",
    "Die 18 novembris": "IN DEDICATIONE BASILICARUM SS. PETRI ET PAULI, APOSTOLORUM",
    "Die 8 decembris": "IN CONCEPTIONE IMMACULATA B. MARIAE VIRGINIS",
}


def clean(text):
    if isinstance(text, list):
        text = " / ".join(str(t) for t in text)
    text = " ".join(str(text).split())
    for pat, rep in OCR_RULES:
        text = re.sub(pat, rep, text)
    return TEXT_FIXES.get(text, text)


# ---- spec-derived headings ---------------------------------------------------
# Chapters without a subsections file get their Mass headings from specs/*.json
# (one spec per Mass; the spec's `label` carries the Latin title after " — ").
# Group headings the specs can't supply are listed here: (level, title, pdf page, y),
# page/y read off the text layer. Masses without chants of their own have no spec
# and are listed here too.
CH4_HEADINGS = [
    (2, "MISSAE RITUALES", 638, 37),
    (3, "I. In conferendis sacramentis initiationis christianae", 638, 89),
    (3, "II. In conferendis sacris Ordinibus", 639, 295),
    (3, "III. Ad ministrandum Viaticum", 640, 359),
    (3, "IV. Pro sponsis", 640, 427),
    (3, "V. In benedictione abbatis vel abbatissae", 642, 245),
    (3, "VI. In die consecrationis virginum et in professione religiosorum", 642, 355),
    (2, "MISSAE AD DIVERSA", 645, 38),
    (3, "I. Pro sancta Ecclesia", 645, 76),
    (3, "II. Pro rebus publicis", 648, 88),
    (3, "III. In diversis circumstantiis publicis", 648, 387),
    (3, "IV. Pro quibusdam necessitatibus particularibus", 652, 52),
    (2, "MISSAE VOTIVAE", 653, 38),
    (3, "De Ss.ma Trinitate", 653, 78),
    (3, "De Mysterio S. Crucis", 653, 124),
    (3, "De beata Maria Virgine", 657, 190),
    (3, "De uno sancto Apostolo", 661, 382),
]
# group headings whose children are the specs that follow them
CH4_GROUPS = {t for lvl, t, _, _ in CH4_HEADINGS
              if lvl == 2 or t.startswith(("I. In conferendis sacramentis", "I. Pro sancta",
                                           "II. Pro rebus", "III. In diversis", "IV. Pro quibusdam"))}
# single-Mass ritual sections: the roman-numeral heading already is the Mass
CH4_SKIP_SPECS = {"in-conferendis-sacris-ordinibus", "pro-sponsis",
                  "in-benedictione-abbatis", "in-die-consecrationis-virginum"}
# the BVM votive forms have English-only labels; titles as printed (p662-663)
SPEC_TITLES = {
    "de-beata-maria-virgine-adventus": "Tempore Adventus",
    "de-beata-maria-virgine-nativitatis": "Tempore Nativitatis",
    "de-beata-maria-virgine-post-baptismatis": "Tempore per annum, post festum Baptismatis Domini",
    "de-beata-maria-virgine-paschali": "Tempore paschali",
    "de-beata-maria-virgine-post-pentecosten-a": "Tempore per annum, post Pentecosten A",
    "de-beata-maria-virgine-post-pentecosten-b": "Tempore per annum, post Pentecosten B",
    "de-beata-maria-virgine-post-pentecosten-c": "Tempore per annum, post Pentecosten C",
    "ordo-exsequiarum-vigilia": "DE VIGILIA PRO DEFUNCTO",
    "hildegardis-osb": "S. HILDEGARDIS, VIRGINIS",
}

_doc = None
_printed_to_pdf = None


def doc():
    global _doc
    if _doc is None:
        _doc = fitz.open(PDF)
    return _doc


def pdf_page_for(printed):
    global _printed_to_pdf
    if _printed_to_pdf is None:
        mapping = load(GR / "page_mapping.json")["mapping"]
        _printed_to_pdf = {v: int(k) for k, v in mapping.items() if v}
    return _printed_to_pdf.get(printed)


def norm(text):
    return re.sub(r"[^a-z]", "", text.lower())


def specs_between(first_pdf, last_pdf):
    """(slug, title, pdf_page, y) for each spec whose first chant lies in the page range.
    y is the heading found in the text layer, else just above the first chant's band."""
    out = []
    for f in sorted(SPECS.glob("*.json")):
        spec = load(f)
        chants = [c for c in spec.get("chants", []) if isinstance(c.get("page"), int)]
        if not chants:
            continue
        printed, band_top = min((c["page"], (c.get("band") or [60])[0]) for c in chants)
        page = pdf_page_for(printed)
        if page is None or not first_pdf <= page <= last_pdf:
            continue
        title = SPEC_TITLES.get(f.stem) or spec["label"].split(" — ")[-1].strip()
        key = norm(title)[:30]
        found = None
        # the BVM forms share prefixes (and A/B/C share a heading), so trust their bands
        for p in () if f.stem.startswith("de-beata-maria-virgine") else (page, page - 1):
            hits = [b[1] for b in doc()[p - 1].get_text("blocks")
                    if len(b[4]) < 120 and key in norm(b[4])]
            if hits:
                found = (p, hits[0])
                break
        out.append((f.stem, title, *(found or (page, max(0, band_top - 25)))))
    return sorted(out, key=lambda r: (r[2], r[3]))


def chapter4_rows():
    items = [("h", lvl, t, p, y) for lvl, t, p, y in CH4_HEADINGS]
    items += [("s", slug, t, p, y) for slug, t, p, y in specs_between(637, 661)
              if slug not in CH4_SKIP_SPECS]
    items.sort(key=lambda r: (r[3], r[4]))
    rows, group_lvl = [], 2
    for kind, a, title, page, y in items:
        if kind == "h":
            rows.append([a, title, page, y])
            if title in CH4_GROUPS:
                group_lvl = a
            elif a == 2:
                group_lvl = 2
        else:
            lvl = 4 if a.startswith("de-beata-maria-virgine") else group_lvl + 1
            rows.append([lvl, title, page, y])
    return rows


def entries_for(chapter_dir):
    """Yield (level, title, pdf_page, y) for one chapter; level 1 = chapter."""
    num = chapter_dir.name
    c = load(chapter_dir / "meta.json")["page_offset"]
    yield 1, CHAPTER_TITLES[num], c, None

    chapter_file = next((chapter_dir / f for f in ("subsections.json", "subsections_ai.json")
                         if (chapter_dir / f).exists()), None)
    seen = set()
    rows = []
    if chapter_file:
        entries = load(chapter_file)
        for i, e in enumerate(entries):
            t = clean(e.get("text") or e.get("heading", ""))
            seen.add(t.lower())
            row = [2 + e.get("level", 0), t, c + e["page"] - 1, e.get("y")]
            rows.append(row)
            if t in FEAST_TITLES:
                nxt = entries[i + 1] if i + 1 < len(entries) else None
                if nxt and nxt.get("level", 0) > e.get("level", 0):
                    entries[i + 1] = dict(nxt, text=FEAST_TITLES[t])
                else:
                    rows.append([row[0] + 1, FEAST_TITLES[t], row[2], row[3]])
    if num == "5":
        # the funeral-rite stations are printed as parts of the Ordo Exsequiarum
        ordo = next(i for i, r in enumerate(rows) if "ORDO EXSEQUIARUM" in r[1])
        for r in rows[ordo + 1:]:
            r[0] += 1
        # the Vigil has a spec but no subsections entry
        for slug, title, page, y in specs_between(672, 672):
            if slug == "ordo-exsequiarum-vigilia":
                rows.insert(ordo + 1, [3, title, page, y])
    if num == "4":
        rows += chapter4_rows()
    if num == "7":
        # only the O.S.B. proper Masses have specs so far
        rows.append([2, "MISSAE PROPRIAE ORDINIS SANCTI BENEDICTI", 849, 58])
        rows += [[3, t, p, y] for _, t, p, y in specs_between(849, 879)]

    sections = sorted((d for d in chapter_dir.iterdir()
                       if d.is_dir() and d.name.split("_")[0].isdigit()
                       and (d / "meta.json").exists()),
                      key=lambda d: int(d.name.split("_")[0]))
    for d in sections:
        s = load(d / "meta.json")["page_offset"]
        sub = d / "subsections.json"
        if chapter_file:
            # chapter-level file already lists sections; only add headings it lacks,
            # slotted in after the last row on or before their page
            if sub.exists():
                for e in load(sub):
                    t = clean(e.get("text") or e.get("heading", ""))
                    if t.lower() not in seen:
                        page = c + s + e["page"] - 2
                        at = max(i for i, r in enumerate(rows) if r[2] <= page) + 1
                        rows.insert(at, [3 + e.get("level", 0), t, page, e.get("y") or None])
            continue
        title = clean(load(d / "meta.json")["title"])
        rows.append([2, title, c + s - 1, None])
        if sub.exists():
            entries = load(sub)
            top = [e for e in entries if e.get("level", 0) == 0]
            for e in entries:
                t = clean(e.get("text") or e.get("heading", ""))
                if len(top) == 1 and e is top[0] and t.lower() == title.lower():
                    continue  # sole top heading just repeats the section title
                rows.append([3 + e.get("level", 0), t, c + s + e["page"] - 2, e.get("y")])
    yield from rows



def build():
    toc = []
    for ch in sorted((d for d in GR.iterdir() if d.is_dir() and d.name.isdigit()),
                     key=lambda d: int(d.name)):
        for lvl, title, page, y in entries_for(ch):
            toc.append([lvl, title, page, y])
    return toc


def main():
    toc = build()
    doc = fitz.open(PDF)
    n = doc.page_count
    out, prev = [], 0
    for lvl, title, page, y in toc:
        lvl = min(lvl, prev + 1)
        prev = lvl
        if not 1 <= page <= n:
            print(f"!! page {page} out of range: {title}")
            continue
        if y:
            dest = {"kind": fitz.LINK_GOTO, "page": page - 1,
                    "to": fitz.Point(0, max(0, y - 20)), "zoom": 0}
            out.append([lvl, title, page, dest])
        else:
            out.append([lvl, title, page])
    for item in out:
        print("  " * (item[0] - 1) + f"{item[1]}  [p{item[2]}]")
    print(f"\n{len(out)} entries")
    if "--write" in sys.argv:
        bak = PDF.with_suffix(".pdf.bak")
        if not bak.exists():
            shutil.copy2(PDF, bak)
        doc.set_toc(out)
        doc.saveIncr()
        print(f"Wrote outline to {PDF} (backup: {bak.name})")


if __name__ == "__main__":
    main()
