#!/usr/bin/env python
"""show_row.py — everything an index-rows agent needs about ONE OCO chant_indices row.

    python oco/show_row.py <row_id>

Prints: the row and its same-incipit siblings; the engravings on its page that start with the
incipit (full text from the white text layer, printed refs, CAO); gregobase candidates (cited
editions + CAO + full-text match over all editions) with their chant_group and the opening of the
gabc; the book_toc heading in force on the page; and the LPS slots its codes map to (or why not).
Read-only.
"""
import os
import re
import sys

import fitz
from sqlalchemy import text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from _db import engine  # noqa: E402
from index_util import SECTION_TO_OFFICE_PART, condense  # noqa: E402
from oco_sigla import load_saints, targets  # noqa: E402
from resolve_oco_index import engravings, incipit_test, lyrics  # noqa: E402
import oco_pages  # noqa: E402


def main():
    rid = int(sys.argv[1])
    doc = fitz.open(os.path.join(HERE, "oco.pdf"))
    with engine().connect() as c:
        r = c.execute(text("SELECT * FROM chant_indices WHERE row_id=:i"), {"i": rid}).mappings().first()
        print("ROW", {k: r[k] for k in ("row_id", "id", "section_type", "incipit", "page", "day_code",
                                         "hour_code", "place_code", "notes", "chant_uuid", "chant_group_id",
                                         "match_status")})
        for s in c.execute(text("SELECT row_id, id, page, day_code, hour_code, place_code, chant_uuid, chant_group_id, "
                                "match_status FROM chant_indices WHERE book='OCO' AND incipit=:t AND row_id<>:i"),
                           {"t": r["incipit"], "i": rid}):
            print("  sibling", dict(s._mapping))
        saints = load_saints(c)
        row = c.execute(text("SELECT page, section_type, day_code, hour_code, place_code FROM chant_indices WHERE row_id=:i"),
                        {"i": rid}).first()
        ts, why = targets(row, saints)
        print("LPS TARGETS:", why or "")
        for t in ts:
            print("  ", t)
        cf = os.path.join(HERE, "lps_conflicts.txt")
        for line in (open(cf, encoding="utf-8") if os.path.exists(cf) else []):
            if line.split("'")[0].strip().endswith(f"#{r['id']}"):
                print("HELD CONFLICT:", line.strip())
        gid = (r["chant_uuid"] or "").removeprefix("gregobase:")
        if r["page"] is None and r["section_type"] == "hymnus" and gid:
            cited = [str(oco_pages.printed(i + 1)) for i in range(len(doc)) for ln in doc[i].get_links()
                     if re.search(rf"[?&=/]id=?{gid}\b|/{gid}\b", ln.get("uri") or "")]
            print("PAGES citing this hymn (body links):", ", ".join(dict.fromkeys(cited)) or "none")
        if r["page"] is None and r["section_type"] == "hymnus":
            print("PAGE: none — hymns are 'Name (LHym N)' cross-references; render the citing pages above")
            return
        if r["page"] is None:
            print("PAGE: none (broken index link) — find the engraving; vigil-canticle sets are in the Appendix pp1179–1200")
            return
        p = int(r["page"])
        toc = c.execute(text("SELECT level, text, printed_page FROM book_toc WHERE book='OCO' AND "
                             "CAST(printed_page AS UNSIGNED) <= :p ORDER BY idx DESC LIMIT 3"), {"p": p}).all()
        print("TOC in force:", " | ".join(f"L{t.level} {t.text} p{t.printed_page}" for t in reversed(toc)))
        print(f"RENDER: python tools/render_page.py --book OCO {p}")
        test = incipit_test(r["incipit"])
        engr = [e for q in (p, p + 1) for e in engravings(doc, q) if test(e[0])]
        print(f"ENGRAVINGS starting with the incipit on p{p}/p{p + 1}: {len(engr)}")
        op = SECTION_TO_OFFICE_PART.get(r["section_type"])
        for full, refs, cao in engr:
            print(f"  TEXT: {full}\n  REFS: {refs}  CAO {cao}")
            key = condense(full).replace("oe", "ae")
            cands = c.execute(text(
                "SELECT g.id, g.incipit, g.mode, g.version, g.cantusid, m.chant_group_id grp, g.gabc FROM gregobase_chants g "
                "LEFT JOIN gregobase_chant_group_map m ON m.gregobase_id=g.id WHERE g.`office-part`=:op "
                "AND g.duplicateof IS NULL AND g.incipit LIKE :w"),
                {"op": op, "w": " ".join(re.findall(r"\w+", r["incipit"])[:1]) + "%"}).all()
            for g in cands:
                ly = lyrics(g.gabc).replace("oe", "ae")
                n = min(len(ly), len(key))
                same = n >= 12 and ly[:n] == key[:n]
                cited = [s for (s,) in c.execute(text("SELECT CONCAT(source,':',page) FROM gregobase_chant_sources "
                                                      "WHERE chant_id=:i"), {"i": g.id})]
                if same or (cao and g.cantusid == cao.zfill(6)):
                    body = (g.gabc or "").split("%%", 1)[-1].strip()[:160].replace("\n", " ")
                    print(f"    cand gregobase:{g.id} grp {g.grp} m{g.mode} {g.version or ''} '{g.incipit}' "
                          f"text={'=' if same else '≠'} cantus={g.cantusid} sources={cited}\n      {body}")


if __name__ == "__main__":
    main()
