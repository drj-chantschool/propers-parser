#!/usr/bin/env python
"""candidates.py — gregobase candidates for ONE OCO engraving, from its printed text (stage `pages`).

    python oco/candidates.py "<engraving's full text>" [--part antiphona|responsorium breve|invitatorium|hymnus]
                             [--cao N] [--mode 8g]

The text is the white text line page_draft.py prints for the engraving. Lists every gregobase chant whose
sung text starts like it (or whose cantusid = the CAO number), with chant_group, mode, cited sources
(`7:327` = AM 1934 p327; 6 = ARII, 24 = PM, 56 = RM, 9 = AR, 48 = Liber antiphonarius 1960) and the
opening of the gabc, so the producer can compare neumes with the engraving. Read-only.
"""
import argparse
import os
import re
import sys

from sqlalchemy import text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from _db import engine  # noqa: E402
from index_util import SECTION_TO_OFFICE_PART, condense  # noqa: E402
from resolve_oco_index import lyrics  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--part", default="antiphona")
    ap.add_argument("--cao")
    ap.add_argument("--mode")
    a = ap.parse_args()
    key = condense(a.text).replace("oe", "ae")
    first = re.findall(r"\w+", a.text)[0]
    op = SECTION_TO_OFFICE_PART.get(a.part)
    with engine().connect() as c:
        cands = c.execute(text(
            "SELECT g.id, g.incipit, g.mode, g.version, g.cantusid, g.`office-part` op, m.chant_group_id grp, g.gabc "
            "FROM gregobase_chants g LEFT JOIN chants m ON m.origin_source = 'GREGOBASE' AND m.origin_id = CAST(g.id AS CHAR) "
            "WHERE g.duplicateof IS NULL AND (g.incipit LIKE :w OR g.cantusid=:cao)"),
            {"w": first[:6] + "%", "cao": (a.cao or "x").zfill(6)}).all()
        shown = 0
        for g in cands:
            ly = lyrics(g.gabc).replace("oe", "ae")
            n = min(len(ly), len(key))
            same = n >= 10 and ly[:n] == key[:n]
            cao = bool(a.cao and g.cantusid == a.cao.zfill(6))
            if not (same or cao) or (op and g.op != op and not cao):
                continue
            shown += 1
            cited = [s for (s,) in c.execute(text("SELECT CONCAT(source,':',page) FROM gregobase_chant_sources "
                                                  "WHERE chant_id=:i"), {"i": g.id})]
            body = (g.gabc or "").split("%%", 1)[-1].strip()[:170].replace("\n", " ")
            flag = "" if not a.mode or (g.mode or "")[:1] == a.mode[:1] else "  (mode differs)"
            print(f"gregobase:{g.id} grp {g.grp or 'UNGROUPED'} m{g.mode} {g.op} {g.version or ''} '{g.incipit}' "
                  f"text={'=' if same else '≠'} cao={'=' if cao else '-'} sources={cited}{flag}\n    {body}")
        print(f"{shown} candidate(s)")


if __name__ == "__main__":
    main()
