"""Load the GR 1974 Kyriale (graduale/kyriale/kyriale.json) into kyriale_mass(_part) + lit_part_sources.

Model (user rulings 2026-11-17, see graduale/specs/README.md "Kyriale"):
  * kyriale_mass / kyriale_mass_part catalogue each Missa and the chant in each part.
  * Assignments are lit_part_sources rows on superepochs, one per chant per scope:
    PASC / OT / ADV / TQ / COM-BMV / COM-APOST / liturgia-defunctorum, narrowed by wkday
    (1 = Sundays) or rank_code (rank sets expanded from the JSON). option_num = Missa number;
    option_txt names the Missa ("Kyriale IX (Cum iubilo)") so a Missa's rows can be found.
  * Rows are upserted by slot (uq_lps_slot): existing rows are left alone, chant_uuid is never
    overwritten. The catalogue is replaced per Missa (it is derived from the JSON only).

Usage:  python graduale/load_kyriale.py [--dry-run | --verify] [--only N,N]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from _db import engine
from sqlalchemy import text

BOOK = "GRADUALE"
SRC = os.path.join(os.path.dirname(__file__), "kyriale", "kyriale.json")
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII",
         "XIV", "XV", "XVI", "XVII", "XVIII"]
PART_NAMES = {"ky": "Kyrie", "gl": "Gloria", "sanc": "Sanctus", "agn": "Agnus Dei", "ite": "Ite, missa est"}


def build(data, ro, only):
    parts = dict(ro.execute(text("SELECT part_code, part_id FROM service_part WHERE service_code='MASS'")).fetchall())
    errors, cat, rows = [], [], []
    for m in data["masses"]:
        n = m.get("n")
        key = n if n is not None else m["id"]
        if only and key not in only:
            continue
        if n is None:   # a chant set that is not a Missa (Asperges, Credo, ad-lib): rows only, no catalogue
            name, optnum = m["name"], m.get("option_num", 1)
        else:
            name, optnum = f"Kyriale {ROMAN[n]}" + (f" ({m['trope']})" if m.get("trope") else ""), n
        mparts = []
        for seq, (pc, gid, page, label, alt, rubric, note) in enumerate(m["parts"], 1):
            if pc not in parts:
                errors.append(f"{name}: unknown part {pc}")
                continue
            if pc not in PART_NAMES:
                PART_NAMES[pc] = pc
            mparts.append(dict(part_code=pc, part_id=parts[pc], chant_uuid=f"gregobase:{gid}", label=label,
                               is_alternative=alt, rubric=rubric, printed_page_num=page, seq=seq, notes=note))
        if n is not None:
            cat.append(dict(n=n, title=m.get("title"), trope=m.get("trope"), pages=m["pages"],
                            notes=m.get("notes"), parts=mparts))
        for sc in m["scopes"]:
            ranks = [None]
            if sc.get("rank"):
                ranks = [r for key in sc["rank"] for r in data["rank_sets"][key]]
            for p in mparts:
                if "labels" in sc and p["label"] not in sc["labels"]:
                    continue
                if "parts" in sc and p["part_code"] not in sc["parts"]:
                    continue
                txt = name
                if p["label"]:
                    txt += f", {PART_NAMES[p['part_code']]} {p['label']}"
                if p["rubric"]:
                    txt += f": {p['rubric']}"
                if m.get("title"):
                    txt += f" [{m['title']}]"
                if sc.get("via"):
                    txt += f" [{sc['via']}]"
                for rk in ranks:
                    rows.append(dict(part_id=p["part_id"], lit_epoch_slug=sc["epoch"], wkday=sc.get("wkday"),
                                     rank_code=rk, chant_uuid=p["chant_uuid"], printed_page_num=p["printed_page_num"],
                                     option_num=optnum, option_txt=txt[:512], _key=key,
                                     display_name=f"{name} — {PART_NAMES[p['part_code']]}"[:300],
                                     _label=f"{(ROMAN[n] if n else m['id']):>5} {p['part_code']:<4} {p['label'] or '-'} {p['chant_uuid']:<16} -> {sc['epoch']} wkday={sc.get('wkday')} rank={rk}"))
    # reference checks
    for r in {r["lit_epoch_slug"] for r in rows}:
        if not ro.execute(text("SELECT 1 FROM lit_epoch WHERE slug=:s"), dict(s=r)).first():
            errors.append(f"missing lit_epoch {r}")
    for c in cat + [dict(n=0, parts=[dict(chant_uuid=r["chant_uuid"], printed_page_num=r["printed_page_num"]) for r in rows])]:
        for p in c["parts"]:
            if not ro.execute(text("SELECT 1 FROM v_chant_item WHERE chant_item_uid=:u"), dict(u=p["chant_uuid"])).first():
                errors.append(f"Kyriale {ROMAN[c['n']]}: chant {p['chant_uuid']} not in v_chant_item")
            if not ro.execute(text("SELECT 1 FROM books WHERE book=:b AND printed_page_num=:p"),
                              dict(b=BOOK, p=p["printed_page_num"])).first():
                errors.append(f"page {p['printed_page_num']} not in books")
    for rk in {r["rank_code"] for r in rows if r["rank_code"]}:
        if not ro.execute(text("SELECT 1 FROM p_lit_rank WHERE rank_code=:r"), dict(r=rk)).first():
            errors.append(f"unknown rank {rk}")
    return cat, rows, errors


SLOT_SQL = """SELECT text_id, chant_uuid FROM lit_part_sources
  WHERE jurisdiction='UNIVERSAL' AND lit_epoch_slug=:lit_epoch_slug AND part_id=:part_id AND book=:book
    AND assignment_authority_code=:book AND cycle_sun IS NULL AND cycle_wkday IS NULL
    AND wkday <=> :wkday AND wknum_mod_4 IS NULL AND wknum_mod_2 IS NULL AND rank_code <=> :rank_code
    AND translation_source_code IS NULL AND option_num=:option_num AND chant_uuid=:chant_uuid"""


def existing(c, r):
    return c.execute(text(SLOT_SQL), dict(r, book=BOOK)).first()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = {int(x) if x.isdigit() else x for x in a.only.split(",") if x}
    data = json.load(open(SRC, encoding="utf-8"))
    with engine().connect() as ro:
        cat, rows, errors = build(data, ro, only)
        new = [r for r in rows if not existing(ro, r)]
    for e in errors:
        print("✗", e)
    if a.dry_run or errors:
        for r in rows:
            print(("+ " if r in new else "= ") + r["_label"])
        print(f"{len(cat)} Missae, {sum(len(c['parts']) for c in cat)} chants, {len(rows)} assignment rows ({len(new)} new)")
        if errors:
            print("REFUSED: fix the errors above"); sys.exit(1)
        return
    if a.verify:
        with engine().connect() as ro:
            fails = []
            for c in cat:
                k = ro.execute(text("SELECT kyriale_id FROM kyriale_mass WHERE book=:b AND number=:n"), dict(b=BOOK, n=c["n"])).scalar()
                got = ro.execute(text("SELECT COUNT(*) FROM kyriale_mass_part WHERE kyriale_id=:k"), dict(k=k)).scalar() if k else 0
                if got != len(c["parts"]):
                    fails.append(f"CATALOGUE Kyriale {ROMAN[c['n']]}: expected {len(c['parts'])} parts, got {got}")
            if new:
                fails.append(f"IDEMPOTENT: {len(new)} rows would still insert")
            got = sum(1 for r in rows if existing(ro, r))
            if got != len(rows):
                fails.append(f"ROW COUNT: expected {len(rows)}, got {got}")
        print("\n".join(fails) if fails else "", "VERIFY FAIL" if fails else f"VERIFY PASS ({len(cat)} Missae, {len(rows)} rows)")
        sys.exit(1 if fails else 0)
    with engine(rw=True).begin() as c:
        for m in cat:
            c.execute(text("""INSERT INTO kyriale_mass (book, number, title, trope, page_first, page_last, notes)
                              VALUES (:b,:n,:t,:tr,:p1,:p2,:no)
                              ON DUPLICATE KEY UPDATE title=VALUES(title), trope=VALUES(trope), page_first=VALUES(page_first),
                                page_last=VALUES(page_last), notes=VALUES(notes)"""),
                      dict(b=BOOK, n=m["n"], t=m["title"], tr=m["trope"], p1=m["pages"][0], p2=m["pages"][1], no=m["notes"]))
            k = c.execute(text("SELECT kyriale_id FROM kyriale_mass WHERE book=:b AND number=:n"), dict(b=BOOK, n=m["n"])).scalar()
            c.execute(text("DELETE FROM kyriale_mass_part WHERE kyriale_id=:k"), dict(k=k))
            for p in m["parts"]:
                c.execute(text("""INSERT INTO kyriale_mass_part (kyriale_id, part_id, chant_uuid, label, is_alternative, rubric,
                                    printed_page_num, seq, notes) VALUES (:k,:part_id,:chant_uuid,:label,:is_alternative,:rubric,
                                    :printed_page_num,:seq,:notes)"""), dict(p, k=k))
        ins = 0
        for r in rows:
            if existing(c, r):
                continue
            c.execute(text("""INSERT INTO lit_part_sources (part_id, lit_epoch_slug, wkday, rank_code, chant_uuid, book,
                                assignment_authority_code, printed_page_num, option_num, option_txt, display_name, jurisdiction)
                              VALUES (:part_id,:lit_epoch_slug,:wkday,:rank_code,:chant_uuid,:book,:book,:printed_page_num,
                                :option_num,:option_txt,:display_name,'UNIVERSAL')"""),
                      {k: v for k, v in dict(r, book=BOOK).items() if not k.startswith("_")})
            ins += 1
    print(f"loaded {len(cat)} Missae; {ins} lit_part_sources rows inserted ({len(rows) - ins} already present)")


if __name__ == "__main__":
    main()
