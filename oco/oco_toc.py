#!/usr/bin/env python
"""oco_toc.py — OCO's TOC (book_toc) as evidence for the sigla mapper.

The Proprium de sanctis headings ("Die 3: S. Blasii", then "Vel: S. Ansgarii" for a second saint
of the same day) give, for each date, its saints IN BOOK ORDER and the page each one starts on.
`saint_entries(conn)` matches every heading to that date's UNIVERSAL proper_of_saints slug by name
(Latin heading vs English common_name, by 4-letter stems), so the mapper can:
  - pick the saint of a multi-saint date whose own section holds the row's page;
  - read B1/B2/M1/M2 as the n-th saint of the date (see the switch in oco_sigla.py).

    python oco/oco_toc.py          # print every multi-saint date: heading → slug (or why not)
"""
import re
import sys
import unicodedata

MONTHS = ["Ianuarius", "Februarius", "Martius", "Aprilis", "Maius", "Iunius", "Iulius", "Augustus",
          "September", "October", "November", "December"]
STOP = {"sanct", "sancti", "sancta", "sanctae", "saint", "saints", "beata", "beatae", "virgin", "virgi",
        "marty", "bisho", "pries", "abbot", "docto", "relig", "compa", "socio", "sociorum", "and", "et",
        "the", "of", "ss", "mi"}


def stems(s, n=4):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("ae", "e").replace("j", "i").replace("w", "u").replace("v", "u").replace("y", "i").replace("ph", "f")
    s = s.replace("th", "t").replace("k", "c").replace("ch", "c")
    return {w[:n] for w in re.findall(r"[a-z]{4,}", s) if w[:5] not in STOP and w not in STOP}


def saint_entries(conn):
    """{(month, day): [(slug or None, heading, start_page, end_page)]} in book order; end_page is the
    start page of the next TOC entry (a page may be shared with the neighbours)."""
    from sqlalchemy import text
    toc = conn.execute(text("SELECT idx, level, text, CAST(printed_page AS UNSIGNED) p FROM book_toc "
                            "WHERE book='OCO' ORDER BY idx")).all()
    names = {}
    for slug, m, d, name in conn.execute(text(
            "SELECT slug, month_nominal, day_nominal, common_name FROM proper_of_saints "
            "WHERE jurisdiction='UNIVERSAL' AND month_nominal IS NOT NULL")):
        nm = name + " " + slug.replace("-", " ")
        names.setdefault((m, d), []).append((slug, stems(nm), stems(nm, 3)))
    out, month, day, in_sanct = {}, None, None, False
    for i, t in enumerate(toc):
        if t.level == 1:
            in_sanct = "SANCTIS" in t.text
            continue
        if not in_sanct:
            continue
        if t.level == 2 and t.text in MONTHS:
            month = MONTHS.index(t.text) + 1
            continue
        m = re.match(r"Die (\d+):\s*(.*)", t.text)
        if m:
            day, title = int(m.group(1)), m.group(2)
        elif t.text.startswith("Vel:") and day:
            title = t.text[4:].strip()
        else:
            continue
        end = toc[i + 1].p if i + 1 < len(toc) else t.p
        out.setdefault((month, day), []).append([None, t.text, t.p, end, title])
    for key, es in out.items():
        cands = names.get(key, [])
        for n in (4, 3):  # 4-letter stems, then 3 ('Blasii' ~ 'Blaise')
            for e in es:
                if e[0]:
                    continue
                st = stems(e[4], n)
                taken = {x[0] for x in es}
                scored = sorted(((len(st & (s4 if n == 4 else s3)), slug) for slug, s4, s3 in cands
                                 if slug not in taken), reverse=True)
                if scored and scored[0][0] and (len(scored) == 1 or scored[1][0] < scored[0][0]):
                    e[0] = scored[0][1]
        left = [slug for slug, *_ in cands if slug not in {x[0] for x in es}]
        open_ = [e for e in es if not e[0]]
        if len(open_) == 1 and len(left) == 1 and len(es) == len(cands):  # elimination ('Xysti' = sixtus-ii)
            open_[0][0] = left[0]
    return {k: [tuple(e[:4]) for e in es] for k, es in out.items()}


