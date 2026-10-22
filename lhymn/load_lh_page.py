#!/usr/bin/env python
"""load_lh_page.py — load ONE Liber Hymnarius page spec into lit_part_sources.

Contract: propers-parser/lhymn/specs/README.md. One spec per printed page
(specs/p0004.json). Rows land with book = assignment_authority_code = 'LIBER_HYMNARIUS',
printed_page_num = the spec page, ref_page_num = the cited page for cross-references.

    python load_lh_page.py --spec specs/p0004.json --dry-run   # resolve + show, no writes
    python load_lh_page.py --spec specs/p0004.json             # write (upsert)
    python load_lh_page.py --spec specs/p0004.json --verify    # DB == spec for this page?
    python load_lh_page.py --spec ... --prune                  # also delete stale rows of this page

Exit codes: 0 ok · 1 spec/resolve error · 3 spec carries open questions (not loaded)
            · 4 dependency missing (a cited Common has no LH rows yet) · 5 verify FAIL
The last stdout line is always a one-line JSON summary for the batch log.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

import keyring
from sqlalchemy import bindparam, create_engine, text

BOOK = AUTH = "LIBER_HYMNARIUS"
GREGOBASE_LH_SOURCE = 15
QUEUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work_queue.json")
# Printed page span of each LH Common, inclusive of the page where the next section starts
# (a Common's tail can share it). A common_ref expands only once ALL these pages are finished
# in the work queue — otherwise the copy would be silently partial.
COMMON_RANGES = {
    "COM-DED": (247, 253), "COM-BMV": (253, 263), "COM-BMV-SAB": (263, 266), "COM-APOST": (266, 273),
    "COM-MART-PLUR": (273, 280), "COM-MART-UNO": (280, 289), "COM-PAST": (289, 301),
    "COM-DOCT": (301, 305), "COM-VIRG": (305, 311), "COM-SANCT-VIR": (311, 318),
    "COM-SANCT-MULIER": (318, 324), "COM-SANCT-RELIG": (324, 328), "officium-defunctorum": (328, 336),
    "COM-MON": (537, 541),
}

# Commons whose sub-Commons partition them by subject (user ruling 2026-10-15): a saint must cite the
# sub-Common that fits (e.g. COM-VIRG-UNA), which then inherits the parent's shared rows.
PARTITIONED_COMMONS = {"COM-PAST", "COM-VIRG", "COM-SANCT-VIR", "COM-SANCT-MULIER"}


def common_unfinished(slug, exclude=None):
    """Pages of the Common not yet loaded/no_rows in the queue ([] = complete; None = unknown slug).
    `exclude` is the citing page: ranges share boundary pages, so a page that opens the next Common
    and cites this one must not wait on itself."""
    if slug not in COMMON_RANGES:
        return None
    with open(QUEUE, encoding="utf-8") as f:
        pages = json.load(f)["pages"]
    lo, hi = COMMON_RANGES[slug]
    return [p for p in range(lo, hi + 1)
            if str(p) != str(exclude)
            and pages.get(str(p), {}).get("status") not in ("loaded", "no_rows", "skipped")]


class SpecError(Exception):
    pass


class DependencyError(Exception):
    pass


def engine(user):
    pw = keyring.get_password("liturgio-mysql", user)
    return create_engine(f"mysql+mysqlconnector://{user}:{pw}@localhost:3306/liturgio", future=True)


def condense(s):
    """Lower-case, fold accents and ligatures, keep letters only (j→i, v/u kept apart)."""
    s = (s or "").replace("æ", "ae").replace("Æ", "ae").replace("œ", "oe").replace("Œ", "oe")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().replace("j", "i")
    return re.sub(r"[^a-z]", "", s)


def incipit_keys(raw):
    """Index/gregobase incipit → list of condensed fragments to prefix-match.

    Strips editorial parentheses ("Te lucis (Tempus Adventus)") and splits on ellipses
    ("Verbum supernum... a Patre" → ["verbumsupernum", "apatre"])."""
    raw = re.sub(r"\([^)]*\)", " ", raw or "")
    parts = [condense(p) for p in re.split(r"\.\.\.|…", raw)]
    return [p for p in parts if p]


def incipit_matches(spec_incipit, cand_incipit):
    s = condense(spec_incipit)
    keys = incipit_keys(cand_incipit)
    if not s or not keys:
        return False
    head = keys[0]
    if not (s.startswith(head) or head.startswith(s)):
        return False
    # later ellipsis fragments must appear somewhere after the head when the spec is long enough
    rest = s[len(head):]
    return all(k in rest for k in keys[1:]) if len(rest) >= sum(map(len, keys[1:])) else True


def norm_mode(m):
    if m is None:
        return None
    m = str(m).strip().lower()
    roman = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8"}
    base = m.rstrip("*")
    return roman.get(base, base) + m[len(base):]


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    for k in ("page", "page_kind"):
        if k not in spec:
            raise SpecError(f"spec missing '{k}'")
    spec["page"] = str(spec["page"])
    spec.setdefault("rows", [])
    spec.setdefault("common_refs", [])
    spec.setdefault("questions", [])
    spec.setdefault("jurisdiction", "UNIVERSAL")
    if spec["page_kind"] not in ("assign", "continuation_only", "no_chant"):
        raise SpecError(f"page_kind must be assign|continuation_only|no_chant, got {spec['page_kind']!r}")
    if spec["page_kind"] != "assign" and (spec["rows"] or spec["common_refs"]):
        raise SpecError(f"page_kind={spec['page_kind']} but rows/common_refs are present")
    return spec


class Resolver:
    def __init__(self, c):
        self.c = c
        self.parts = {(r.service_code, r.part_code): r.part_id for r in
                      c.execute(text("SELECT part_id, service_code, part_code FROM service_part"))}
        self.ranks = {r[0] for r in c.execute(text("SELECT rank_code FROM p_lit_rank"))}
        self.jur = {r[0] for r in c.execute(text("SELECT jurisdiction_code FROM p_jurisdiction"))}
        self._epoch = {}

    def epoch_title(self, slug):
        if slug is None:
            return "Psalter (per annum)"
        if slug not in self._epoch:
            r = self.c.execute(text("SELECT title FROM lit_epoch WHERE slug=:s"), {"s": slug}).first()
            if not r:
                raise SpecError(f"lit_epoch slug {slug!r} does not exist")
            self._epoch[slug] = r[0] or slug
        return self._epoch[slug]

    def ancestors(self, slug):
        """[slug, parent, grandparent, ...] via lit_epoch_tree."""
        chain = [slug]
        while True:
            r = self.c.execute(text("SELECT parent_slug FROM lit_epoch_tree WHERE child_slug=:s"),
                               {"s": chain[-1]}).first()
            if not r or r[0] in chain:
                return chain
            chain.append(r[0])

    def descendants(self, slug):
        """Every epoch below slug (sub-Commons), depth-first."""
        out = []
        for (child,) in self.c.execute(text("SELECT child_slug FROM lit_epoch_tree WHERE parent_slug=:s "
                                            "ORDER BY child_slug"), {"s": slug}).all():
            out += [child] + self.descendants(child)
        return out

    def page_exists(self, page):
        return self.c.execute(text("SELECT 1 FROM books WHERE book=:b AND printed_page_num=:p"),
                              {"b": BOOK, "p": str(page)}).first() is not None

    def pool(self, page):
        """Candidate chants that BEGIN on `page`: LH index rows first, then gregobase LH sources."""
        out = []
        for r in self.c.execute(text(
                "SELECT row_id, section_type, mode, incipit, notes, chant_uuid, match_status FROM chant_indices "
                "WHERE book=:b AND page=:p"), {"b": BOOK, "p": str(page)}).mappings():
            mode = r["mode"]
            if mode is None and r["notes"] and "printed mode:" in r["notes"]:
                mode = r["notes"].split("printed mode:")[1].split(";")[0].strip()
            out.append({"src": "index", "id": r["row_id"], "incipit": r["incipit"], "mode": norm_mode(mode),
                        "chant_uuid": r["chant_uuid"], "status": r["match_status"], "kind": r["section_type"]})
        for r in self.c.execute(text(
                "SELECT c.id, c.incipit, c.mode, c.`office-part` AS op FROM gregobase_chant_sources s "
                "JOIN gregobase_chants c ON c.id = s.chant_id WHERE s.source=:src AND s.page=:p"),
                {"src": GREGOBASE_LH_SOURCE, "p": str(page)}).mappings():
            out.append({"src": "gregobase", "id": r["id"], "incipit": r["incipit"], "mode": norm_mode(r["mode"]),
                        "chant_uuid": f"gregobase:{r['id']}", "status": None, "kind": r["op"]})
        return out

    # office-part values gregobase uses for each LH part (None = don't check)
    OFFICE_PARTS = {"hymn": {"hy"}, "invan": {"an", "iv", "in"}, "invps": {"ps", "iv", "in"},
                    "resp": {"re", "rb"}, "resp2": {"re", "rb"}, "tedeum": None}

    def check(self, uuid, row, target):
        """Trust-but-verify the resolved chant against the spec. Returns (summary, warnings[])."""
        if not uuid or not uuid.startswith("gregobase:"):
            return None, []
        gid = int(uuid.split(":")[1])
        g = self.c.execute(text("SELECT incipit, mode, `office-part` AS op, gabc FROM gregobase_chants WHERE id=:i"),
                           {"i": gid}).mappings().first()
        if not g:
            return None, [f"⚠ CHECK {uuid} does not exist in gregobase_chants"]
        lh_pages = [r[0] for r in self.c.execute(text(
            "SELECT page FROM gregobase_chant_sources WHERE chant_id=:i AND source=:s"),
            {"i": gid, "s": GREGOBASE_LH_SOURCE})]
        words = re.sub(r"<[^>]*>|\([^)]*\)|\{|\}|\[[^\]]*\]", "", g["gabc"] or "")
        words = re.sub(r"\s+", " ", words).strip()
        warn = []
        head = condense(row["incipit"])[:14]
        if head and not condense(words).startswith(head):
            warn.append(f"⚠ CHECK {uuid}: GABC text starts {words[:50]!r}, spec incipit {row['incipit']!r}")
        pm, gm = norm_mode(row.get("mode")), norm_mode(g["mode"])
        if pm and gm and pm.rstrip("*") != gm.rstrip("*"):
            warn.append(f"⚠ CHECK {uuid}: gregobase mode {g['mode']!r} ≠ printed mode {row.get('mode')!r}")
        ops = self.OFFICE_PARTS.get(row["part"])
        if ops and (g["op"] or "") not in ops:
            warn.append(f"⚠ CHECK {uuid}: gregobase office-part {g['op']!r} unexpected for {row['part']}")
        if lh_pages and str(target) not in map(str, lh_pages):
            warn.append(f"⚠ CHECK {uuid}: gregobase ties it to LH page(s) {lh_pages}, not p{target}")
        summary = (f"{g['incipit']!r} m{g['mode']} {g['op']}, LH p{','.join(map(str, lh_pages)) or '-'}; "
                   f"text {words[:45]!r}")
        return summary, warn

    def chant(self, row, page):
        """Return (chant_uuid, how, notes[])."""
        notes = []
        if row.get("chant_uuid"):
            return row["chant_uuid"], "explicit chant_uuid", notes
        if row.get("index_row_id"):
            r = self.c.execute(text("SELECT page, incipit, chant_uuid FROM chant_indices WHERE row_id=:i AND book=:b"),
                               {"i": row["index_row_id"], "b": BOOK}).mappings().first()
            if not r:
                raise SpecError(f"index_row_id {row['index_row_id']} not an LH chant_indices row")
            if str(r["page"]) != str(page):
                notes.append(f"ℹ index row {row['index_row_id']} lists page {r['page']}, target page is {page}")
            if r["chant_uuid"] is None and not row.get("allow_unresolved"):
                raise SpecError(f"index row {row['index_row_id']} has no chant_uuid (set allow_unresolved)")
            return r["chant_uuid"], f"index row {row['index_row_id']}", notes
        target = row.get("ref_page") or page
        cands = [c for c in self.pool(target) if incipit_matches(row["incipit"], c["incipit"])]
        mode = norm_mode(row.get("mode"))
        if mode and len({c["chant_uuid"] for c in cands}) > 1:
            m = [c for c in cands if c["mode"] == mode]
            if m:
                cands = m
        uuids = {c["chant_uuid"] for c in cands if c["chant_uuid"]}
        if len(uuids) == 1:
            u = uuids.pop()
            c = next(c for c in cands if c["chant_uuid"] == u)
            if c["src"] == "index" and c["status"] in ("resolved_with_difficulty", "ambiguous", "reviewed"):
                notes.append(f"ℹ index row {c['id']} match_status={c['status']}")
            return u, f"{c['src']}:{c['id']} on p{target}", notes
        if len(uuids) > 1:
            raise SpecError(f"{row['incipit']!r} on p{target}: ambiguous {sorted(uuids)} — give mode or index_row_id")
        if row.get("allow_unresolved"):
            notes.append(f"⚠ unresolved chant {row['incipit']!r} on p{target} (allow_unresolved)")
            return None, "unresolved", notes
        hint = []
        for p in (int(target) - 1, int(target) + 1) if str(target).isdigit() else ():
            hint += [f"p{p}:{c['src']}:{c['id']} {c['incipit']!r}" for c in self.pool(p)
                     if incipit_matches(row["incipit"], c["incipit"])]
        pool = [f"{c['src']}:{c['id']} {c['incipit']!r} m{c['mode']}" for c in self.pool(target)]
        raise SpecError(f"no chant for {row['incipit']!r} on p{target}. pool={pool}"
                        + (f"; neighbouring pages: {hint}" if hint else ""))


def expand(row):
    wkdays = row.get("wkdays") or [row.get("wkday")]
    ranks = row.get("rank_codes") or [row.get("rank_code")]
    for w in wkdays:
        for r in ranks:
            yield w, r


def build_rows(spec, res):
    """Return (rows, notes). Each row is a dict of lit_part_sources column values."""
    page, jur = spec["page"], spec["jurisdiction"]
    if not res.page_exists(page):
        raise SpecError(f"books has no LH page {page}")
    if jur not in res.jur:
        raise SpecError(f"unknown jurisdiction {jur}")
    out, notes = [], []
    check_warnings = spec.setdefault("_check_warnings", [])
    for i, r in enumerate(spec["rows"], start=1):
        for k in ("incipit", "service", "part", "kind"):
            if k not in r:
                raise SpecError(f"row {i} missing '{k}'")
        if r["kind"] not in ("engraved", "xref"):
            raise SpecError(f"row {i}: kind must be engraved|xref")
        if r["kind"] == "xref" and not r.get("ref_page"):
            raise SpecError(f"row {i}: xref needs ref_page")
        if r["kind"] == "engraved" and r.get("ref_page"):
            raise SpecError(f"row {i}: engraved row must not carry ref_page")
        # ref_book: a cross-book cue (e.g. "Vel R. Emendemus, in Graduale"): ref_page is a page of that book.
        # The LH index can't resolve it, so the chant must be explicit. intake_queue #4, 2026-10-18.
        if r.get("ref_book"):
            if r["kind"] != "xref":
                raise SpecError(f"row {i}: ref_book only on xref rows")
            if not r.get("chant_uuid"):
                raise SpecError(f"row {i}: ref_book row needs an explicit chant_uuid")
            if not res.c.execute(text("SELECT 1 FROM books WHERE book=:b AND printed_page_num=:p"),
                                 {"b": r["ref_book"], "p": str(r["ref_page"])}).first():
                raise SpecError(f"row {i}: no books row {r['ref_book']} p{r['ref_page']}")
        pid = res.parts.get((r["service"], r["part"]))
        if pid is None:
            raise SpecError(f"row {i}: no service_part {r['service']}.{r['part']}")
        slugs = r.get("lit_epoch_slugs") or [r.get("lit_epoch_slug")]
        for slug in slugs:
            res.epoch_title(slug)
        slug = slugs[0]
        # "universal": true = a rank-only row with no epoch: any day of that rank, whatever the
        # season (e.g. the Te Deum "in sollemnitatibus et festis"). User ruling 2026-10-18, intake_queue #3.
        if r.get("universal"):
            if slug is not None or len(slugs) > 1:
                raise SpecError(f"row {i}: universal row must not carry lit_epoch_slug(s)")
            if not (r.get("rank_codes") or r.get("rank_code")):
                raise SpecError(f"row {i}: universal row needs rank_codes")
            if r.get("wknum_mod_2") is not None or r.get("wknum_mod_4") is not None or r.get("psalter_all_weeks"):
                raise SpecError(f"row {i}: universal row must not carry psalter fields")
        elif slug is None and not (r.get("wknum_mod_2") is not None or r.get("wknum_mod_4") is not None
                                   or r.get("psalter_all_weeks")):
            raise SpecError(f"row {i}: lit_epoch_slug null needs wknum_mod_2/4 or psalter_all_weeks:true "
                            "(or universal:true with rank_codes)")
        uuid, how, n = res.chant(r, page)
        notes += [f"row {i}: {x}" for x in n]
        summ, warn = res.check(uuid, r, page if r.get("ref_book") else (r.get("ref_page") or page))
        if summ:
            notes.append(f"row {i}: ✓? {uuid} = {summ}")
        acked = set(r.get("verified_despite", []))
        for w in warn:
            kind = w.split(": ", 1)[1].split(" ")[1] if ": " in w else ""
            notes.append(f"row {i}: {w}" + ("  [acknowledged in spec]" if any(a in w for a in acked) else ""))
            if not any(a in w for a in acked):
                check_warnings.append(f"row {i}")
        note = " | ".join(x for x in (r.get("rubric"), r.get("notes")) if x) or None
        for slug, wk, rk in ((sl, w, k) for sl in slugs for (w, k) in expand(r)):
            title = res.epoch_title(slug)
            if rk is not None and rk not in res.ranks:
                raise SpecError(f"row {i}: unknown rank_code {rk}")
            out.append(dict(
                src=f"row {i}", how=how, incipit=r["incipit"], lit_epoch_slug=slug, part_id=pid,
                svc=f"{r['service']}.{r['part']}", wkday=wk, wknum_mod_2=r.get("wknum_mod_2"),
                wknum_mod_4=r.get("wknum_mod_4"), rank_code=rk, cycle_sun=r.get("cycle_sun"),
                cycle_wkday=r.get("cycle_wkday"),
                option_num=None if r.get("after_common") else r.get("option_num", 1),
                _order=(10 ** 6, i), _after_common=bool(r.get("after_common")),
                option_txt=r.get("option_txt"), chant_uuid=uuid, jurisdiction=r.get("jurisdiction", jur),
                printed_page_num=page, ref_page_num=r.get("ref_page"), ref_book=r.get("ref_book"), notes=(note or "")[:500] or None,
                display_name=f"{title} — {r['service']}.{r['part']} — {r['incipit']}"[:300]))
    # Common references: copy the cited Common's LH rows as cross-references.
    # Rows marked after_common (an 'ad libitum' proper) don't displace the Common's row for that slot.
    filled = {(x["lit_epoch_slug"], x["part_id"], x["wkday"], x["rank_code"]) for x in out
              if not x.get("_after_common")}
    for j, cr in enumerate(spec["common_refs"], start=1):
        for k in ("lit_epoch_slug", "common_slug", "common_page"):
            if k not in cr:
                raise SpecError(f"common_ref {j} missing '{k}'")
        title = res.epoch_title(cr["lit_epoch_slug"])
        res.epoch_title(cr["common_slug"])
        # A sub-Common (e.g. COM-VIRG-UNA) inherits its ancestors' shared rows. Sub-Commons are NOT
        # pulled in from a parent: a Common split by subject must be cited at the right sub-Common.
        if cr["common_slug"] in PARTITIONED_COMMONS:
            raise SpecError(f"common_ref {j}: {cr['common_slug']} is split by subject; cite a sub-Common "
                            f"({', '.join(res.descendants(cr['common_slug']))})")
        chain = res.ancestors(cr["common_slug"])
        below = []
        src = res.c.execute(text(
            "SELECT l.*, sp.service_code, sp.part_code FROM lit_part_sources l JOIN service_part sp USING (part_id) "
            "WHERE l.book=:b AND l.lit_epoch_slug IN :s AND l.jurisdiction IN (:j,'UNIVERSAL') "
            "ORDER BY sp.display_order, l.wkday, l.option_num, l.text_id").bindparams(bindparam("s", expanding=True)),
            {"b": BOOK, "s": chain + below, "j": jur}).mappings().all()
        ranged = next((s for s in chain if s in COMMON_RANGES), None)
        todo = common_unfinished(ranged, exclude=page) if ranged else None
        if todo is None:
            raise SpecError(f"common_ref {j}: {cr['common_slug']} has no page range in COMMON_RANGES "
                            f"(neither it nor an ancestor)")
        if todo:
            raise DependencyError(f"common_ref {j}: {ranged} not fully loaded; pages pending {todo}")
        if not src:
            raise DependencyError(f"common_ref {j}: {cr['common_slug']} has no LH rows loaded yet")
        lo, hi = cr.get("common_page_range", [None, None]) if cr.get("common_page_range") else (None, None)
        for s in src:
            if lo and not (lo <= int(s["printed_page_num"]) <= hi):
                continue
            key = (cr["lit_epoch_slug"], s["part_id"], s["wkday"], s["rank_code"])
            if key in filled and cr.get("skip_filled", True):
                continue
            # Slots the saint fills with propers printed on OTHER pages ("praeter sequentia" spanning pages).
            if f"{s['service_code']}.{s['part_code']}" in cr.get("skip_slots", []):
                continue
            out.append(dict(
                src=f"common {j}", how=f"from {cr['common_slug']} text_id {s['text_id']}",
                incipit=(s["display_name"] or "").split(" — ")[-1], lit_epoch_slug=cr["lit_epoch_slug"],
                part_id=s["part_id"], svc=f"{s['service_code']}.{s['part_code']}", wkday=s["wkday"],
                wknum_mod_2=s["wknum_mod_2"], wknum_mod_4=s["wknum_mod_4"], rank_code=s["rank_code"],
                cycle_sun=s["cycle_sun"], cycle_wkday=s["cycle_wkday"], option_num=None,
                _order=(cr.get("ref_option", j), s["option_num"]),
                option_txt=(cr.get("option_txt") or s["option_txt"]
                            or (res.epoch_title(s["lit_epoch_slug"]) if s["lit_epoch_slug"] in below else None)),
                chant_uuid=s["chant_uuid"], jurisdiction=jur, printed_page_num=page,
                ref_page_num=s["ref_page_num"] or int(s["printed_page_num"]), ref_book=None,
                notes=(" | ".join(x for x in (cr.get("rubric"), s["option_txt"] and f"common option: {s['option_txt']}") if x) or None),
                display_name=f"{title} — {s['service_code']}.{s['part_code']} — "
                             f"{(s['display_name'] or '').split(' — ')[-1]}"[:300]))
    # Number common-derived options per slot after any explicit options in that slot.
    slots = {}
    for x in out:
        k = (x["lit_epoch_slug"], x["part_id"], x["wkday"], x["rank_code"], x["wknum_mod_2"], x["wknum_mod_4"])
        slots.setdefault(k, []).append(x)
    for k, xs in slots.items():
        explicit = [x["option_num"] for x in xs if x["option_num"] is not None]
        if any(x.get("_after_common") for x in xs):
            # An ad-libitum proper whose common_ref was loaded from another page: number it after the
            # options other pages already put in this slot (the Common's copied hymn).
            x0 = xs[0]
            r = res.c.execute(text(
                "SELECT MAX(option_num) FROM lit_part_sources WHERE book=:b AND translation_source_code IS NULL "
                "AND jurisdiction=:j AND lit_epoch_slug<=>:e AND part_id=:pid AND wkday<=>:w AND rank_code<=>:rk "
                "AND wknum_mod_2<=>:m2 AND wknum_mod_4<=>:m4 AND printed_page_num<>:pg"),
                {"b": BOOK, "j": x0["jurisdiction"], "e": k[0], "pid": k[1], "w": k[2], "rk": k[3],
                 "m2": k[4], "m4": k[5], "pg": page}).scalar()
            explicit.append(r or 0)
        nxt = max(explicit, default=0) + 1
        for x in sorted((x for x in xs if x["option_num"] is None), key=lambda x: x["_order"]):
            x["option_num"] = nxt
            nxt += 1
    # duplicate-slot guard
    seen = {}
    for x in out:
        k = (x["jurisdiction"], x["lit_epoch_slug"], x["part_id"], x["wkday"], x["rank_code"], x["wknum_mod_2"],
             x["wknum_mod_4"], x["cycle_sun"], x["cycle_wkday"], x["option_num"])
        if k in seen:
            raise SpecError(f"{x['src']} and {seen[k]} occupy the same slot/option {k} — set option_num")
        seen[k] = x["src"]
    return out, notes


SLOT_COLS = ("jurisdiction", "lit_epoch_slug", "part_id", "wkday", "wknum_mod_2", "wknum_mod_4", "rank_code",
             "cycle_sun", "cycle_wkday", "option_num")
WRITE_COLS = SLOT_COLS + ("chant_uuid", "printed_page_num", "ref_page_num", "ref_book", "option_txt", "notes", "display_name")


def find_existing(c, x):
    where = " AND ".join(f"{k} <=> :{k}" for k in SLOT_COLS)
    return c.execute(text(f"SELECT text_id, chant_uuid, printed_page_num FROM lit_part_sources "
                          f"WHERE book=:book AND translation_source_code IS NULL AND {where}"),
                     {**{k: x[k] for k in SLOT_COLS}, "book": BOOK}).mappings().all()


def page_rows(c, page):
    return c.execute(text("SELECT text_id, lit_epoch_slug, part_id, wkday, rank_code, option_num, chant_uuid "
                          "FROM lit_part_sources WHERE book=:b AND printed_page_num=:p"),
                     {"b": BOOK, "p": page}).mappings().all()


def fmt(x):
    day = "".join(f" {k}={x[k]}" for k in ("wkday", "wknum_mod_2", "wknum_mod_4", "rank_code", "cycle_sun")
                  if x[k] is not None)
    ref = (f" xref→{x['ref_book'] + ' ' if x.get('ref_book') else ''}p{x['ref_page_num']}"
           if x["ref_page_num"] else " engraved")
    return (f"  [{x['src']}] {x['lit_epoch_slug'] or ('PSALTER' if x['wknum_mod_2'] is not None or x['wknum_mod_4'] is not None else 'ANY')} {x['svc']} opt{x['option_num']}{day}{ref} "
            f"{x['incipit']!r} -> {x['chant_uuid'] or 'NULL'} ({x['how']})"
            + (f" [{x['option_txt']}]" if x["option_txt"] else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    ap.add_argument("--prune", action="store_true", help="delete this page's LH rows not in the spec")
    a = ap.parse_args()
    summary = {"spec": os.path.basename(a.spec), "mode": "verify" if a.verify else "dry-run" if a.dry_run else "load"}
    try:
        spec = load_spec(a.spec)
        summary.update(page=spec["page"], page_kind=spec["page_kind"])
        ro = engine("liturgio_ro")
        with ro.connect() as c:
            res = Resolver(c)
            rows, notes = build_rows(spec, res)
            for x in rows:
                print(fmt(x))
            for n in notes:
                print(n)
            existing_page = page_rows(c, spec["page"])
            matched = {}
            for x in rows:
                ex = find_existing(c, x)
                same = [e for e in ex if e["chant_uuid"] == x["chant_uuid"]]
                matched[id(x)] = same[0]["text_id"] if same else None
                if ex and not same:
                    print(f"  ⚠ slot already holds a DIFFERENT chant: {[dict(e) for e in ex]} for {x['src']}")
                    summary.setdefault("conflicts", []).append(x["src"])
        expected_ids = {v for v in matched.values() if v}
        stale = [dict(r) for r in existing_page if r["text_id"] not in expected_ids]
        summary.update(rows=len(rows), engraved=sum(1 for x in rows if not x["ref_page_num"]),
                       xref=sum(1 for x in rows if x["ref_page_num"]),
                       unresolved=sum(1 for x in rows if not x["chant_uuid"]),
                       questions=len(spec["questions"]),
                       check_warnings=len(spec["_check_warnings"]))
        if spec["questions"]:
            print("OPEN QUESTIONS (page not loadable until answered):")
            for q in spec["questions"]:
                print("  ?", q)
        if a.verify:
            missing = [x["src"] for x in rows if not matched[id(x)]]
            ok = not missing and not stale
            print(f"VERIFY {'PASS' if ok else 'FAIL'}: expected {len(rows)}, matched {len(rows) - len(missing)}, "
                  f"stale {len(stale)}" + (f", missing {missing}" if missing else ""))
            summary["verify"] = "PASS" if ok else "FAIL"
            print(json.dumps(summary, ensure_ascii=False))
            return 0 if ok else 5
        if a.dry_run:
            new = sum(1 for x in rows if not matched[id(x)])
            print(f"DRY-RUN OK: {len(rows)} rows ({new} would insert, {len(rows) - new} existing), "
                  f"{len(stale)} stale on this page")
            summary.update(would_insert=new, stale=len(stale))
            print(json.dumps(summary, ensure_ascii=False))
            return 3 if spec["questions"] else 0
        if spec["questions"]:
            print(json.dumps(summary, ensure_ascii=False))
            return 3
        if spec["_check_warnings"]:
            raise SpecError(f"unacknowledged ⚠ CHECK on {spec['_check_warnings']} — fix the chant or add a "
                            f"'verified_despite' entry to the row after confirming against the page")
        if summary.get("conflicts"):
            raise SpecError(f"slot conflicts {summary['conflicts']} — resolve before loading")
        rw = engine("jcost")
        ins = upd = 0
        with rw.begin() as c:
            for x in rows:
                vals = {k: x[k] for k in WRITE_COLS}
                if matched[id(x)]:
                    c.execute(text("UPDATE lit_part_sources SET printed_page_num=:printed_page_num, "
                                   "ref_page_num=:ref_page_num, ref_book=:ref_book, option_txt=:option_txt, notes=:notes, "
                                   "display_name=:display_name WHERE text_id=:tid"),
                              {**vals, "tid": matched[id(x)]})
                    upd += 1
                else:
                    cols = ", ".join(WRITE_COLS)
                    c.execute(text(f"INSERT INTO lit_part_sources ({cols}, book, assignment_authority_code, "
                                   f"original_lang, review_status) VALUES ("
                                   + ", ".join(f":{k}" for k in WRITE_COLS)
                                   + ", :book, :auth, 'la', 'draft')"), {**vals, "book": BOOK, "auth": AUTH})
                    ins += 1
            pruned = 0
            if a.prune and stale:
                ids = [s["text_id"] for s in stale]
                c.execute(text("DELETE FROM lit_part_sources WHERE text_id IN (" + ",".join(map(str, ids)) + ")"))
                pruned = len(ids)
        print(f"LOADED: {ins} inserted, {upd} refreshed, {pruned} pruned, {len(stale) - pruned} stale left")
        summary.update(inserted=ins, refreshed=upd, pruned=pruned, stale=len(stale) - pruned)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except DependencyError as e:
        print("DEPENDENCY:", e)
        summary["error"] = f"dependency: {e}"
        print(json.dumps(summary, ensure_ascii=False))
        return 4
    except (SpecError, json.JSONDecodeError) as e:
        print("ERROR:", e)
        summary["error"] = str(e)[:400]
        print(json.dumps(summary, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
