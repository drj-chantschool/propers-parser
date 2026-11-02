#!/usr/bin/env python
"""resolve_oco_index.py — deterministic first pass linking OCO chant_indices rows to gregobase.

OCO has no gregobase edition (tools/resolve_index.py needs one), but every engraving in it is
preceded by its full text, printed in white (invisible), and usually a reference line, e.g.
    Annuntiate populis et dicite: Ecce Deus salvator noster veniet.
    cf. Ier 31,10; Is 12,2; CAO 1428; ARII 3
The references name editions gregobase does have, at a page:
    AM → 7 (Antiphonale Monasticum 1934), ARII → 6 (Antiphonale Romanum II 2009),
    PM → 24 (Psalterium Monasticum 1981), RM → 56 (Liber Responsorialis 1895), AR → 9 (AR 1912)
(measured 2026-10-20: incipit hits per siglum/source over all 2266 reference lines), and
CAO nnnn is gregobase_chants.cantusid '00nnnn'.

Rule (auto-link ONLY this case; everything else → agent queue):
  1. exactly ONE engraving on the row's page (the index link target) whose full text starts with
     the row's incipit (text before '...', without a trailing setting number, must prefix it; text
     after '...' must occur in it);
  2. the gregobase chants reachable from that engraving's references — on a cited (source, page),
     or with cantusid = its CAO number — filtered to the row's office-part, incipit prefix and
     duplicateof IS NULL, are exactly ONE chant;
  3. that chant belongs to a chant_group;
  4. its GABC lyrics and the engraving's full text agree exactly over their common length (a
     short incipit prefix-matches different chants: 'Quaerite Dominum' et vivet / dum inveniri);
  5. the incipit carries no setting number ('Ecce Agnus Dei 1' / '2': same text, two melodies).
Rule B (invitatories): the index prints 'LHym N', the Liber Hymnarius page of the invitatory; the
curated LIBER_HYMNARIUS chant_indices rows on page N give exactly one chant_uuid whose incipit
prefix-matches (setting numbers and '- cum alleluia' variants excluded) → that link, with the LH
row's own match_status ('reviewed' → 'resolved').
Writes chant_uuid + match_status only where match_status IS NULL and chant_uuid IS NULL.

    python oco/resolve_oco_index.py [--commit] [--units-file oco/queues/index-rows.units] [--report F]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

import fitz
from sqlalchemy import bindparam, text

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from _db import engine  # noqa: E402
from index_util import SECTION_TO_OFFICE_PART, condense, prefix_match  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oco_pages  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SIGLUM_SOURCE = {"AM": 7, "ARII": 6, "PM": 24, "RM": 56, "AR": 9}
REF_LINE = re.compile(r"\bCAO\s+\d|\b(?:AM|ARII|PM|RM|AR)\s+\d")
REF = re.compile(r"\b([A-Z][A-Za-z]{1,4})\s+(\d+(?:\s*(?:,|&)\s*\d+)*)")


def engravings(doc, page):
    """[(full_text, {source_id: [pages]}, cao or None)] for one PRINTED page (oco_pages maps it to the PDF).

    Each engraving's full text is printed in WHITE (invisible, searchable) just above the staff;
    the visible reference line, when there is one, follows it before the staff."""
    pg = oco_pages.page(doc, page)
    if pg is None:
        return []
    lines = []  # (white?, text) in reading order
    for b in pg.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            spans = [sp for sp in ln["spans"] if sp["text"].strip()]
            if spans:  # an invitatory's white line ends in a visible 'LHym N'
                white = spans[0]["color"] == 0xFFFFFF
                lines.append((white, " ".join(sp["text"].strip() for sp in spans
                                             if (sp["color"] == 0xFFFFFF) == white)))
    out = []
    for j, (white, line) in enumerate(lines):
        if not white or (j and lines[j - 1][0]):
            continue  # not white, or the wrapped tail of the previous white line
        full = line
        k = j + 1
        while k < len(lines) and lines[k][0]:
            full += " " + lines[k][1]
            k += 1
        refs, cao = defaultdict(list), None
        if k < len(lines) and REF_LINE.search(lines[k][1]):
            for m in REF.finditer(lines[k][1]):
                nums = re.findall(r"\d+", m.group(2))
                if m.group(1) == "CAO":
                    cao = nums[0]
                elif m.group(1) in SIGLUM_SOURCE:
                    refs[SIGLUM_SOURCE[m.group(1)]] += nums
        out.append((full, dict(refs), cao))
    return out


def lyrics(gabc):
    """Condensed sung text of a GABC (no header, neumes, <sp>/<v> markup, *, |)."""
    body = (gabc or "").split("%%", 1)[-1]
    body = re.sub(r"<(sp|v|nlba|alt)>.*?</\1>", "", body)
    body = re.sub(r"\([^)]*\)|<[^>]+>|[{}*|]", "", body)
    return condense(body)


def same_text(full, gabc):
    a, b = condense(full), lyrics(gabc)
    n = min(len(a), len(b))
    return n >= 8 and a[:n] == b[:n]


def incipit_test(incipit):
    """Index incipit → predicate on an engraving's full text."""
    head, _, tail = incipit.partition("...")
    head = re.sub(r"\s+\d+$", "", head.strip())  # 'Surrexit Dominus 2' = second setting
    h, t = condense(head), condense(tail)
    return lambda full: bool(h) and condense(full).startswith(h) and (not t or t in condense(full))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--units-file")
    ap.add_argument("--report", default=os.path.join(HERE, "index_resolve_report.txt"))
    a = ap.parse_args()
    doc = fitz.open(os.path.join(HERE, "oco.pdf"))
    eng = engine(rw=a.commit)
    resolved, left, lines = [], [], []
    page_cache = {}
    with (eng.begin() if a.commit else eng.connect()) as c:
        todo = c.execute(text("SELECT row_id, id, section_type, incipit, page, notes FROM chant_indices "
                              "WHERE book='OCO' AND match_status IS NULL AND chant_uuid IS NULL ORDER BY id")).all()
        for r in todo:
            op = SECTION_TO_OFFICE_PART.get(r.section_type)
            why, g, status = None, None, "resolved"
            lh = re.search(r"LHym (\d+)", r.notes or "")
            if r.section_type == "invitatorium" and lh:
                if re.search(r"\s\d+$", r.incipit) or "cum alleluia" in (r.notes or ""):
                    why = "numbered setting / cum alleluia variant"
                else:
                    hits = {(x.chant_uuid, x.match_status) for x in c.execute(text(
                        "SELECT incipit, chant_uuid, match_status FROM chant_indices WHERE book='LIBER_HYMNARIUS' "
                        "AND page=:p AND section_type='invitatorium' AND chant_uuid IS NOT NULL"), {"p": lh.group(1)})
                        if prefix_match(x.incipit, r.incipit)}
                    if len({u for u, _ in hits}) != 1:
                        why = f"{len(hits)} LH invitatory links on LHym p{lh.group(1)}"
                    else:
                        uuid, st = next(iter(hits))
                        g = type("G", (), {"id": uuid, "incipit": f"LH p{lh.group(1)}"})
                        status = "resolved_with_difficulty" if st == "resolved_with_difficulty" else "resolved"
            elif r.page is None:
                why = "no page (broken index link)"
            elif re.search(r"\b[a-z]\.\s", r.incipit):
                why = "abbreviated incipit"
            elif re.search(r"\s\d+$", r.incipit.partition("...")[0].strip()):
                why = "numbered setting"
            else:
                p = int(r.page)
                if p not in page_cache:
                    page_cache[p] = engravings(doc, p)
                test = incipit_test(r.incipit)
                hits = [e for e in page_cache[p] if test(e[0])]
                if len(hits) != 1:
                    why = f"{len(hits)} engravings on p{p} start with the incipit"
                else:
                    full, refs, cao = hits[0]
                    cands = {}
                    for src, pages in refs.items():
                        for row in c.execute(text(
                                "SELECT g.id, g.incipit, g.gabc, m.chant_group_id FROM gregobase_chant_sources s "
                                "JOIN gregobase_chants g ON g.id=s.chant_id "
                                "LEFT JOIN chants m ON m.origin_source = 'GREGOBASE' AND m.origin_id = CAST(g.id AS CHAR) "
                                "WHERE s.source=:s AND s.page IN :pp AND g.`office-part`=:op "
                                "AND g.duplicateof IS NULL").bindparams(
                                    bindparam("pp", expanding=True)),
                                {"s": src, "pp": [str(x) for x in pages], "op": op}):
                            if prefix_match(row.incipit, full):
                                cands[row.id] = row
                    if cao:
                        for row in c.execute(text(
                                "SELECT g.id, g.incipit, g.gabc, m.chant_group_id FROM gregobase_chants g "
                                "LEFT JOIN chants m ON m.origin_source = 'GREGOBASE' AND m.origin_id = CAST(g.id AS CHAR) "
                                "WHERE g.cantusid=:k AND g.`office-part`=:op AND g.duplicateof IS NULL"),
                                {"k": cao.zfill(6), "op": op}):
                            if prefix_match(row.incipit, full):
                                cands[row.id] = row
                    if len(cands) != 1:
                        why = f"{len(cands)} gregobase candidates from refs {refs} CAO {cao}"
                    else:
                        g = next(iter(cands.values()))
                        if g.chant_group_id is None:
                            why = f"gregobase:{g.id} is ungrouped"
                        elif not same_text(full, g.gabc):
                            why = f"gregobase:{g.id} text differs from the engraving"
            if why:
                left.append(r.row_id)
                lines.append(f"· row {r.row_id} id {r.id} p{r.page} {r.incipit!r}: {why}")
                continue
            uuid = g.id if isinstance(g.id, str) else f"gregobase:{g.id}"
            resolved.append(r.row_id)
            lines.append(f"✓ row {r.row_id} id {r.id} p{r.page} {r.incipit!r} → {uuid} {g.incipit!r} [{status}]")
            if a.commit:
                c.execute(text("UPDATE chant_indices SET chant_uuid=:u, match_status=:s "
                               "WHERE row_id=:i AND match_status IS NULL AND chant_uuid IS NULL"),
                          {"u": uuid, "s": status, "i": r.row_id})
    with open(a.report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if a.units_file:
        with open(a.units_file, "w", encoding="utf-8") as f:
            f.writelines(f"r{i}\n" for i in left)
    print(json.dumps({"commit": a.commit, "resolved": len(resolved), "for_agents": len(left),
                      "report": a.report}))


if __name__ == "__main__":
    main()
