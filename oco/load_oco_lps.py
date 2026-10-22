#!/usr/bin/env python
"""load_oco_lps.py — OCO chant_indices rows → lit_part_sources (the combined "index row" pass).

A unit is ONE chant_indices row (book OCO). Its identity is the row's chant_uuid (one edition) or
chant_group_id (group, no edition chosen); its assignment comes from the printed day/hour/place codes
through oco/oco_sigla.py — deterministic, never guessed — or, for a code that can't name the day
(a date with several saints), from a reviewed override in oco/index/lps_overrides.json
{"<index id>": {"slugs": [...], "wkday": null, "option_txt": null, "rank_codes": null}}. One index row can expand into several LPS rows
(a code list '25/4 11/6 18/10', L-V, rank tiers, cycle letters 'Mbc').

LPS row: book='OCO', printed_page_num = the engraving page (index link target; NULL for hymns, which
OCO cites from the Liber Hymnarius: ref_book='LIBER_HYMNARIUS', ref_page_num = LHym page),
assignment_authority_code='OCO', jurisdiction UNIVERSAL, review_status 'draft',
notes 'OCO index #<id>: <day> | <hour> | <place>'.
option_num: fixed by the codes for B1/B2/M1/M2 alternatives; else 1 when the codes carry no option
qualifier; otherwise the next free number in the slot.
Two DIFFERENT chants claiming option 1 of the same slot is a conflict: reported, not loaded.
Upsert by (slot + chant): re-running is idempotent; an existing row's chant is never overwritten.

    python oco/load_oco_lps.py [--rows ID,ID-ID | --where "<SQL on chant_indices ci>"] [--dry-run | --verify]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

from sqlalchemy import text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from _db import engine  # noqa: E402
from oco_sigla import load_saints, targets  # noqa: E402

SLOT = ["lit_epoch_slug", "part_id", "wkday", "wknum_mod_2", "wknum_mod_4", "cycle_sun", "cycle_wkday", "rank_code"]


def id_filter(spec):
    ids = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        ids += list(range(int(a), int(b or a) + 1))
    return ids


# Lent III-V weekday cross-references (intake #24; v.6 pp183, 199, 215-216): "Infra hebdomadam, si quavis die
# legatur evangelium de …, antiphonae sequentes adhiberi possunt: Laudes B …, Vesp. M … ut supra pro anno A".
# (source index id = the Sunday row whose chant is meant, Lent week, service, part, weekdays, gospel, rubric page)
# Saturday has no Vespers of its own (I Vespers of Sunday), so the Magnificat rows stop at Friday.
LENT_XREFS = [
    (596, 3, "LAUDS", "antB", range(2, 8), "de Samaritana", 183),     # Aqua
    (2118, 3, "VESPERS", "antM", range(2, 7), "de Samaritana", 183),  # Mulier, venient dies (Sunday Sext, a)
    (2592, 4, "LAUDS", "antB", range(2, 8), "de caeco nato", 199),    # Rabbi
    (440, 4, "VESPERS", "antM", range(2, 7), "de caeco nato", 199),   # A saeculo
    (1949, 5, "LAUDS", "antB", range(2, 8), "de Lazaro", 216),        # Lazarus amicus noster (Sunday Terce, a)
    (1143, 5, "VESPERS", "antM", range(2, 7), "de Lazaro", 216),      # Domine, si hic (Sunday Sext, a)
]


def lent_xrefs(rows, part_id):
    """Plan rows for LENT_XREFS whose source index row is in `rows` and identified. They wait (like ad-lib
    options) until the weekday slot has its own option-1 antiphon."""
    by_id = {r.id: r for r in rows}
    out = []
    for src, wk, svc, part, days, gospel, rubric_page in LENT_XREFS:
        r = by_id.get(src)
        if not r or not (r.chant_uuid or r.chant_group_id):
            continue
        for d in days:
            out.append({
                "index_id": r.id, "row_id": r.row_id, "incipit": r.incipit,
                "lit_epoch_slug": f"TQ-LENT-0{wk}-{d}", "part_id": part_id[(svc, part)], "svc": f"{svc}.{part}",
                "wkday": None, "wknum_mod_2": None, "wknum_mod_4": None, "cycle_sun": None, "cycle_wkday": None,
                "rank_code": None, "option_txt": f"cum Evangelio {gospel}", "option_num": None,
                "chant_uuid": r.chant_uuid, "chant_group_id": r.chant_group_id,
                "printed_page_num": str(rubric_page), "ref_book": "OCO", "ref_page_num": int(r.page) if r.page else None,
                "hold_without_primary": True,
                "notes": f"OCO p{rubric_page} 'Infra hebdomadam, si quavis die legatur evangelium {gospel}': "
                         f"xref of index #{r.id} ({r.day_code} | {r.hour_code} | {r.place_code})",
            })
    return out


def build(c, where, params):
    saints = load_saints(c)
    part_id = {(s, p): i for i, s, p in c.execute(text("SELECT part_id, service_code, part_code FROM service_part"))}
    rows = c.execute(text(
        "SELECT ci.row_id, ci.id, ci.section_type, ci.incipit, ci.page, ci.day_code, ci.hour_code, ci.place_code, "
        "ci.notes, ci.chant_uuid, ci.chant_group_id FROM chant_indices ci WHERE ci.book='OCO' AND " + where +
        " ORDER BY ci.id"), params).all()
    plan, skipped = [], []
    ov = os.path.join(HERE, "index", "lps_overrides.json")
    overrides = json.load(open(ov, encoding="utf-8")) if os.path.exists(ov) else {}
    for r in rows:
        if not r.chant_uuid and not r.chant_group_id:
            skipped.append((r, "no identity yet"))
            continue
        ts, why = targets(r, saints, overrides.get(str(r.id)))
        if why:
            skipped.append((r, why))
            continue
        lh = re.search(r"LHym (\d+)", r.notes or "")
        for t in ts:
            for rank in t["rank_codes"] or [None]:
                plan.append({
                    "index_id": r.id, "row_id": r.row_id, "incipit": r.incipit,
                    "lit_epoch_slug": t["slug"], "part_id": part_id[(t["service"], t["part"])],
                    "svc": f"{t['service']}.{t['part']}", "wkday": t["wkday"],
                    "wknum_mod_2": t["wknum_mod_2"], "wknum_mod_4": t["wknum_mod_4"],
                    "cycle_sun": t["cycle_sun"], "cycle_wkday": t["cycle_wkday"], "rank_code": rank,
                    "option_txt": t["option_txt"], "option_num": t.get("option_num"), "chant_uuid": r.chant_uuid, "chant_group_id": r.chant_group_id,
                    "printed_page_num": r.page,
                    "ref_book": "LIBER_HYMNARIUS" if r.section_type == "hymnus" and lh else None,
                    "ref_page_num": int(lh.group(1)) if r.section_type == "hymnus" and lh else None,
                    "notes": f"OCO index #{r.id}: {r.day_code} | {r.hour_code} | {r.place_code}"[:500],
                })
    plan += lent_xrefs(rows, part_id)
    return plan, skipped


def key(p):
    return tuple(p[k] for k in SLOT)


def ident(p):
    return p["chant_uuid"] or f"group:{p['chant_group_id']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", help="index ids, e.g. 1-50,77")
    ap.add_argument("--where", help="extra SQL condition on chant_indices ci")
    ap.add_argument("--with-adlib", action="store_true",
                    help="load 'Ad libitum' options even when their slot has no option-1 primary yet (by default "
                         "they wait: an ad-lib alone in a more specific slot would hide the primary in the day query)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    where, params = "1=1", {}
    if a.rows:
        where = "ci.id IN (" + ",".join(map(str, id_filter(a.rows))) + ")"
    if a.where:
        where += f" AND ({a.where})"
    write = not (a.dry_run or a.verify)
    eng = engine(rw=write)
    with (eng.begin() if write else eng.connect()) as c:
        plan, skipped = build(c, where, params)
        existing = defaultdict(list)  # slot → [(option_num, ident, text_id)] for OCO rows
        for e in c.execute(text("SELECT text_id, option_num, chant_uuid, chant_group_id, " + ", ".join(SLOT) +
                                " FROM lit_part_sources WHERE assignment_authority_code='OCO' AND book='OCO'")).mappings():
            existing[tuple(e[k] for k in SLOT)].append((e["option_num"], e["chant_uuid"] or f"group:{e['chant_group_id']}", e["text_id"]))
        stats = defaultdict(int)
        conflicts = []
        for p in plan:
            slot = existing[key(p)]
            if not a.with_adlib and ((p["option_txt"] or "").startswith("Ad libitum") or p.get("hold_without_primary"))                     and not any(x[0] == 1 for x in slot) and not any(x[1] == ident(p) for x in slot):
                stats["held_adlib_no_primary"] += 1
                continue
            have = [x for x in slot if x[1] == ident(p)]
            if have:
                stats["unchanged"] += 1
                continue
            if a.verify:
                stats["MISSING"] += 1
                print(f"✗ missing  #{p['index_id']} {p['incipit']!r} {p['lit_epoch_slug']} {p['svc']}")
                continue
            if p["option_num"]:  # the codes fix the option (B1/B2 alternatives)
                taken = [x for x in slot if x[0] == p["option_num"]]
                if taken:
                    conflicts.append(p)
                    print(f"⚠ CONFLICT #{p['index_id']} {p['incipit']!r} → {p['lit_epoch_slug']} {p['svc']} "
                          f"option {p['option_num']} already {taken[0][1]} (text_id {taken[0][2]})")
                    continue
                opt = p["option_num"]
            elif p["option_txt"] is None:
                prim = [x for x in slot if x[0] == 1]
                if prim:
                    conflicts.append(p)
                    print(f"⚠ CONFLICT #{p['index_id']} {p['incipit']!r} → {p['lit_epoch_slug']} {p['svc']} "
                          f"wkday={p['wkday']} option 1 already {prim[0][1]} (text_id {prim[0][2]})")
                    continue
                opt = 1
            else:
                opt = max([x[0] for x in slot] + [1]) + 1
            stats["insert"] += 1
            slot.append((opt, ident(p), None))
            print(f"+ #{p['index_id']:>4} {p['incipit'][:32]:<32} {str(p['lit_epoch_slug']):<22} {p['svc']:<16} "
                  f"wd={p['wkday']} m2={p['wknum_mod_2']} m4={p['wknum_mod_4']} cs={p['cycle_sun']} "
                  f"cw={p['cycle_wkday']} rk={p['rank_code']} opt={opt} {p['option_txt'] or ''} → {ident(p)}")
            if write:
                c.execute(text(
                    "INSERT INTO lit_part_sources (jurisdiction, lit_epoch_slug, part_id, wkday, wknum_mod_2, "
                    "wknum_mod_4, cycle_sun, cycle_wkday, rank_code, option_num, option_txt, chant_uuid, chant_group_id, "
                    "book, printed_page_num, ref_book, ref_page_num, assignment_authority_code, review_status, notes) "
                    "VALUES ('UNIVERSAL', :lit_epoch_slug, :part_id, :wkday, :wknum_mod_2, :wknum_mod_4, :cycle_sun, "
                    ":cycle_wkday, :rank_code, :opt, :option_txt, :chant_uuid, :chant_group_id, 'OCO', "
                    ":printed_page_num, :ref_book, :ref_page_num, 'OCO', 'draft', :notes)"), {**p, "opt": opt})
        reasons = defaultdict(int)
        for _, why in skipped:
            reasons[why if not why.startswith(("no rule", "place", "hour")) else why.split(" ")[0] + " …"] += 1
    print(json.dumps({"mode": "verify" if a.verify else "dry-run" if a.dry_run else "load",
                      "planned_rows": len(plan), **stats, "conflicts": len(conflicts),
                      "skipped_index_rows": len(skipped), "skip_reasons": dict(reasons)}, ensure_ascii=False))
    sys.exit(1 if (a.verify and stats["MISSING"]) or conflicts else 0)


if __name__ == "__main__":
    main()
