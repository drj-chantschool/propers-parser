#!/usr/bin/env python
"""resolve_oco_text.py — second deterministic pass for OCO chant_indices: full-text match against
EVERY gregobase edition (resolve_oco_index.py only follows the editions the engraving cites).

For each still-unlinked row whose page holds exactly one engraving starting with the incipit
(same test as resolve_oco_index.py), collect the gregobase chants of the row's office-part whose
GABC lyrics equal the engraving's full text over their common length (>= MIN_COMMON condensed
letters; oe→ae folded on both sides). Outcome per row:
  chant  — exactly one such chant                     → a chant link
  group  — several chants, all in ONE chant_group      → a group match (no edition chosen)
  multi  — chants in several groups / ungrouped        → agent
  none   — nothing                                     → agent
Dry-run by default; prints a summary and writes the per-row result to --out (JSON lines).
Nothing is written to the DB here: how group matches are stored is decided separately.

    python oco/resolve_oco_text.py [--out oco/index_text_matches.jsonl]
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

import fitz
from sqlalchemy import text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from _db import engine  # noqa: E402
from index_util import SECTION_TO_OFFICE_PART, condense  # noqa: E402
from resolve_oco_index import engravings, incipit_test, lyrics  # noqa: E402

MIN_COMMON = 20
KEY = 12


def fold(s):
    return s.replace("oe", "ae")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "index_text_matches.jsonl"))
    a = ap.parse_args()
    doc = fitz.open(os.path.join(HERE, "oco.pdf"))
    with engine().connect() as c:
        by_key = defaultdict(list)  # (office-part, first KEY letters) → [(id, lyrics, group)]
        for g in c.execute(text(
                "SELECT g.id, g.`office-part` op, g.gabc, m.chant_group_id grp FROM gregobase_chants g "
                "LEFT JOIN gregobase_chant_group_map m ON m.gregobase_id=g.id "
                "WHERE g.duplicateof IS NULL AND g.`office-part` IN ('an','rb','re')")):
            ly = fold(lyrics(g.gabc))
            if len(ly) >= KEY:
                by_key[(g.op, ly[:KEY])].append((g.id, ly, g.grp))
        todo = c.execute(text("SELECT row_id, id, section_type, incipit, page FROM chant_indices "
                              "WHERE book='OCO' AND chant_uuid IS NULL AND page IS NOT NULL ORDER BY id")).all()
    cache, stats, out = {}, Counter(), []
    for r in todo:
        p = int(r.page)
        if p not in cache:
            cache[p] = engravings(doc, p)
        hits = [e for e in cache[p] if incipit_test(r.incipit)(e[0])]
        res = {"row_id": r.row_id, "id": r.id, "page": r.page, "incipit": r.incipit}
        if len(hits) != 1 or re.search(r"\s\d+$", r.incipit.partition("...")[0].strip()):
            res["outcome"] = "no-engraving" if len(hits) != 1 else "numbered"
        else:
            full = fold(condense(hits[0][0]))
            op = SECTION_TO_OFFICE_PART[r.section_type]
            cands = []
            for gid, ly, grp in by_key.get((op, full[:KEY]), []):
                n = min(len(full), len(ly))
                if n >= MIN_COMMON and full[:n] == ly[:n]:
                    cands.append((gid, grp))
            groups = {grp for _, grp in cands}
            res["text"] = hits[0][0]
            res["chants"] = sorted(gid for gid, _ in cands)
            res["groups"] = sorted(x for x in groups if x is not None)
            if not cands:
                res["outcome"] = "none"
            elif len(cands) == 1:
                res["outcome"] = "chant"
            elif len(groups) == 1 and None not in groups:
                res["outcome"] = "group"
            else:
                res["outcome"] = "multi"
        stats[res["outcome"]] += 1
        out.append(res)
    with open(a.out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in out)
    print(json.dumps({"rows": len(out), **stats, "out": a.out}))


if __name__ == "__main__":
    main()
