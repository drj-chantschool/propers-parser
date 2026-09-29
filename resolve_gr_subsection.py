"""
resolve_gr_subsection.py — Step-0 prep for /gr-batch

Given one or more week numbers (and a season), resolves each to:
  - the heading row in graduale_toc (TEXT, PRINTED_PAGE, Y)
  - the printed-page span [start … end]
  - the next-heading boundary (NOT to cross)
  - the lit_epoch slug (with existence check)
  - the split PDF path (with existence check)
  - a ready-to-paste producer-brief anchor block

Seasons (--season):
  ot    Ordinary Time weeks 1..34  → HEBDOMADA <ordinal>        → OT-OT-NN
        PDFs under graduale/1/7_tempus-per-annum/
  pasc  Easter weeks 2..6          → HEBDOMADA <ordinal> PASCHAE → PASC-AD_ASC-NN
        PDFs under graduale/1/5_tempus-paschale/
        (week 1 is the day-based Octave; weeks 7+ live in the Ascension chapter
        with POST_ASC/ASC subseasons — out of scope for this week-formulary resolver.)
  lent  Lent weeks 0..5 — DAY-BASED, not a week formulary: each day (DOMINICA, FERIA N,
        SABBATO) is its own lit_epoch day-slug (TQ-LENT-NN-D), so one --week resolves to
        SEVERAL producer-brief anchors, one per day found under that week's heading.
        Week 0 = "Dies post Cineres" (Ash Wed + the 3 ferias after, days 4-7 only, no
        Dominica/Feria II/III); weeks 1-5 = HEBDOMADA <ordinal> QUADRAGESIMAE (days 1-7).
        PDFs under graduale/1/4_tempus-quadragesimae/<week-folder>/<day>.pdf — nested TWO
        levels deep (chapter/week-folder/day-file), unlike ot/pasc's flat pdf_dir.
        Tolerates graduale_toc's OCR-corrupted week headings (e.g. "QUADRAGESIMJ£" for
        "QUADRAGESIMAE") by prefix-matching "HEBDOMADA <ordinal>" rather than requiring an
        exact spelling, and reuses whatever text actually matched (typos included) to look
        up the split-PDF folder, since the folder names were slugified from the same OCR text.
        Holy Week (TQ-HOLYWEEK) is NOT covered — Holy Thursday's split is a subfolder
        (likely Chrism Mass + Mass of the Lord's Supper), needs separate handling first.

  sanctorale  Proprium de Sanctis (chapter 3) — DATE-BASED, use --date not --week.
        These days are NOT in graduale_toc at all; headings come from
        graduale/3/subsections_ai.json (level 1 = 'Die N <mensis>' or 'Eodem die',
        level 2 = feast title, `page` = 1-indexed into 3_proprium-de-sanctis.pdf).
        A date bearing two saints ('Eodem die') resolves to SEVERAL anchors, like lent.
        The slug comes from proper_of_saints(month_nominal, day_nominal) — the GR titles
        are Latin and the slugs English, so never match them by name; ~22 dates carry
        more than one saint and are reported AMBIGUOUS for the director to pick.
        Also reports the printed rank marker (Mem./Fest./Sol.) when present — that is
        rank_code data, NOT a chant, and its ABSENCE means nothing (All Saints is a
        solemnity and prints no marker).

Usage:
    python resolve_gr_subsection.py --week 25 26                 # OT (default season)
    python resolve_gr_subsection.py --season pasc --week 2 3 4 5 6
    python resolve_gr_subsection.py --season pasc --week 2-6     # range syntax also accepted
    python resolve_gr_subsection.py --season lent --week 0       # Ash Wed + 3 ferias (4 anchors)
    python resolve_gr_subsection.py --season lent --week 1-5     # weeks 1-5 (up to 7 anchors each)
    python resolve_gr_subsection.py --season sanctorale --date 8-20
    python resolve_gr_subsection.py --season sanctorale --date "August 20" aug-24

Environment:
    Interpreter: C:\\Users\\johna\\liturgio\\.venv\\Scripts\\python.exe
    Run with PYTHONUTF8=1

DB:
    MySQL via OS keyring (service "liturgio-mysql", user "liturgio_ro").
    Table graduale_toc columns: IDX, Y, LEVEL, TEXT, PRINTED_PAGE (no PDF_PAGE).
    Table lit_epoch columns: slug, kind, title, …
"""

import argparse
import re
import sys
from pathlib import Path

import keyring
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Roman numerals + English ordinals (1..34) for human-readable labels
# ---------------------------------------------------------------------------
_ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
    6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X",
    11: "XI", 12: "XII", 13: "XIII", 14: "XIV", 15: "XV",
    16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX", 20: "XX",
    21: "XXI", 22: "XXII", 23: "XXIII", 24: "XXIV", 25: "XXV",
    26: "XXVI", 27: "XXVII", 28: "XXVIII", 29: "XXIX", 30: "XXX",
    31: "XXXI", 32: "XXXII", 33: "XXXIII", 34: "XXXIV",
}


def _ordinal(n: int) -> str:
    if 11 <= n <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"


