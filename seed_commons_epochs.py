#!/usr/bin/env python
"""Seed the Graduale Romanum's Communia (Commons) into lit_epoch / lit_epoch_tree.

`make-lit-epoch.sql` left the Commons hierarchy as future work, so no lit_epoch row
existed for any Common — which blocked loading Graduale chapter 2 entirely
(`lit_part_sources.lit_epoch_slug` is a required FK into `lit_epoch.slug`).

This seeds a new `kind='common'` tier: 5 container nodes (a Commune that only wraps
named sub-formularies) and 21 formulary nodes (one per line the book's own TOC on
printed p. 395 names). Page spans are PRINTED pages in `graduale romanum.pdf`.

Idempotent: re-running UPSERTs the same rows and re-inserts no tree edges.
Read-only unless --commit is passed.
"""
import argparse
import sys

import keyring
from sqlalchemy import create_engine, text

# (slug, parent_slug, title, printed span, notes)
CONTAINERS = [
    ("COM-DED",       None, "Common of the Dedication of a Church",            "397-402", None),
    ("COM-APOST-TP",  None, "Common of Apostles or Martyrs in Paschaltide",    "439-444", None),
    ("COM-MART-XTP",  None, "Common of Martyrs outside Paschaltide",           "445-484", None),
    ("COM-PAST",      None, "Common of Pastors",                               "485-492",
     "GR p. 492 closes with a rubric: for pastors in general, founders of churches and "
     "missionaries, take texts from the Common of Holy Men and Women (COM-SANCT) instead. "
     "No separate 'in genere' formulary is printed here."),
    ("COM-SANCT",     None, "Common of Holy Men and Women",                    "508-530", None),
]

FORMULARIES = [
    # slug, parent, title, printed span
    ("COM-DED-IPSA",        "COM-DED",      "In ipsa ecclesia dedicata",                    "397-398"),
    ("COM-DED-ALIIS",       "COM-DED",      "In aliis ecclesiis",                           "398-402"),
    ("COM-DED-ALTARIS",     "COM-DED",      "In dedicatione altaris",                       "402-402"),
    ("COM-BMV",             None,           "Common of the Blessed Virgin Mary",            "403-423"),
    ("COM-APOST-XTP",       None,           "Common of Apostles outside Paschaltide",       "424-438"),
    ("COM-APOST-TP-APOST",  "COM-APOST-TP", "Pro Apostolis",                                "439-439"),
    ("COM-APOST-TP-PLUR",   "COM-APOST-TP", "Pro pluribus Apostolis vel martyribus",        "439-442"),
    ("COM-APOST-TP-UNO",    "COM-APOST-TP", "Pro uno Apostolo vel martyre",                 "442-444"),
    ("COM-MART-XTP-PAPIS",  "COM-MART-XTP", "Pro papis vel episcopis",                      "445-447"),
    ("COM-MART-XTP-PRESB",  "COM-MART-XTP", "Pro presbyteris",                              "447-450"),
    ("COM-MART-XTP-PLUR",   "COM-MART-XTP", "Pro pluribus martyribus",                      "450-473"),
    ("COM-MART-XTP-UNO",    "COM-MART-XTP", "Pro uno martyre",                              "473-484"),
    ("COM-PAST-PAPIS",      "COM-PAST",     "Pro papis vel episcopis",                      "485-492"),
    ("COM-DOCT",            None,           "Common of Doctors of the Church",              "493-497"),
    ("COM-VIRG",            None,           "Common of Virgins",                            "498-507"),
    ("COM-SANCT-GEN",       "COM-SANCT",    "Commune sanctorum et sanctarum in genere",     "508-516"),
    ("COM-SANCT-RELIG",     "COM-SANCT",    "Pro religiosis",                               "516-519"),
    ("COM-SANCT-MISER",     "COM-SANCT",    "Pro iis qui opera misericordiae exercuerunt",  "519-522"),
    ("COM-SANCT-EDUC",      "COM-SANCT",    "Pro educatoribus",                             "522-523"),
    ("COM-SANCT-RESP",      "COM-SANCT",    "Pro iis qui respublicas moderati sunt",        "523-525"),
    ("COM-SANCT-MULIER",    "COM-SANCT",    "Pro sanctis mulieribus",                       "525-530"),
]

UPSERT = text(
    "INSERT INTO lit_epoch (slug, kind, title, sort_order, notes) "
    "VALUES (:slug, 'common', :title, :sort_order, :notes) "
    "ON DUPLICATE KEY UPDATE title=VALUES(title), sort_order=VALUES(sort_order), "
    "notes=VALUES(notes)"
)
EDGE = text(
    "INSERT IGNORE INTO lit_epoch_tree (parent_slug, child_slug) VALUES (:p, :c)"
)


def build():
    """Return (rows, edges) in printed-page order, containers before their children."""
    by_parent = {}
    for slug, parent, title, span in FORMULARIES:
        by_parent.setdefault(parent, []).append((slug, title, span))

    ordered = []
    containers = {c[0]: c for c in CONTAINERS}
    # Walk everything in printed-page order; emit a container just before its first child.
    everything = [(c[0], None, c[2], c[3], c[4]) for c in CONTAINERS] + [
        (s, p, t, sp, None) for (s, p, t, sp) in FORMULARIES
    ]
    everything.sort(key=lambda r: (int(r[3].split("-")[0]), r[1] is not None))
    for slug, parent, title, span, notes in everything:
        ordered.append((slug, parent, title, span, notes))

    rows, edges = [], []
    for i, (slug, parent, title, span, notes) in enumerate(ordered, start=1):
        note = notes
        span_note = f"GR (Graduale Romanum) printed pp. {span}"
        note = f"{span_note}. {note}" if note else span_note
        rows.append({
            "slug": slug, "title": title,
            "sort_order": 1000 + i, "notes": note,
        })
        if parent:
            edges.append({"p": parent, "c": slug})
    assert set(containers) <= {r["slug"] for r in rows}
    return rows, edges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="actually write (default: dry run)")
    args = ap.parse_args()

    rows, edges = build()
    user = "jcost" if args.commit else "liturgio_ro"
    pw = keyring.get_password("liturgio-mysql", user)
    engine = create_engine(f"mysql+mysqlconnector://{user}:{pw}@localhost:3306/liturgio")

    with engine.begin() if args.commit else engine.connect() as conn:
        existing = {
            r[0] for r in conn.execute(
                text("SELECT slug FROM lit_epoch WHERE slug IN :s").bindparams(
                    __import__("sqlalchemy").bindparam("s", expanding=True)
                ),
                {"s": [r["slug"] for r in rows]},
            )
        }
        print(f"{len(rows)} epoch rows ({len(rows) - len(edges)} roots, {len(edges)} edges); "
              f"{len(existing)} already present")
        for r in rows:
            mark = "UPDATE" if r["slug"] in existing else "INSERT"
            print(f"  {mark:6s} {r['slug']:22s} sort={r['sort_order']}  {r['title']}")
        for e in edges:
            print(f"  EDGE   {e['p']:22s} -> {e['c']}")

        if not args.commit:
            print("\nDRY RUN — nothing written. Re-run with --commit.")
            return 0

        for r in rows:
            conn.execute(UPSERT, r)
        for e in edges:
            conn.execute(EDGE, e)
        print("\nCOMMITTED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
