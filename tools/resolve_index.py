#!/usr/bin/env python
"""resolve_index.py — deterministic first pass linking chant_indices rows to gregobase, any book.

Auto-resolves ONLY the safe case (the rule that resolved 286/544 LH rows with no rework):
the book's gregobase source ties exactly one chant to the index page (±1, index page numbers are
sometimes a line/page off), and that chant's office-part, mode and incipit prefix all agree with
the row, and it belongs to a chant_group. Two guards came from checking the rule against the
curated LH links (272 agree / 3 disagree before them, 0 after): no auto-link when the row has no
numeric mode (D, E, 6* ...), nor when another index row has the same incipit on the same page
(in festis / in memoriis, cum alleluia, second settings — the variants a prefix can't tell apart). Everything else is left for one-row-per-agent review
(index-row-resolver), which writes 'resolved_with_difficulty' — never 'resolved'.

    python tools/resolve_index.py --book LIBER_HYMNARIUS --source 15 [--commit] [--units-file F]

--source   gregobase_sources.id of THIS book's edition (15 = Liber Hymnarius 1983, 4 = GR 1974,
           16 = Gregorian Missal 1990); 0 if gregobase has no edition of the book.
--units-file  write the still-unlinked row_ids (r<row_id> per line) for tools/work_queue.py
Rows that already carry a match_status are never touched.
"""
import argparse
import json

from sqlalchemy import bindparam, text

from _db import engine
from index_util import SECTION_TO_OFFICE_PART, condense, prefix_match


def candidates(c, source, office_part, page):
    pages = [str(int(page) + d) for d in (0, -1, 1)] if str(page).isdigit() else [str(page)]
    rows = c.execute(text(
        "SELECT g.id, g.incipit, g.mode, s.page, m.chant_group_id "
        "FROM gregobase_chant_sources s JOIN gregobase_chants g ON g.id = s.chant_id "
        "LEFT JOIN chants m ON m.origin_source = 'GREGOBASE' AND m.origin_id = CAST(g.id AS CHAR) "
        "WHERE s.source = :src AND s.page IN :pages AND g.`office-part` = :op AND g.duplicateof IS NULL"
    ).bindparams(bindparam("pages", expanding=True)),
        {"src": source, "pages": pages, "op": office_part}).all()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--source", type=int, required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--units-file")
    a = ap.parse_args()
    eng = engine(rw=a.commit)
    resolved, left = [], []
    with (eng.begin() if a.commit else eng.connect()) as c:
        todo = c.execute(text("SELECT row_id, section_type, mode, incipit, page FROM chant_indices "
                              "WHERE book=:b AND match_status IS NULL AND chant_uuid IS NULL ORDER BY id"),
                         {"b": a.book}).all()
        siblings = {}
        for r in c.execute(text("SELECT incipit, page FROM chant_indices WHERE book=:b"), {"b": a.book}):
            k = (condense(r.incipit), str(r.page))
            siblings[k] = siblings.get(k, 0) + 1
        for r in todo:
            op = SECTION_TO_OFFICE_PART.get(r.section_type)
            why = None
            if not op or not a.source:
                why = "no office-part/source"
            elif r.mode is None:
                why = "no numeric mode"
            elif siblings.get((condense(r.incipit), str(r.page)), 0) > 1:
                why = "same incipit twice on this page"
            else:
                hits = [g for g in candidates(c, a.source, op, r.page) if prefix_match(g.incipit, r.incipit)]
                same_page = [g for g in hits if g.page == str(r.page)]
                pool = same_page or hits
                pool = [g for g in pool if str(g.mode or "").strip() == str(r.mode)]
                if len(pool) != 1:
                    why = f"{len(pool)} candidates"
                elif pool[0].chant_group_id is None:
                    why = f"gregobase:{pool[0].id} is ungrouped"
                else:
                    g = pool[0]
                    resolved.append((r.row_id, g.id))
                    print(f"✓ row {r.row_id} p{r.page} {r.incipit!r} → gregobase:{g.id} {g.incipit!r} m{g.mode}")
                    if a.commit:
                        c.execute(text("UPDATE chant_indices SET chant_uuid=:u, match_status='resolved' "
                                       "WHERE row_id=:i AND match_status IS NULL"),
                                  {"u": f"gregobase:{g.id}", "i": r.row_id})
                    continue
            left.append(r.row_id)
            print(f"· row {r.row_id} p{r.page} {r.incipit!r}: {why} → agent queue")
    if a.units_file:
        with open(a.units_file, "w", encoding="utf-8") as f:
            f.writelines(f"r{i}\n" for i in left)
    print(json.dumps({"commit": a.commit, "resolved": len(resolved), "for_agents": len(left)}))


if __name__ == "__main__":
    main()