# ---------------------------------------------------------------------------
# Latin feminine ordinals (for "HEBDOMADA <ordinal>" headings), 1..34
# ---------------------------------------------------------------------------
_LAT_UNITS = {
    1: "PRIMA", 2: "SECUNDA", 3: "TERTIA", 4: "QUARTA", 5: "QUINTA",
    6: "SEXTA", 7: "SEPTIMA", 8: "OCTAVA", 9: "NONA",
}
_LAT_TENS = {10: "DECIMA", 20: "VIGESIMA", 30: "TRIGESIMA"}


def latin_ordinal(n: int) -> str:
    """Feminine Latin ordinal used in Graduale week headings (PRIMA … TRIGESIMA QUARTA).

    A wrong value here surfaces loudly as a graduale_toc no-match, so it is
    self-checking rather than silently mis-resolving.
    """
    if n == 11:
        return "UNDECIMA"
    if n == 12:
        return "DUODECIMA"
    if 1 <= n <= 9:
        return _LAT_UNITS[n]
    if n in _LAT_TENS:
        return _LAT_TENS[n]
    tens, unit = (n // 10) * 10, n % 10
    if tens in _LAT_TENS and unit in _LAT_UNITS:
        return f"{_LAT_TENS[tens]} {_LAT_UNITS[unit]}"
    raise ValueError(f"no Latin ordinal for week {n}")


# ---------------------------------------------------------------------------
# Season configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
GRADUALE_ROOT = SCRIPT_DIR / "graduale" / "1"

SEASONS = {
    "ot": {
        "name": "Ordinary Time",
        "pdf_dir": "7_tempus-per-annum",
        "weeks": range(1, 35),
        "heading": lambda n: f"HEBDOMADA {latin_ordinal(n)}",
        "slug": lambda n: f"OT-OT-{n:02d}",
        "subsection": lambda n: f"ot-ot-{n:02d}",
        "label": lambda n: f"{_ordinal(n)} week of Ordinary Time (Hebdomada {_ROMAN[n]} per annum)",
    },
    "pasc": {
        "name": "Easter",
        "pdf_dir": "5_tempus-paschale",
        # Week 1 = Octave (day-based); weeks 7+ = Ascension chapter (POST_ASC/ASC).
        "weeks": range(2, 7),
        "heading": lambda n: f"HEBDOMADA {latin_ordinal(n)} PASCHAE",
        "slug": lambda n: f"PASC-AD_ASC-{n:02d}",
        "subsection": lambda n: f"pasc-ad-asc-{n:02d}",
        "label": lambda n: f"{_ordinal(n)} week of Easter (Hebdomada {_ROMAN[n]} Paschae)",
    },
}

# ---------------------------------------------------------------------------
# Lent (day-based) — a "week" resolves to MULTIPLE lit_epoch day-slugs, one per
# printed day heading (DOMINICA/FERIA N/SABBATO), not a single week formulary.
# ---------------------------------------------------------------------------
LENT_PDF_DIR = "4_tempus-quadragesimae"
LENT_WEEKS = range(0, 6)  # 0 = Dies post Cineres; 1-5 = HEBDOMADA N QUADRAGESIMAE

_WKDAY_EN = {1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday",
             5: "Thursday", 6: "Friday", 7: "Saturday"}


def _lent_wkday(heading_text: str) -> int | None:
    """Map a LEVEL=3 Lent day heading to its calendar weekday (Sun=1..Sat=7). Tolerates
    week 0's specially-named days (FERIA QUARTA CINERUM, FERIA QUINTA POST CINERES) and
    OCR spacing quirks ('FERIA  QUARTA' double space) via substring match, not equality."""
    t = _norm(heading_text)
    if t.startswith("DOMINICA"):
        return 1
    if t.startswith("FERIA"):
        if "SECUNDA" in t:
            return 2
        if "TERTIA" in t:
            return 3
        if "QUARTA" in t:
            return 4
        if "QUINTA" in t:
            return 5
        if "SEXTA" in t:
            return 6
    if t.startswith("SABBATO"):
        return 7
    return None


def _lent_label(week_n: int, wkday: int, heading_text: str) -> str:
    """Mirrors the label style already used in the loaded tq-lent-*.json specs."""
    heading_title = " ".join(w.capitalize() for w in heading_text.split())
    if week_n == 0:
        if wkday == 4:
            return "Lent — Ash Wednesday (Feria Quarta Cinerum)"
        return f"Lent — {_WKDAY_EN[wkday]} after Ash Wednesday ({heading_title})"
    if wkday == 1:
        return f"Lent — {_ordinal(week_n)} Sunday (Dominica {_ROMAN[week_n]} in Quadragesima)"
    return f"Lent — {_ordinal(week_n)} week, {_WKDAY_EN[wkday]} ({heading_title})"


def slugify(s: str) -> str:
    """Match split_subsections.py's slugify so heading ↔ split-PDF names line up."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _norm(s: str) -> str:
    """Collapse whitespace + uppercase for tolerant heading comparison.

    (graduale_toc has e.g. 'HEBDOMADA  QUINTA PASCHAE' with a double space.)
    """
    return " ".join(s.split()).upper()


# ---------------------------------------------------------------------------
# DB engine
# ---------------------------------------------------------------------------
def _engine():
    pw = keyring.get_password("liturgio-mysql", "liturgio_ro")
    if pw is None:
        raise RuntimeError("No password found in keyring for liturgio-mysql / liturgio_ro")
    return create_engine(
        f"mysql+mysqlconnector://liturgio_ro:{pw}@localhost:3306/liturgio",
        future=True,
    )


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------
def fetch_toc_rows(conn) -> list[dict]:
    """Return all LEVEL=2 rows from graduale_toc (BOOK='GRADUALE'), ordered by IDX."""
    rows = conn.execute(text(
        "SELECT IDX, Y, LEVEL, TEXT, PRINTED_PAGE "
        "FROM graduale_toc "
        "WHERE BOOK = 'GRADUALE' AND LEVEL = 2 "
        "ORDER BY IDX"
    )).fetchall()
    return [{"idx": r[0], "y": r[1], "level": r[2], "text": r[3], "printed_page": r[4]}
            for r in rows]


def epoch_exists(conn, slug: str, kind: str = "week") -> bool:
    row = conn.execute(text(
        "SELECT 1 FROM lit_epoch WHERE slug = :slug AND kind = :kind LIMIT 1"
    ), {"slug": slug, "kind": kind}).fetchone()
    return row is not None


def find_split_pdf(pdf_dir: Path, heading: str) -> Path | None:
    """Find the split PDF for a heading by matching the slug, ignoring the
    numeric filename prefix (which is a list position, not the week number)."""
    target = slugify(heading) + ".pdf"
    if not pdf_dir.is_dir():
        return None
    for p in sorted(pdf_dir.glob("*.pdf")):
        if re.sub(r"^\d+_", "", p.name) == target:
            return p
    return None


def find_split_subdir(parent_dir: Path, heading: str) -> Path | None:
    """Find the week-level split SUBDIRECTORY for a heading by matching the slug, ignoring
    the numeric prefix — mirrors find_split_pdf but for a directory. Lent's split PDFs are
    nested two levels deep (chapter/week-folder/day-file.pdf), unlike ot/pasc's flat pdf_dir."""
    target = slugify(heading)
    if not parent_dir.is_dir():
        return None
    for p in sorted(parent_dir.iterdir()):
        if p.is_dir() and re.sub(r"^\d+_", "", p.name) == target:
            return p
    return None


def fetch_all_toc_rows(conn) -> list[dict]:
    """Return ALL rows (any LEVEL) from graduale_toc (BOOK='GRADUALE'), ordered by IDX.
    Needed for Lent's day-based resolution, which must see LEVEL=3 day headings nested
    under a LEVEL=1/2 week/section heading (fetch_toc_rows only fetches LEVEL=2)."""
    rows = conn.execute(text(
        "SELECT IDX, Y, LEVEL, TEXT, PRINTED_PAGE "
        "FROM graduale_toc WHERE BOOK = 'GRADUALE' ORDER BY IDX"
    )).fetchall()
    return [{"idx": r[0], "y": r[1], "level": r[2], "text": r[3], "printed_page": r[4]}
            for r in rows]


# ---------------------------------------------------------------------------
# Per-week resolution
# ---------------------------------------------------------------------------
def resolve_week(n: int, season: str, toc_rows: list[dict], conn) -> tuple[dict, bool]:
    """Resolve week N of the given season.  Returns (info_dict, ok)."""
    cfg = SEASONS[season]
    ok = True

    heading_expected = cfg["heading"](n)

    # Split PDF (matched by heading slug, not numeric prefix).
    pdf_dir = GRADUALE_ROOT / cfg["pdf_dir"]
    pdf_path = find_split_pdf(pdf_dir, heading_expected)
    pdf_exists = pdf_path is not None
    if not pdf_exists:
        ok = False

    # Heading row in graduale_toc (whitespace-tolerant match).
    heading_row = None
    for row in toc_rows:
        if _norm(row["text"]) == _norm(heading_expected):
            heading_row = row
            break
    if heading_row is None:
        ok = False

    # Next LEVEL=2 heading (by IDX) = the span boundary NOT to cross.
    next_heading_row = None
    if heading_row is not None:
        for row in toc_rows:
            if row["idx"] > heading_row["idx"]:
                next_heading_row = row
                break

    span_start = heading_row["printed_page"] if heading_row else None
    span_end = (next_heading_row["printed_page"] - 1) if next_heading_row else None

    epoch_slug = cfg["slug"](n)
    slug_exists = epoch_exists(conn, epoch_slug)
    if not slug_exists:
        ok = False

    info = {
        "n": n,
        "season": season,
        "subsection": cfg["subsection"](n),
        "label": cfg["label"](n),
        "heading_expected": heading_expected,
        "heading_row": heading_row,
        "next_heading_row": next_heading_row,
        "span_start": span_start,
        "span_end": span_end,
        "epoch_slug": epoch_slug,
        "slug_exists": slug_exists,
        "pdf_path": pdf_path,
        "pdf_exists": pdf_exists,
    }
    return info, ok


def _lent_chapter_bounds(all_rows: list[dict]) -> tuple[int, float] | None:
    """IDX range (exclusive lo, exclusive hi) of the 'TEMPUS QUADRAGESIMAE' LEVEL=1
    chapter. Needed because "HEBDOMADA SECUNDA"/"TERTIA"/etc. prefixes also occur in
    Advent, Ordinary Time, and Paschaltide headings elsewhere in the book — searching
    graduale_toc unscoped can match the WRONG season's week (caught via the week-2 sanity
    check below matching 'HEBDOMADA SECUNDA ADVENTUS' before this guard was added)."""
    chapter = next((r for r in all_rows
                     if r["level"] == 1 and _norm(r["text"]) == "TEMPUS QUADRAGESIMAE"), None)
    if chapter is None:
        return None
    next_chapter = next((r for r in all_rows
                          if r["idx"] > chapter["idx"] and r["level"] == 1), None)
    return chapter["idx"], (next_chapter["idx"] if next_chapter else float("inf"))


def resolve_lent_week(week_n: int, all_rows: list[dict], conn) -> tuple[list[dict], bool]:
    """Resolve week N of Lent (0 = Dies post Cineres) to a LIST of per-DAY info dicts —
    unlike ot/pasc, a Lent "week" is not one lit_epoch_slug: each printed day heading
    (DOMINICA/FERIA N/SABBATO) is its own day-kind lit_epoch row (TQ-LENT-NN-D). Each
    returned dict has the same shape resolve_week() produces, plus a "wkday" key, so
    print_anchor() is reused unchanged. Returns (day_infos, week_ok) where week_ok is
    False if the week's own heading or ANY of its days failed to resolve."""
    ok = True

    bounds = _lent_chapter_bounds(all_rows)
    if bounds is None:
        print("✗ 'TEMPUS QUADRAGESIMAE' chapter heading not found in graduale_toc",
              file=sys.stderr)
        return [], False
    lo_idx, hi_idx = bounds
    chapter_rows = [r for r in all_rows if lo_idx < r["idx"] < hi_idx]

    if week_n == 0:
        parent = next((r for r in chapter_rows if _norm(r["text"]) == "DIES POST CINERES"), None)
        parent_expected = "DIES POST CINERES"
    else:
        prefix = f"HEBDOMADA {latin_ordinal(week_n)}"
        # Prefix match, not equality: graduale_toc has OCR-corrupted spellings for some
        # weeks (e.g. "QUADRAGESIMJ£" for "QUADRAGESIMAE") — the ordinal prefix alone is
        # enough to identify the row, and we reuse ITS actual text (typos and all) below
        # for the split-PDF folder lookup, since that folder was slugified from the same
        # text. Scoped to chapter_rows so it can't match another season's same-ordinal week.
        parent = next((r for r in chapter_rows
                        if r["level"] <= 2 and _norm(r["text"]).startswith(_norm(prefix))), None)
        parent_expected = prefix + " QUADRAGESIMAE"

    if parent is None:
        print(f"WEEK {week_n}: ✗ parent heading not found in graduale_toc "
              f"(expected {parent_expected!r})", file=sys.stderr)
        return [], False

    lent_dir = GRADUALE_ROOT / LENT_PDF_DIR
    week_dir = find_split_subdir(lent_dir, parent["text"])
    if week_dir is None:
        print(f"WEEK {week_n}: ✗ no split subdirectory matching {parent['text']!r} "
              f"under {lent_dir.as_posix()}", file=sys.stderr)
        ok = False

    # Next LEVEL<=2 row (any level) = the boundary after which this week's days stop.
    next_top = next((r for r in all_rows
                      if r["idx"] > parent["idx"] and r["level"] <= 2), None)
    upper_idx = next_top["idx"] if next_top else float("inf")
    day_rows = [r for r in all_rows
                if parent["idx"] < r["idx"] < upper_idx and r["level"] == 3]
    if not day_rows:
        print(f"WEEK {week_n}: ✗ no LEVEL=3 day headings found under {parent['text']!r}",
              file=sys.stderr)
        return [], False

    infos = []
    for i, day_row in enumerate(day_rows):
        wkday = _lent_wkday(day_row["text"])
        if wkday is None:
            print(f"WEEK {week_n}: ✗ unrecognized day heading {day_row['text']!r} "
                  f"on p{day_row['printed_page']} — skipping", file=sys.stderr)
            ok = False
            continue

        next_row = day_rows[i + 1] if i + 1 < len(day_rows) else next_top
        span_end = (next_row["printed_page"] - 1) if next_row else None

        epoch_slug = f"TQ-LENT-{week_n:02d}-{wkday}"
        slug_exists = epoch_exists(conn, epoch_slug, kind="day")

        pdf_path = find_split_pdf(week_dir, day_row["text"]) if week_dir else None

        day_ok = slug_exists and pdf_path is not None
        ok = ok and day_ok

        infos.append({
            "n": week_n,
            "wkday": wkday,
            "season": "lent",
            "subsection": epoch_slug.lower(),
            "label": _lent_label(week_n, wkday, day_row["text"]),
            "heading_expected": day_row["text"],
            "heading_row": day_row,
            "next_heading_row": next_row,
            "span_start": day_row["printed_page"],
            "span_end": span_end,
            "epoch_slug": epoch_slug,
            "slug_exists": slug_exists,
            "pdf_path": pdf_path,
            "pdf_exists": pdf_path is not None,
            "ok": day_ok,
        })

    return infos, ok


# ---------------------------------------------------------------------------
# Sanctorale (Proprium de Sanctis) — DATE-based, and not in graduale_toc at all
# ---------------------------------------------------------------------------
SANCTORALE_CHAPTER = SCRIPT_DIR / "graduale" / "3"
SANCTORALE_HEADINGS = SANCTORALE_CHAPTER / "subsections_ai.json"
SANCTORALE_PDF = SANCTORALE_CHAPTER / "3_proprium-de-sanctis.pdf"
_PAGE_MAPPING = SCRIPT_DIR / "graduale" / "APPLIED" / "page_mapping.json"

# Latin month genitives as printed in 'Die 20 augusti', -> (number, folder stem)
_MONTHS = {
    "ianuarii": (1, "ianuarius"), "februarii": (2, "februarius"),
    "martii": (3, "martius"), "aprilis": (4, "aprilis"),
    "maii": (5, "maius"), "iunii": (6, "iunius"),
    "iulii": (7, "iulius"), "augusti": (8, "augustus"),
    "septembris": (9, "september"), "octobris": (10, "october"),
    "novembris": (11, "november"), "decembris": (12, "december"),
}
_MONTH_BY_NUM = {n: stem for n, stem in _MONTHS.values()}
_EN_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# right-margin rank markers; absence is NOT evidence of a lower rank
_RANK_MARKERS = {"mem": "MEMORIAL", "fest": "FEAST", "sol": "SOLEMNITY"}


def parse_dates(args: list[str]) -> list[tuple[int, int]]:
    """Parse '8-20', '08-20', 'aug-20', 'August 20' into (month, day) pairs."""
    out = []
    for raw in args:
        s = raw.strip().lower().replace(",", " ")
        m = re.match(r"^\s*([a-z]+|\d{1,2})\s*[-/ ]\s*(\d{1,2})\s*$", s)
        if not m:
            print(f"WARNING: cannot parse date {raw!r} — skipping", file=sys.stderr)
            continue
        mon_tok, day = m.group(1), int(m.group(2))
        if mon_tok.isdigit():
            mon = int(mon_tok)
        else:
            mon = _EN_MONTHS.get(mon_tok[:3])
            if mon is None:
                print(f"WARNING: unknown month {mon_tok!r} in {raw!r} — skipping",
                      file=sys.stderr)
                continue
        if not (1 <= mon <= 12 and 1 <= day <= 31):
            print(f"WARNING: date out of range: {raw!r} — skipping", file=sys.stderr)
            continue
        out.append((mon, day))
    return sorted(set(out))


def _section_delta(meta_path: Path) -> int | None:
    """Page delta for a split section.

    `meta.json`'s `page_offset` is the count of pages BEFORE the section, so the
    section's page 1 comes from parent page `page_offset + 1` — i.e. the additive
    delta is `page_offset - 1`, not `page_offset`. (Verified: Proprium de Sanctis
    meta says 529 but chapter p62 is main-PDF p590, delta 528.) Getting this wrong
    shifts every page by one, so it is cross-checked against the number printed on
    the page in resolve_sanctorale_date().
    """
    if not meta_path.is_file():
        return None
    import json as _json
    return int(_json.loads(meta_path.read_text(encoding="utf-8"))["page_offset"]) - 1


def _printed_from_chapter_page(chapter_page: int) -> int | None:
    """chapter PDF page -> printed page, via the calibrated main-PDF page mapping."""
    delta = _section_delta(SANCTORALE_CHAPTER / "meta.json")
    if delta is None or not _PAGE_MAPPING.is_file():
        return None
    import json as _json
    mapping = _json.loads(_PAGE_MAPPING.read_text(encoding="utf-8"))["mapping"]
    return mapping.get(str(chapter_page + delta))


def _printed_on_page(doc, chapter_page: int) -> int | None:
    """Read the page number printed in the top margin (the self-check for the delta).

    OCR splits it across spans ('59 4', '5'+'90'), so join every span in the top
    band and keep the digits.
    """
    try:
        page = doc[chapter_page - 1]
    except Exception:
        return None
    digits = ""
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            if l["bbox"][1] > 32:
                continue
            tok = "".join(re.sub(r"\D", "", s["text"]) for s in l["spans"])
            if tok:
                digits = tok
                break
        if digits:
            break
    return int(digits) if digits.isdigit() and 2 <= len(digits) <= 3 else None


def _rank_marker_near(doc, chapter_page: int, title_y: float) -> str | None:
    """The printed rank marker on/just under a feast title, or None.

    Matched at LINE level with the right-margin spans joined: OCR both mangles the
    word (`Sol.`->`sot.`) and splits it into separate spans (`Mem.`->'M','e','m.'),
    so per-span matching silently misses real markers.
    """
    try:
        page = doc[chapter_page - 1]
    except Exception:
        return None
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            y0 = l["bbox"][1]
            if not (title_y - 8 <= y0 <= title_y + 26):
                continue
            joined = "".join(s["text"] for s in l["spans"] if s["bbox"][0] >= 285.0)
            n = re.sub(r"[^a-z]", "", joined.lower())
            for stem, rank in _RANK_MARKERS.items():
                if n == stem or (len(n) == len(stem)
                                 and sum(a != b for a, b in zip(n, stem)) == 1):
                    return f"{joined.strip()} -> {rank}"
    return None


def _suggest_slug(title: str, candidates: list[tuple[str, str]]) -> str | None:
    """Best-guess slug for a date carrying several saints, by Latin↔English stem overlap.

    A SUGGESTION only — the caller must present it as such. Latin titles decline
    ('S. FABIANI' for Fabian, 'IOSEPH DE CALASANZ' for Joseph Calasanz), so this
    scores the longest common prefix between any title word and any common_name
    word, requiring >=4 chars and a UNIQUE winner. Names that translate rather than
    decline ('LUDOVICI' -> 'Louis') score nothing, which is the honest answer.
    """
    def words(s):
        return [w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in
                {"sancti", "sanctae", "beatae", "episcopi", "presbyteri", "martyris",
                 "martyrum", "virginis", "abbatis", "doctoris", "papae", "apostoli"}]

    scores = []
    for slug, name in candidates:
        best = 0
        for lw in words(title):
            for ew in words(name):
                k = 0
                while k < min(len(lw), len(ew)) and lw[k] == ew[k]:
                    k += 1
                best = max(best, k)
        scores.append((best, slug))
    scores.sort(reverse=True)
    if scores and scores[0][0] >= 4 and (len(scores) == 1 or scores[0][0] > scores[1][0]):
        return scores[0][1]
    return None


def _load_sanctorale_headings() -> list[dict]:
    import json as _json
    return _json.loads(SANCTORALE_HEADINGS.read_text(encoding="utf-8"))


def resolve_sanctorale_date(month: int, day: int, entries: list[dict],
                            conn, doc) -> tuple[list[dict], bool]:
    """Resolve one calendar date to per-Mass anchors (>1 when the date has 'Eodem die').

    Returns (infos, ok) with the same dict shape resolve_week() produces so
    print_anchor() is reused unchanged.
    """
    # --- ordered level-1 date headings, carrying 'Eodem die' forward
    dates: list[dict] = []
    for e in entries:
        if e.get("level") != 1:
            continue
        txt = (e.get("text") or "").strip()
        m = re.search(r"die\s+(\d{1,2})\s+([a-z]+)", txt, re.I)
        if m and m.group(2).lower() in _MONTHS:
            mon = _MONTHS[m.group(2).lower()][0]
            dates.append({"date": (mon, int(m.group(1))), "text": txt,
                          "page": e["page"], "y": e["y"]})
        elif re.search(r"eodem\s+die", txt, re.I) and dates:
            dates.append({"date": dates[-1]["date"], "text": txt,
                          "page": e["page"], "y": e["y"]})

    hits = [i for i, d in enumerate(dates) if d["date"] == (month, day)]
    if not hits:
        print(f"{month}-{day}: ✗ no 'Die {day} …' heading in {SANCTORALE_HEADINGS.name}",
              file=sys.stderr)
        return [], False

    # --- slug candidates for this calendar date
    rows = conn.execute(text(
        "SELECT slug, common_name FROM proper_of_saints "
        "WHERE month_nominal = :m AND day_nominal = :d ORDER BY slug"
    ), {"m": month, "d": day}).fetchall()
    candidates = [(r[0], r[1]) for r in rows]

    delta_ok = True
    infos, ok = [], True
    for k, i in enumerate(hits):
        d = dates[i]
        nxt = dates[i + 1] if i + 1 < len(dates) else None

        titles = [e for e in entries
                  if e.get("level") == 2
                  and (e["page"], e["y"]) > (d["page"], d["y"])
                  and (nxt is None or (e["page"], e["y"]) < (nxt["page"], nxt["y"]))]
        title_txt = titles[0]["text"].strip() if titles else "(no title line in headings JSON)"

        printed = _printed_from_chapter_page(d["page"])
        actual = _printed_on_page(doc, d["page"])
        # Only a SAME-LENGTH read is evidence: OCR routinely drops a digit from the
        # page number (606 -> '66', 618 -> '68'), and a short read like that is an
        # unreliable read, not a disagreement. A real off-by-one is 3 digits vs 3.
        if (printed is not None and actual is not None
                and len(str(actual)) == len(str(printed)) and actual != printed):
            delta_ok = False
        span_end = None
        if nxt is not None:
            nxt_printed = _printed_from_chapter_page(nxt["page"])
            if nxt_printed is not None:
                span_end = nxt_printed if nxt["page"] == d["page"] else nxt_printed - 1

        marker = _rank_marker_near(doc, d["page"], titles[0]["y"] if titles else d["y"])

        # --- slug
        if len(candidates) == 1:
            slug, cname, ambiguous = candidates[0][0], candidates[0][1], False
        elif not candidates:
            slug, cname, ambiguous = None, None, False
        else:
            slug, cname, ambiguous = None, None, True

        slug_exists = bool(slug) and conn.execute(text(
            "SELECT 1 FROM lit_epoch WHERE slug = :s AND kind = 'saint' LIMIT 1"
        ), {"s": slug}).fetchone() is not None

        stem = _MONTH_BY_NUM[month]
        month_dir = next((p for p in sorted(SANCTORALE_CHAPTER.iterdir())
                          if p.is_dir() and re.sub(r"^\d+_", "", p.name) == stem), None)
        pdf_path = month_dir / f"0_{stem}.pdf" if month_dir else None
        if pdf_path is not None and not pdf_path.is_file():
            pdf_path = None
        month_page = None
        if month_dir is not None:
            mdelta = _section_delta(month_dir / "meta.json")
            if mdelta is not None:
                month_page = d["page"] - mdelta

        extra = [f"split_pdf_page: {month_page}  (page {month_page} of the month split"
                 f" = chapter p{d['page']} = printed p{printed})"]
        if marker:
            extra.append(f"rank_marker: {marker}   [rank_code data, NOT a chant]")
        else:
            extra.append("rank_marker: (none printed) — absence is NOT evidence of rank")
        if ambiguous:
            extra.append("slug: ✗ AMBIGUOUS — this date carries several saints; pick by the "
                         "GR title: " + ", ".join(f"{s} ({n})" for s, n in candidates))
            hint = _suggest_slug(title_txt, candidates)
            if hint:
                extra.append(f"      SUGGESTION (unconfirmed, verify against the title): {hint}")
        elif not candidates:
            extra.append("slug: ✗ NO proper_of_saints ROW for this date — real calendar gap; "
                         "report it, do not invent a slug")

        this_ok = bool(slug) and slug_exists and pdf_path is not None and printed is not None
        ok = ok and this_ok

        infos.append({
            "n": f"{month}-{day}" + (f" [{k + 1}]" if len(hits) > 1 else ""),
            "unit_label": f"SANCTORALE {month:02d}-{day:02d}"
                          + (f"  (Mass {k + 1} of {len(hits)})" if len(hits) > 1 else ""),
            "season": "sanctorale",
            "subsection": slug or f"UNRESOLVED-{month:02d}-{day:02d}",
            "label": (f"{cname} ({title_txt}, {d['text']})" if cname
                      else f"{title_txt} ({d['text']})"),
            "heading_expected": d["text"],
            "heading_row": {"text": f"{d['text']} — {title_txt}",
                            "printed_page": printed, "y": d["y"]},
            "next_heading_row": ({"text": nxt["text"],
                                  "printed_page": _printed_from_chapter_page(nxt["page"]),
                                  "y": nxt["y"]} if nxt else None),
            "span_start": printed,
            "span_end": span_end,
            "epoch_slug": slug or "(unresolved)",
            "slug_exists": slug_exists,
            "pdf_path": pdf_path,
            "pdf_exists": pdf_path is not None,
            "extra_lines": extra,
            "ok": this_ok,
        })

    if not delta_ok:
        print("✗ page-delta self-check FAILED: the computed printed page disagrees with "
              "the number printed on the page. meta.json's page_offset convention may "
              "have changed — fix _section_delta() before trusting these spans.",
              file=sys.stderr)
        ok = False

    return infos, ok


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def print_anchor(info: dict, ok: bool) -> None:
    n = info["n"]
    hr = info["heading_row"]
    nhr = info["next_heading_row"]
    subsection = info["subsection"]
    label = info["label"]

    unit_noun = "day" if info["season"] == "sanctorale" else "week"
    unit = f"this {unit_noun}" if info["season"] == "sanctorale" else f"week {n}"

    print("=" * 70)
    if "unit_label" in info:
        print(f"{info['unit_label']}  [{label}]")
    elif "wkday" in info:
        print(f"WEEK {n}  wkday={info['wkday']}  [{label}]")
    else:
        print(f"WEEK {n}  [{label}]")
    print()

    print(f"  subsection      : {subsection}")
    print(f"  label           : {label}")

    slug_mark = "✓" if info["slug_exists"] else "✗ MISSING"
    print(f"  lit_epoch_slug  : {info['epoch_slug']}  [{slug_mark}]")

    if hr:
        print(f"  heading text    : {hr['text']}")
        print(f"  heading page    : {hr['printed_page']}")
        print(f"  heading Y       : {hr['y']:.0f}")
    else:
        print(f"  heading text    : ✗ NOT FOUND IN GRADUALE_TOC  (expected: {info['heading_expected']})")

    if info["span_start"] is not None and info["span_end"] is not None:
        print(f"  printed span    : [{info['span_start']} … {info['span_end']}]")
    else:
        print(f"  printed span    : ✗ CANNOT COMPUTE (missing heading or next-heading row)")

    if nhr:
        print(f"  next heading    : {nhr['text']}")
        print(f"    boundary page : {nhr['printed_page']}  (DO NOT cross)")
        print(f"    boundary Y    : {nhr['y']:.0f}")
        print(f"    NOTE: trailing options for {unit} may spill onto p{nhr['printed_page']} ABOVE Y={nhr['y']:.0f}")
    else:
        print(f"  next heading    : ✗ NONE ({unit} may be the last entry in the section)")

    if hr:
        print(f"  NOTE: the previous {unit_noun}'s tail sits ABOVE Y={hr['y']:.0f} on p{hr['printed_page']} — EXCLUDE it")

    if info["pdf_path"]:
        pdf_rel = info["pdf_path"].relative_to(SCRIPT_DIR.parent)
        print(f"  split PDF       : {pdf_rel.as_posix()}  [✓ EXISTS]")
    elif info["season"] == "sanctorale":
        print(f"  split PDF       : ✗ MISSING — expected "
              f"graduale/3/<N>_<month>/0_<month>.pdf")
    else:
        want = slugify(info["heading_expected"]) + ".pdf"
        if info["season"] == "lent":
            print(f"  split PDF       : ✗ MISSING — no file matching *_{want} "
                  f"under {(GRADUALE_ROOT / LENT_PDF_DIR).as_posix()}/<week-folder>/")
        else:
            pdf_dir = GRADUALE_ROOT / SEASONS[info["season"]]["pdf_dir"]
            print(f"  split PDF       : ✗ MISSING — no file matching *_{want} in {pdf_dir.as_posix()}")

    for line in info.get("extra_lines", ()):
        print(f"  {line}")

    print(f"  status          : {'OK' if ok else '✗ ONE OR MORE CHECKS FAILED'}")
    print()

    # --- Paste-ready producer-brief block ---
    print("  --- PRODUCER BRIEF ANCHOR ---")
    if hr and nhr and info["pdf_path"] and info["slug_exists"]:
        pdf_rel = info["pdf_path"].relative_to(SCRIPT_DIR.parent)
        brief_lines = [
            f"subsection: {subsection}",
            f"label: {label}",
            f"lit_epoch_slug: {info['epoch_slug']}",
            f"heading: {hr['text']}",
            f"heading_printed_page: {hr['printed_page']}",
            f"heading_y: {hr['y']:.0f}",
            f"printed_span: [{info['span_start']} … {info['span_end']}]",
            f"next_heading: {nhr['text']}",
            f"next_heading_printed_page: {nhr['printed_page']}",
            f"next_heading_y: {nhr['y']:.0f}",
            f"boundary_note: Trailing options for this week may spill onto p{nhr['printed_page']} ABOVE Y={nhr['y']:.0f}; previous week tail sits ABOVE Y={hr['y']:.0f} on p{hr['printed_page']} — exclude it.",
            f"split_pdf: {pdf_rel.as_posix()}",
        ]
        brief_lines.extend(info.get("extra_lines", ()))
        for line in brief_lines:
            print(f"  {line}")
    else:
        print("  [INCOMPLETE — fix missing items above before handing to producer]")
    print()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def parse_weeks(args: list[str], valid: range) -> list[int]:
    """Parse ['2', '3', '2-6'] into sorted unique ints, validated against `valid`."""
    weeks = []
    for arg in args:
        if "-" in arg and not arg.lstrip("-").isdigit():
            lo, hi = (int(x) for x in arg.split("-", 1))
            weeks.extend(range(lo, hi + 1))
        else:
            weeks.append(int(arg))
    result = []
    for w in sorted(set(weeks)):
        if w not in valid:
            print(f"WARNING: week {w} is out of range for this season "
                  f"({valid.start}..{valid.stop - 1}) — skipping", file=sys.stderr)
            continue
        result.append(w)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve GR week formularies to producer-brief anchor blocks."
    )
    parser.add_argument(
        "--season", "-s", choices=sorted(SEASONS) + ["lent", "sanctorale"], default="ot",
        help="Liturgical season (default: ot). 'sanctorale' takes --date, not --week.",
    )
    parser.add_argument(
        "--week", "-w", nargs="+", metavar="N",
        help="One or more week numbers, or ranges like 2-6. (Not for --season sanctorale.)",
    )
    parser.add_argument(
        "--date", "-d", nargs="+", metavar="M-D",
        help="Sanctorale only: calendar dates like 8-20, aug-20, \"August 20\".",
    )
    args = parser.parse_args()

    if args.season == "sanctorale":
        if not args.date:
            parser.error("--season sanctorale requires --date (e.g. --date 8-20)")
    elif not args.week:
        parser.error("--week is required for this season")

    eng = _engine()
    any_failed = False

    if args.season == "sanctorale":
        dates = parse_dates(args.date)
        if not dates:
            print("ERROR: no valid dates provided.", file=sys.stderr)
            return 1
        try:
            import fitz
        except ImportError:
            print("ERROR: PyMuPDF (fitz) is required for --season sanctorale.",
                  file=sys.stderr)
            return 1
        if not SANCTORALE_HEADINGS.is_file():
            print(f"ERROR: {SANCTORALE_HEADINGS} not found.", file=sys.stderr)
            return 1
        entries = _load_sanctorale_headings()
        doc = fitz.open(SANCTORALE_PDF) if SANCTORALE_PDF.is_file() else None
        if doc is None:
            print(f"ERROR: {SANCTORALE_PDF} not found.", file=sys.stderr)
            return 1
        with eng.connect() as conn:
            for mon, day in dates:
                infos, date_ok = resolve_sanctorale_date(mon, day, entries, conn, doc)
                any_failed = any_failed or not date_ok
                for info in infos:
                    print_anchor(info, info["ok"])
        return 1 if any_failed else 0

    if args.season == "lent":
        weeks = parse_weeks(args.week, LENT_WEEKS)
        if not weeks:
            print("ERROR: no valid week numbers provided.", file=sys.stderr)
            return 1
        with eng.connect() as conn:
            all_rows = fetch_all_toc_rows(conn)
            for n in weeks:
                infos, week_ok = resolve_lent_week(n, all_rows, conn)
                any_failed = any_failed or not week_ok
                for info in infos:
                    print_anchor(info, info["ok"])
        return 1 if any_failed else 0

    cfg = SEASONS[args.season]
    weeks = parse_weeks(args.week, cfg["weeks"])
    if not weeks:
        print("ERROR: no valid week numbers provided.", file=sys.stderr)
        return 1

    with eng.connect() as conn:
        toc_rows = fetch_toc_rows(conn)
        for n in weeks:
            info, ok = resolve_week(n, args.season, toc_rows, conn)
            any_failed = any_failed or not ok
            print_anchor(info, ok)

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