def main():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
    from _db import engine
    from sqlalchemy import text
    with engine().connect() as c:
        ents = saint_entries(c)
        db = {}
        for slug, m, d in c.execute(text("SELECT slug, month_nominal, day_nominal FROM proper_of_saints "
                                         "WHERE jurisdiction='UNIVERSAL' AND month_nominal IS NOT NULL")):
            db.setdefault((m, d), []).append(slug)
    bad = 0
    for (m, d), es in sorted(ents.items()):
        if len(es) < 2 and len(db.get((m, d), [])) < 2:
            continue
        print(f"{d}/{m}: db {db.get((m, d))}")
        for slug, title, p, e in es:
            bad += slug is None
            print(f"   {'✓' if slug else '✗'} {slug or '-':40} {title} p{p}-{e}")
    print("unmatched headings:", bad, "| headings with no slug at all:",
          sum(s is None for es in ents.values() for s, *_ in es))



def check():
    """Cross-check the mapper against the TOC: a row whose engraving is its OWN first assignment (the
    link's named dest starts with the row's day code) must map to the slug of the TOC section holding
    its page. Sanctorale sections know their slug (saint_entries); other sections get the slug most of
    their own rows map to (≥ 60 %). Prints the rows that disagree."""
    import json
    import os
    import sys
    from collections import Counter, defaultdict
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "tools"))
    sys.path.insert(0, here)
    from _db import engine
    from oco_sigla import load_saints, targets
    from sqlalchemy import text
    links = json.load(open(os.path.join(here, "index", "link_targets.json"), encoding="utf-8"))
    with engine().connect() as c:
        saints = load_saints(c)
        toc = c.execute(text("SELECT idx, level, text, CAST(printed_page AS UNSIGNED) p FROM book_toc "
                             "WHERE book='OCO' ORDER BY idx")).all()
        rows = c.execute(text("SELECT id, row_id, incipit, page, section_type, day_code, hour_code, place_code "
                              "FROM chant_indices WHERE book='OCO' AND page IS NOT NULL")).all()
    known = {}  # toc text+page → slug, from the sanctorale
    for es in saints.toc.values():
        for slug, title, p, _ in es:
            if slug:
                known[(title, p)] = slug

    def leaves(p):  # the deepest entries that can hold page p: those starting on p + the one running into it
        before = [t for t in toc if t.p < p]
        on = [t for t in toc if t.p == p]
        return ([before[-1]] if before else []) + on

    own, votes = [], defaultdict(Counter)
    for r in rows:
        dest = (links.get(str(r.id)) or [None, None, None])[2] or ""
        m = re.match(r"A\[([^,]*),", dest)
        if not m or m.group(1) != r.day_code:
            continue
        ts, why = targets(r, saints)
        slugs = {t["slug"] for t in ts if t["slug"]}
        if why or not slugs:
            continue
        lv = leaves(int(r.page))
        own.append((r, slugs, lv))
        if len(lv) == 1:
            for s in slugs:
                votes[lv[0].idx][s] += 1
    expect = {}
    for t in toc:
        if (t.text, t.p) in known:
            expect[t.idx] = {known[(t.text, t.p)]}
        elif votes[t.idx]:
            s, n = votes[t.idx].most_common(1)[0]
            if n >= 0.6 * sum(votes[t.idx].values()):
                expect[t.idx] = {s for s, k in votes[t.idx].items() if k == n}
    flagged = []
    for r, slugs, lv in own:
        exp = [expect.get(t.idx) for t in lv]
        if any(e is None for e in exp):
            continue  # a section with no expectation can't judge
        if not slugs & set().union(*exp):
            flagged.append((r, slugs, lv, exp))
    print(f"own-engraving rows checked: {len(own)}; disagree with the TOC: {len(flagged)}")
    for r, slugs, lv, exp in flagged:
        print(f"  #{r.id} '{r.incipit[:32]}' {r.day_code}|{r.hour_code}|{r.place_code} p{r.page} → {sorted(slugs)} "
              f"but TOC {' / '.join(t.text for t in lv)} expects {sorted(set().union(*exp))}")


if __name__ == "__main__" and "--check" in sys.argv:
    check()
    sys.exit()


if __name__ == "__main__":
    main()
