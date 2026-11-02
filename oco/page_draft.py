#!/usr/bin/env python
"""page_draft.py — the deterministic first pass for ONE OCO page (stage `pages`).

The page is the authority for lit_part_sources; the index is a finding aid (user, 2026-10-23). This
tool reads what the PDF itself says about a page and proposes a spec for the producer to verify
against the image:

  - the page's reading order outside the staves: headings, hour labels, part sigla, cue lines
    ("Iste confessor ut ad Vesperas", "Ut in hebd. I.", "Name (LHym N)"), rubrics;
  - each engraving: its hidden full text (white), ref line, siglum, mode, and its OWN named
    destination (`A[6Q7,Ol,1]` = day 6Q7, Off. lect., antiphon 1), which names the assignment the
    book gives this engraving; the index row with those codes supplies a chant identity if one is set;
  - each cue link: internal links go to another engraving's destination (a cross-reference), and
    gregobase links name a hymn (LHym cue);
  - proposed spec rows: the codes run through oco/oco_sigla.py (the same mapper as the index pass),
    so every proposal is only as good as the codes: the producer checks each against the page.
  - index rows linked to this page that the draft could not place, and engravings with no
    destination.

    python oco/page_draft.py <page> [--out oco/drafts/pNNNN.json] [--quiet]

Read-only (DB and PDF). Writes the draft JSON (default oco/drafts/p<NNNN>.json) and prints a summary.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from types import SimpleNamespace

import fitz
from sqlalchemy import text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from _db import engine  # noqa: E402
from oco_sigla import SUBJECT_WORDS, load_saints, targets  # noqa: E402
from resolve_oco_index import REF, REF_LINE, SIGLUM_SOURCE, incipit_test  # noqa: E402
import oco_pages  # noqa: E402

WHITE = 0xFFFFFF
# left-margin hour labels (spaces removed) → index hour codes
HOUR_LABELS = {"I&IIVesp.": ["1V", "2V"], "Vesp.I&II": ["1V", "2V"], "(II)Vesp.": ["2V"], "IIVesp.": ["2V"],
               "IVesp.": ["1V"], "Vesp.": ["V"], "Laudes": ["L"], "Off.lect.": ["Ol"], "Tertia": ["T"],
               "Sexta": ["S"], "Nona": ["N"], "Hor.med.": ["Hm"], "Compl.": ["C"], "Inv.": ["Inv"], "Inv,": ["Inv"]}
RUNNING_HEADS = {"PROPRIUM DE TEMPORE", "PROPRIUM DE SANCTIS", "COMMUNIA", "ORDO CANTUS OFFICII",
                 "OFFICIUM DEFUNCTORUM", "PSALTERIUM", "APPENDIX"}
MODE = re.compile(r"^(?:[1-8]\*{0,2}(?:-[1-8])?[a-g]?\d?t?|[CDE](?:/[\w*]+)?[a-g]?\d?|per\.)$")
DEST = re.compile(r"^([ARI])\[(.*)\]$")


def norm_code(s):
    return re.sub(r"\s+", "", s or "")


def lines_of(pg):
    """Every text line: dict(y, x, text, font, size, white, music)."""
    out = []
    for b in pg.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            spans = [sp for sp in ln["spans"] if sp["text"].strip()]
            if not spans:
                continue
            white = spans[0]["color"] == WHITE
            keep = [sp for sp in spans if (sp["color"] == WHITE) == white]
            out.append({"y": round(ln["bbox"][1], 1), "y1": round(ln["bbox"][3], 1), "x": round(ln["bbox"][0], 1),
                        "text": " ".join(sp["text"].strip() for sp in keep), "font": keep[0]["font"],
                        "size": round(keep[0]["size"], 1), "white": white,
                        "music": keep[0]["font"].startswith("gre")})
    return out


def layout(pg):
    """(items, engravings). items: reading-order text outside the staves; engravings: dicts with y, text,
    refs, cao, ref_line, siglum, mode."""
    ls = lines_of(pg)
    music = [l for l in ls if l["music"]]
    # a staff band: from the neume line to the lyrics below it
    bands = [(m["y"] - 4, m["y1"] + 26) for m in music if m["size"] > 20]

    def in_staff(l):
        mid = (l["y"] + l["y1"]) / 2
        return any(a <= mid <= b for a, b in bands)

    ls.sort(key=lambda l: (l["y"], l["x"]))
    engr, items = [], []
    whites = [l for l in ls if l["white"]]
    # white text: an engraving's full text; consecutive white lines (wrapped) join
    for l in whites:
        if engr and l["y"] - engr[-1]["_y1"] < 14 and l["y"] > engr[-1]["y"]:
            engr[-1]["text"] += " " + l["text"]
            engr[-1]["_y1"] = l["y1"]
        else:
            engr.append({"y": l["y"], "_y1": l["y1"], "text": l["text"]})
    for i, e in enumerate(engr):
        nxt = engr[i + 1]["y"] if i + 1 < len(engr) else 10 ** 4
        near = [l for l in ls if not l["white"] and not l["music"] and e["y"] - 3 <= l["y"] < min(e["y"] + 80, nxt)]
        ref = next((l for l in near if REF_LINE.search(l["text"]) or re.search(r"\bCAO\b|LHym \d|tr\. man", l["text"])), None)
        e["ref_line"] = ref["text"] if ref else None
        e["refs"], e["cao"] = defaultdict(list), None
        for m in REF.finditer(e["ref_line"] or ""):
            nums = re.findall(r"\d+", m.group(2))
            if m.group(1) == "CAO":
                e["cao"] = nums[0]
            elif m.group(1) in SIGLUM_SOURCE:
                e["refs"][SIGLUM_SOURCE[m.group(1)]] += nums
        e["refs"] = dict(e["refs"])
        sig = [l["text"] for l in near if 110 <= l["x"] < 150 and l["size"] < 12]
        e["siglum"] = " ".join(sig) or None
        md = [l["text"] for l in near if 150 <= l["x"] < 190 and l["font"] == "Aster-Med" and MODE.match(l["text"])]
        e["mode"] = md[0] if md else None
        e["left"] = " ".join(l["text"] for l in near if l["x"] < 110 and l["size"] < 12) or None
        # white text at the page foot with no mode/siglum/staff below it: the engraving itself begins on the
        # NEXT page (p548 'Humiliavit', p265 'Postulavi') — it is that page's row
        e["overflow"] = (e["mode"] is None and e["siglum"] is None and e["y"] > 520
                         and not any(m["y"] > e["y"] for m in music if m["size"] > 20))
        del e["_y1"]
    used_y = {round(e["y"]) for e in engr}
    for l in ls:
        if l["white"] or l["music"] or l["size"] > 30 or l["font"].startswith("CMR"):
            if l["font"].startswith("CMR") and l["x"] < 40:
                items.append({"y": l["y"], "kind": "margin-number", "text": l["text"]})
            continue
        if l["text"] in RUNNING_HEADS or (re.fullmatch(r"\d+", l["text"]) and l["y"] < 60):
            continue
        if in_staff(l) and l["x"] >= 150 and not (l["font"] == "Aster-Med" and MODE.match(l["text"])):
            continue  # lyrics, T.P. markers inside the staff
        if REF_LINE.search(l["text"]) or re.search(r"\bCAO \d", l["text"]):
            continue  # ref lines are reported on their engraving
        if 150 <= l["x"] < 190 and l["font"] == "Aster-Med" and MODE.match(l["text"]):
            continue  # modes are reported on their engraving
        kind = ("hour" if l["x"] < 110 and norm_code(l["text"]) in HOUR_LABELS else
                "heading" if l["font"] == "Aster-Med" else
                "siglum" if 110 <= l["x"] < 150 else
                "rubric" if l["font"].endswith("Ita") else "text")
        items.append({"y": l["y"], "x": l["x"], "kind": kind, "text": l["text"]})
    for e in engr:
        items.append({"y": e["y"], "kind": "ENGRAVING", "text": e["text"][:80]})
    items.sort(key=lambda it: (it["y"], it.get("x", 0)))
    # join a siglum / hour label with the cue printed on the same line
    merged = []
    for it in items:
        if merged and it["kind"] in ("text", "rubric") and abs(it["y"] - merged[-1]["y"]) < 3 \
                and merged[-1]["kind"] in ("hour", "siglum", "cue"):
            prev = merged[-1]
            prev.setdefault("cue", "")
            prev["cue"] = (prev["cue"] + " " + it["text"]).strip()
            continue
        merged.append(it)
    return merged, engr, used_y


def page_links(doc, pg):
    """[(y, cue text, kind, target)] kind 'xref' (named dest) or 'hymn' (gregobase id)."""
    out = []
    for ln in pg.get_links():
        t = pg.get_textbox(ln["from"]).strip().replace("\n", " ")
        if ln["kind"] == fitz.LINK_URI:
            m = re.search(r"chant\.php\?id=(\d+)", ln.get("uri", ""))
            if m:
                out.append((round(ln["from"].y0, 1), t, "hymn", int(m.group(1))))
        elif ln.get("nameddest"):
            out.append((round(ln["from"].y0, 1), t, "xref", ln["nameddest"]))
    return sorted(out)


class Book:
    def __init__(self, c, doc):
        self.c, self.doc = c, doc
        self.saints = load_saints(c)
        self.rows = {r.id: r for r in c.execute(text(
            "SELECT row_id, id, section_type, incipit, page, day_code, hour_code, place_code, notes, chant_uuid, "
            "chant_group_id, match_status FROM chant_indices WHERE book='OCO'")).all()}
        lt = json.load(open(os.path.join(HERE, "index", "link_targets.json"), encoding="utf-8"))
        self.dest_rows = defaultdict(list)  # dest name → index ids linking to it
        for i, (_, _, d) in lt.items():
            if d:
                self.dest_rows[d].append(int(i))
        self.invit = sorted(i for i, r in self.rows.items() if r.section_type == "invitatorium")
        self.names = doc.resolve_names()
        self.dest_page = {n: oco_pages.printed(d["page"] + 1) for n, d in self.names.items() if d.get("page", -1) >= 0}
        self.by_page = defaultdict(list)
        for n, p in self.dest_page.items():
            if DEST.match(n):
                self.by_page[p].append(n)

    def own_rows(self, dest):
        """Index rows whose codes ARE this destination (its own assignment), most specific first."""
        m = DEST.match(dest)
        kind, body = m.group(1), m.group(2)
        if kind == "I":
            n = int(body)
            return [self.rows[self.invit[n]]] if n < len(self.invit) else []
        day, hour, place = (body.split(",") + ["", ""])[:3]
        place = "" if (kind == "R" and place == "R") else place
        linked = [self.rows[i] for i in self.dest_rows.get(dest, [])]

        def same(r, loose=False):
            d = norm_code(r.day_code)
            ok_day = d == norm_code(day) or (loose and (d.startswith(norm_code(day)) or norm_code(day).startswith(d)))
            return ok_day and (r.hour_code or "") == hour and norm_code(r.place_code) == norm_code(place)
        exact = [r for r in linked if same(r)] or [r for r in linked if same(r, True)]
        if exact:
            return exact
        stype = {"A": "antiphona", "R": "responsorium breve"}[kind]
        return [r for r in self.rows.values() if r.section_type == stype and same(r)]

    def toc(self, p):
        return self.c.execute(text("SELECT level, text, printed_page FROM book_toc WHERE book='OCO' AND "
                                   "CAST(printed_page AS UNSIGNED) <= :p ORDER BY idx DESC LIMIT 3"), {"p": p}).all()


def spec_rows(r, kind, why, engr=None, ref_page=None, ref_book=None, book=None):
    ts, err = targets(r, book.saints)
    base = {"incipit": r.incipit, "kind": kind, "index_id": r.id,
            "chant_uuid": r.chant_uuid, "chant_group_id": r.chant_group_id, "draft": why}
    if engr:
        base.update(mode=engr.get("mode"), text=engr["text"][:200])
    if ref_page:
        base.update(ref_page=ref_page, ref_book=ref_book)
    if err:
        return [{**base, "service": None, "part": None, "draft": f"{why}; codes not placeable: {err}"}]
    out = []
    for t in ts:
        note = {}
        if t["option_txt"] and any(SUBJECT_WORDS.match(o) for o in t["option_txt"].split(", ")):
            note = {"draft": base["draft"] + f"; SUBJECT QUALIFIER {t['option_txt']!r}: put it in a sub-epoch "
                                             f"of {t['slug']} (contract: Sub-epochs), not option_txt"}
        out.append({**base, **note, "lit_epoch_slug": t["slug"], "service": t["service"], "part": t["part"],
                    "wkday": t["wkday"], "wknum_mod_2": t["wknum_mod_2"], "wknum_mod_4": t["wknum_mod_4"],
                    "rank_codes": t["rank_codes"], "cycle_sun": t["cycle_sun"], "cycle_wkday": t["cycle_wkday"],
                    "option_num": t["option_num"] or (1 if not t["option_txt"] else None),
                    "option_txt": t["option_txt"]})
    return out


def draft(book, p):
    pg = oco_pages.page(book.doc, p)
    if pg is None:
        return {"page": str(p), "error": "no such printed page in the PDF"}
    items, engr, _ = layout(pg)
    links = page_links(book.doc, pg)
    rows, notes = [], []
    own_dests = list(book.by_page.get(p, []))
    # engravings whose hidden text sits at the foot of the previous page but whose staff begins here
    prev = oco_pages.page(book.doc, p - 1)
    carried = [dict(e, carried_from=p - 1, overflow=False) for e in (layout(prev)[1] if prev else []) if e["overflow"]]
    if carried:
        engr = carried + engr
        own_dests = list(book.by_page.get(p - 1, [])) + own_dests
        notes.append(f"{len(carried)} engraving(s) carried from p{p - 1}: hidden text at its foot, staff begins on this page")
    # 1. engravings ↔ their own destinations
    taken = {k for k, e in enumerate(engr) if e["overflow"]}  # begins on the next page: not ours
    for k in taken:
        notes.append(f"engraving y={engr[k]['y']:.0f} {engr[k]['text'][:40]!r}: only its hidden text is here, the staff "
                     f"begins on p{p + 1} — that page's row")
    for dest in own_dests:
        own = book.own_rows(dest)
        if not own:
            notes.append(f"destination {dest}: no index row has these codes")
            continue
        hit = None
        for k, e in enumerate(engr):
            if k not in taken and incipit_test(own[0].incipit)(e["text"]):
                hit = k
                break
        if hit is None:
            if dest not in book.by_page.get(p, []):
                continue  # a previous-page destination whose engraving stayed on that page
            notes.append(f"destination {dest} (index #{own[0].id} {own[0].incipit!r}): no engraving on this page "
                         "starts with that incipit")
            continue
        taken.add(hit)
        e = engr[hit]
        e["dest"] = dest
        e["index_ids"] = [r.id for r in own]
        for r in own:
            linked = "" if str(r.page) == str(p) else f"; index links p{r.page}"
            rows += spec_rows(r, "engraved", f"dest {dest} → index #{r.id} ({r.day_code} | {r.hour_code} | "
                                             f"{r.place_code}){linked}", engr=e, book=book)
    for k, e in enumerate(engr):
        if k not in taken:
            notes.append(f"engraving y={e['y']:.0f} {e['text'][:50]!r}: no named destination matched — identify and "
                         "assign it from the page")
    # 2. day codes the page is about (own destinations here and on the previous page)
    page_days = {norm_code(DEST.match(d).group(2).split(",")[0]) for q in (p - 1, p) for d in book.by_page.get(q, [])
                 if DEST.match(d) and DEST.match(d).group(1) != "I"}
    hour_at = []  # (y, hour codes) from the left-margin labels
    for it in items:
        if it["kind"] == "hour":
            hour_at.append((it["y"], HOUR_LABELS[norm_code(it["text"])]))

    def hours_for(y):
        hs = [h for (yy, h) in hour_at if yy <= y + 3]
        return hs[-1] if hs else None

    def day_fits(r):
        ds = {norm_code(x) for x in re.split(r"\s+", r.day_code or "")} | {norm_code(r.day_code)}
        return bool(ds & page_days)

    # 3. cue links
    for y, cue, kind, target in links:
        hs = hours_for(y)
        if kind == "hymn":
            cands = [r for r in book.rows.values() if r.chant_uuid == f"gregobase:{target}" and r.section_type == "hymnus"]
            lh = re.search(r"LHym (\d+)", cue)
            fit = [r for r in cands if day_fits(r) and (not hs or any(h in (r.hour_code or "").split() or
                                                                      (h == "V" and "V" in (r.hour_code or ""))
                                                                      for h in hs))]
            why = f"hymn cue {cue!r} (gregobase:{target}) at y={y:.0f}, hour {hs}"
            if not fit:
                notes.append(f"{why}: no hymn index row with this page's day codes {sorted(page_days)}; "
                             f"index rows for this hymn: {[(r.id, r.day_code, r.hour_code) for r in cands][:8]}")
                rows.append({"incipit": re.sub(r"\s*\(LHym.*", "", cue), "kind": "xref", "ref_book": "LIBER_HYMNARIUS",
                             "ref_page": int(lh.group(1)) if lh else None, "chant_uuid": f"gregobase:{target}",
                             "service": None, "part": "hymn", "draft": why + "; slot to be read from the page"})
                continue
            for r in fit:
                lhp = re.search(r"LHym (\d+)", r.notes or "")
                rows += spec_rows(r, "xref", f"{why} → index #{r.id} ({r.day_code} | {r.hour_code})",
                                  ref_page=int(lhp.group(1)) if lhp else (int(lh.group(1)) if lh else None),
                                  ref_book="LIBER_HYMNARIUS", book=book)
            continue
        if not DEST.match(target):
            continue  # section anchors (ADV5, SCT208 …)
        tp = book.dest_page.get(target)
        own = book.own_rows(target)
        own_ids = {r.id for r in own}
        reuse = [book.rows[i] for i in book.dest_rows.get(target, []) if i not in own_ids]
        fit = [r for r in reuse if day_fits(r)] or reuse
        why = f"xref cue {cue!r} at y={y:.0f} → {target} p{tp}"
        if not fit:
            src = own[0] if own else None
            notes.append(f"{why}: no index row reuses that engraving for this page; slot to be read from the page")
            rows.append({"incipit": src.incipit if src else cue, "kind": "xref", "ref_book": "OCO", "ref_page": tp,
                         "index_id": src.id if src else None, "chant_uuid": src.chant_uuid if src else None,
                         "chant_group_id": src.chant_group_id if src else None, "service": None, "part": None,
                         "draft": why})
            continue
        src = next((o for o in own if o.chant_uuid or o.chant_group_id), None)
        for r in fit:
            xs = spec_rows(r, "xref", f"{why} → index #{r.id} ({r.day_code} | {r.hour_code} | {r.place_code})",
                           ref_page=tp, ref_book="OCO", book=book)
            for x in xs:  # the cue IS the target engraving: borrow its identity when the reusing row has none
                if not (x["chant_uuid"] or x["chant_group_id"]) and src:
                    x.update(chant_uuid=src.chant_uuid, chant_group_id=src.chant_group_id,
                             draft=x["draft"] + f"; identity from the engraving's own index #{src.id}")
            rows += xs
    # 4. index rows linked to this page that nothing above placed
    placed = {x.get("index_id") for x in rows}
    for r in book.rows.values():
        if str(r.page) == str(p) and r.id not in placed:
            notes.append(f"index #{r.id} {r.incipit!r} ({r.day_code} | {r.hour_code} | {r.place_code}) links here but "
                         "was not placed: a reuse cued on another page, an index error, or a row to add")
    # 5. what is already loaded for this page (legacy index pass or an earlier page spec)
    loaded = [dict(x._mapping) for x in book.c.execute(text(
        "SELECT l.text_id, l.lit_epoch_slug, CONCAT(sp.service_code,'.',sp.part_code) svc, l.wkday, l.wknum_mod_2, "
        "l.wknum_mod_4, l.rank_code, l.cycle_sun, l.option_num, l.option_txt, l.chant_uuid, l.chant_group_id, "
        "LEFT(l.notes, 60) notes FROM lit_part_sources l JOIN service_part sp USING (part_id) WHERE l.book='OCO' "
        "AND l.printed_page_num=:p ORDER BY sp.display_order, l.wkday"), {"p": str(p)})]
    toc = book.toc(p)
    return {"page": str(p), "toc_in_force": [f"L{t.level} {t.text} p{t.printed_page}" for t in reversed(toc)],
            "reading": items, "engravings": engr, "links": [list(x) for x in links], "rows": rows,
            "notes": notes, "loaded_on_this_page": loaded}


def summary(d):
    out = [f"PAGE {d['page']}   TOC: {' | '.join(d['toc_in_force'])}", "READING:"]
    for it in d["reading"]:
        out.append(f"  {it['y']:6.0f} {it['kind']:<14} {it['text'][:70]}" + (f"  ⇒ {it['cue'][:60]}" if it.get("cue") else ""))
    out.append("ENGRAVINGS:")
    for e in d["engravings"]:
        out.append(f"  y={e['y']:.0f} {e.get('left') or ''} [{e['siglum']}] mode {e['mode']} dest {e.get('dest')} "
                   f"index {e.get('index_ids')}\n      {e['text'][:110]}\n      ref: {e['ref_line']}")
    out.append(f"PROPOSED ROWS ({len(d['rows'])}):")
    for r in d["rows"]:
        out.append(f"  {r['kind']:<8} {str(r.get('lit_epoch_slug')):<22} {r.get('service')}.{r.get('part')} "
                   f"wd={r.get('wkday')} m2={r.get('wknum_mod_2')} m4={r.get('wknum_mod_4')} rk={r.get('rank_codes')} "
                   f"cs={r.get('cycle_sun')} opt={r.get('option_num')} {r.get('option_txt') or ''} "
                   f"{r['incipit']!r} → {r.get('chant_uuid') or (r.get('chant_group_id') and 'group:%s' % r['chant_group_id']) or 'NO IDENTITY'}"
                   f"\n      ({r['draft']})")
    out.append("NOTES:")
    out += [f"  - {n}" for n in d["notes"]] or ["  none"]
    out.append(f"ALREADY LOADED with printed_page_num={d['page']} ({len(d['loaded_on_this_page'])}):")
    for x in d["loaded_on_this_page"]:
        out.append(f"  text_id {x['text_id']} {x['lit_epoch_slug']} {x['svc']} wd={x['wkday']} opt={x['option_num']} "
                   f"{x['option_txt'] or ''} {x['chant_uuid'] or 'group:%s' % x['chant_group_id']}  [{x['notes']}]")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page", type=int)
    ap.add_argument("--out")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    doc = fitz.open(os.path.join(HERE, "oco.pdf"))
    with engine().connect() as c:
        d = draft(Book(c, doc), a.page)
    out = a.out or os.path.join(HERE, "drafts", f"p{a.page:04d}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False, default=str)
    if not a.quiet:
        print(summary(d))
    print(f"DRAFT: {out}")


if __name__ == "__main__":
    main()
