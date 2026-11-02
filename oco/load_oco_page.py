#!/usr/bin/env python
"""load_oco_page.py — load ONE OCO page spec into lit_part_sources (stage `pages`).

Contract: oco/specs/README.md. The PAGE is the authority (user, 2026-10-23): a page spec records every
assignment the page prints — engravings that begin on it and the cross-reference cues printed on it
(hymn cues "Name (LHym N)", "Ut in hebd. I.", "Vel: X", "X, de Communi …"). Rows land with
book = assignment_authority_code = 'OCO', printed_page_num = this page, notes starting 'OCO p<page>'
(the page owns them), ref_book/ref_page_num for cross-references.

Rows loaded earlier by the index pass (oco/load_oco_lps.py, notes 'OCO index #…') are LEGACY: a page
spec ADOPTS a legacy row with the same slot + chant (rewrites its page, option and notes) and REPLACES a
legacy row holding the same slot + option with a different chant. Legacy rows no page touches stay
until the end-of-sweep review (`--legacy-report`).

    python oco/load_oco_page.py --spec oco/specs/p0932.json --dry-run   # resolve + show, no writes
    python oco/load_oco_page.py --spec oco/specs/p0932.json             # write (also prunes this page's stale rows)
    python oco/load_oco_page.py --spec oco/specs/p0932.json --verify    # DB == spec for this page?
    python oco/load_oco_page.py --legacy-report                         # legacy rows no page has adopted

Exit codes: 0 ok · 1 spec/resolve error · 3 spec carries open questions (not loaded)
            · 4 dependency (a cited OCO page has no page-spec rows yet) · 5 verify FAIL.
The last stdout line is always a one-line JSON summary for the batch log.
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
from index_util import condense  # noqa: E402
from resolve_oco_index import lyrics  # noqa: E402

BOOK = AUTH = "OCO"
SLOT = ("jurisdiction", "lit_epoch_slug", "part_id", "wkday", "wknum_mod_2", "wknum_mod_4", "rank_code",
        "cycle_sun", "cycle_wkday")
DAY_FIELDS = ("wkday", "wknum_mod_2", "wknum_mod_4", "cycle_sun", "cycle_wkday")
OFFICE_PARTS = {"hymn": {"hy"}, "invan": {"an", "iv", "in"}, "resp": {"rb", "re"}}


class SpecError(Exception):
    pass


class DependencyError(Exception):
    pass


def owner(notes):
    """'p932' for a page-owned row, 'legacy' for an index-pass row."""
    m = re.match(r"OCO p(\d+)(?::|$)", notes or "")  # legacy Lent xrefs read "OCO p183 'Infra …" — not page-owned
    return f"p{m.group(1)}" if m else "legacy"


def norm_mode(m):
    m = (m or "").strip().lower()
    d = re.match(r"(\d)", m)
    return d.group(1) if d else (m[:1] if m else None)


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    for k in ("page", "page_kind"):
        if k not in spec:
            raise SpecError(f"spec missing '{k}'")
    spec["page"] = str(spec["page"])
    for k in ("rows", "questions", "inherits", "flags"):
        spec.setdefault(k, [])
    if spec["page_kind"] not in ("assign", "continuation_only", "no_chant"):
        raise SpecError(f"page_kind must be assign|continuation_only|no_chant, got {spec['page_kind']!r}")
    if spec["page_kind"] != "assign" and spec["rows"]:
        raise SpecError(f"page_kind={spec['page_kind']} but rows are present")
    return spec


class Resolver:
    def __init__(self, c):
        self.c = c
        self.parts = {(s, p): i for i, s, p in c.execute(text("SELECT part_id, service_code, part_code FROM service_part"))}
        self.ranks = {r[0] for r in c.execute(text("SELECT rank_code FROM p_lit_rank"))}
        self._epoch = {}
        self.deps = []  # cues whose target page has no page-spec rows yet (unit → blocked_dep)

    def epoch_title(self, slug):
        if slug is None:
            return "Psalter"
        if slug not in self._epoch:
            r = self.c.execute(text("SELECT title FROM lit_epoch WHERE slug=:s"), {"s": slug}).first()
            if not r:
                raise SpecError(f"lit_epoch slug {slug!r} does not exist")
            self._epoch[slug] = r[0] or slug
        return self._epoch[slug]

    def identity(self, r, i):
        """(chant_uuid, chant_group_id, how)."""
        if r.get("chant_uuid") or r.get("chant_group_id"):
            return r.get("chant_uuid"), (None if r.get("chant_uuid") else r.get("chant_group_id")), "explicit"
        if r.get("index_id"):
            x = self.c.execute(text("SELECT chant_uuid, chant_group_id FROM chant_indices WHERE book='OCO' AND id=:i"),
                               {"i": r["index_id"]}).first()
            if not x:
                raise SpecError(f"row {i}: index_id {r['index_id']} is not an OCO chant_indices id")
            if x.chant_uuid or x.chant_group_id:
                return x.chant_uuid, (None if x.chant_uuid else x.chant_group_id), f"index #{r['index_id']}"
        if r.get("ref_book") == "OCO":
            # a cue to another OCO engraving: the identity is whatever that page's spec loaded for it
            tp = str(r["ref_page"])
            hits = self.c.execute(text(
                "SELECT DISTINCT chant_uuid, chant_group_id, display_name FROM lit_part_sources WHERE book='OCO' "
                "AND printed_page_num=:p AND ref_page_num IS NULL AND notes LIKE :own"),
                {"p": tp, "own": f"OCO p{tp}%"}).all()
            if not hits:
                self.deps.append(f"row {i} {r['incipit']!r}: cites p{tp}, which no page spec has loaded yet")
                return None, None, f"waits on p{tp}"
            key = condense(r["incipit"])
            ids = {(h.chant_uuid, h.chant_group_id) for h in hits
                   if condense(h.display_name.split(" — ")[-1]).startswith(key[:12])}
            if len(ids) == 1:
                u, g = ids.pop()
                return u, (None if u else g), f"from p{tp}'s spec"
            if not ids:
                raise SpecError(f"row {i} {r['incipit']!r}: p{tp} is loaded but has no engraving with that incipit")
            raise SpecError(f"row {i} {r['incipit']!r}: p{tp} has {len(ids)} identities for that incipit: give chant_uuid")
        if r.get("allow_unresolved"):
            return None, None, "unresolved"
        raise SpecError(f"row {i} {r['incipit']!r}: no identity (give chant_uuid / chant_group_id, or "
                        "allow_unresolved + a flag)")

    def check(self, uuid, group, r):
        """Trust-but-verify the identity against the engraving's printed text and mode → (summary, warnings)."""
        if r.get("ref_book") == "LIBER_HYMNARIUS" or not (uuid or group):
            return None, []
        if uuid and uuid.startswith("gregobase:"):
            ids = [int(uuid.split(":")[1])]
        elif group:
            ids = [g for (g,) in self.c.execute(text("SELECT CAST(origin_id AS UNSIGNED) FROM chants "
                                                     "WHERE chant_group_id=:g AND origin_source='GREGOBASE'"),
                                                {"g": group})]
        else:
            return f"{uuid} (not gregobase: not checked)", []
        gs = self.c.execute(text("SELECT id, incipit, mode, `office-part` op, gabc FROM gregobase_chants WHERE id IN :i")
                            .bindparams(__import__("sqlalchemy").bindparam("i", expanding=True)), {"i": ids or [0]}).all()
        if not gs:
            return None, [f"⚠ CHECK {uuid or 'group:%s' % group}: no gregobase chant"]
        warn = []
        want = condense(r.get("text") or r["incipit"]).replace("oe", "ae")[:24]
        texts = [lyrics(g.gabc).replace("oe", "ae") for g in gs]
        if want and not any(t.startswith(want[:min(len(want), len(t))]) for t in texts if t):
            warn.append(f"⚠ CHECK {uuid or 'group:%s' % group}: sung text starts {texts[0][:30]!r}, page "
                        f"{(r.get('text') or r['incipit'])[:30]!r}")
        pm = norm_mode(r.get("mode"))
        modes = {norm_mode(g.mode) for g in gs if g.mode}
        if pm and pm.isdigit() and modes and pm not in modes:
            warn.append(f"⚠ CHECK {uuid or 'group:%s' % group}: gregobase mode {sorted(modes)} ≠ printed {r.get('mode')!r}")
        ops = OFFICE_PARTS.get(r["part"], {"an"} if r["part"].startswith("ant") else None)
        if ops and not any((g.op or "") in ops for g in gs):
            warn.append(f"⚠ CHECK {uuid or 'group:%s' % group}: office-part {sorted({g.op for g in gs})} for {r['part']}")
        g = gs[0]
        return f"{g.incipit!r} m{g.mode} {g.op}" + (f" (+{len(gs) - 1} in group)" if len(gs) > 1 else ""), warn


def build_rows(spec, res):
    page = spec["page"]
    if not res.c.execute(text("SELECT 1 FROM books WHERE book='OCO' AND printed_page_num=:p"), {"p": page}).first():
        raise SpecError(f"books has no OCO page {page}")
    out, notes, unacked = [], [], []
    for i, r in enumerate(spec["rows"], start=1):
        for k in ("incipit", "kind", "service", "part"):
            if not r.get(k):
                raise SpecError(f"row {i} missing '{k}'")
        if r["kind"] not in ("engraved", "xref"):
            raise SpecError(f"row {i}: kind must be engraved|xref")
        if r["kind"] == "xref" and not (r.get("ref_page") and r.get("ref_book") in ("OCO", "LIBER_HYMNARIUS")):
            raise SpecError(f"row {i}: xref needs ref_book (OCO | LIBER_HYMNARIUS) and ref_page")
        if r["kind"] == "engraved" and r.get("ref_page"):
            raise SpecError(f"row {i}: engraved row must not carry ref_page")
        if r.get("ref_book") == "OCO" and not res.c.execute(
                text("SELECT 1 FROM books WHERE book='OCO' AND printed_page_num=:p"), {"p": str(r["ref_page"])}).first():
            raise SpecError(f"row {i}: ref_page {r['ref_page']} is not an OCO page")
        pid = res.parts.get((r["service"], r["part"]))
        if pid is None:
            raise SpecError(f"row {i}: no service_part {r['service']}.{r['part']}")
        slugs = r.get("lit_epoch_slugs") or [r.get("lit_epoch_slug")]
        for s in slugs:
            res.epoch_title(s)
        ranks = r.get("rank_codes") or [r.get("rank_code")]
        for k in ranks:
            if k is not None and k not in res.ranks:
                raise SpecError(f"row {i}: unknown rank_code {k}")
        wkdays = r.get("wkdays") or [r.get("wkday")]
        uuid, group, how = res.identity(r, i)
        summ, warn = res.check(uuid, group, r)
        if summ:
            notes.append(f"row {i}: ✓? {uuid or 'group:%s' % group} = {summ}")
        acked = r.get("verified_despite", [])
        for w in warn:
            ok = any(a in w for a in acked)
            notes.append(f"row {i}: {w}" + ("  [acknowledged in spec]" if ok else ""))
            if not ok:
                unacked.append(f"row {i}")
        if how == "unresolved":
            notes.append(f"row {i}: ⚠ no identity (allow_unresolved) — {r['incipit']!r}")
        note = " | ".join(x for x in (r.get("rubric"), r.get("notes")) if x)
        for slug in slugs:
            title = res.epoch_title(slug)
            for wk in wkdays:
                for rk in ranks:
                    out.append(dict(
                        src=f"row {i}", how=how, incipit=r["incipit"], jurisdiction=r.get("jurisdiction", "UNIVERSAL"),
                        lit_epoch_slug=slug, part_id=pid, svc=f"{r['service']}.{r['part']}", wkday=wk,
                        wknum_mod_2=r.get("wknum_mod_2"), wknum_mod_4=r.get("wknum_mod_4"), rank_code=rk,
                        cycle_sun=r.get("cycle_sun"), cycle_wkday=r.get("cycle_wkday"),
                        option_num=r.get("option_num"), option_txt=r.get("option_txt"),
                        chant_uuid=uuid, chant_group_id=group, printed_page_num=page,
                        ref_page_num=r.get("ref_page"), ref_book=r.get("ref_book"),
                        notes=(f"OCO p{page}: " + note)[:500] if note else f"OCO p{page}",
                        display_name=f"{title} — {r['service']}.{r['part']} — {r['incipit']}"[:300]))
    return out, notes, unacked


def ident(x):
    return x["chant_uuid"] or f"group:{x['chant_group_id']}"


def plan(c, rows, page):
    """Decide, per spec row, adopt / insert / replace, and number open options. Returns (actions, stale, errors)."""
    existing = defaultdict(list)
    for e in c.execute(text(
            "SELECT text_id, option_num, chant_uuid, chant_group_id, notes, printed_page_num, " + ", ".join(SLOT) +
            " FROM lit_part_sources WHERE book='OCO' AND assignment_authority_code='OCO' "
            "AND translation_source_code IS NULL")).mappings():
        existing[tuple(e[k] for k in SLOT)].append(dict(e, ident=e["chant_uuid"] or f"group:{e['chant_group_id']}",
                                                         owner=owner(e["notes"])))
    me = f"p{page}"
    actions, errors, touched = [], [], set()
    # legacy rows by chant + part + day fields: a page that moves a chant into a sub-epoch (a subject qualifier the
    # index pass stored as option_txt on the parent Common) adopts the parent's legacy row instead of duplicating it
    legacy_by_chant = defaultdict(list)
    for es in existing.values():
        for e in es:
            if e["owner"] == "legacy":
                legacy_by_chant[(e["ident"], e["part_id"], e["jurisdiction"]) + tuple(e[k] for k in DAY_FIELDS + ("rank_code",))].append(e)
    chains = {}

    def ancestors(slug):
        if slug not in chains:
            chain, cur = [], slug
            while cur:
                r = c.execute(text("SELECT parent_slug FROM lit_epoch_tree WHERE child_slug=:s"), {"s": cur}).first()
                cur = r[0] if r and r[0] not in chain else None
                if cur:
                    chain.append(cur)
            chains[slug] = chain
        return chains[slug]
    # this page's own rows are re-derived from the spec: they never block it
    by_slot = defaultdict(list)
    for x in rows:
        if x["how"].startswith("waits"):
            actions.append(("waits", x, None))
            continue
        by_slot[tuple(x[k] for k in SLOT)].append(x)
    for slot, xs in by_slot.items():
        others = [e for e in existing[slot] if e["owner"] != me]
        fixed = [x for x in xs if x["option_num"] is not None]
        nums = [x["option_num"] for x in fixed]
        if len(nums) != len(set(nums)):
            errors.append(f"{xs[0]['svc']} {slot[1]}: two spec rows share option {nums}")
        # open options (option_num null) take the next free number after everything else in the slot
        taken = set(nums) | {e["option_num"] for e in others if e["owner"] != "legacy"}
        nxt = max(taken | {0}) + 1
        for x in xs:
            if x["option_num"] is None:
                x["option_num"] = nxt
                nxt += 1
        for x in xs:
            same = [e for e in existing[slot] if e["ident"] == ident(x)]
            mine = [e for e in same if e["owner"] in (me, "legacy")]
            foreign = [e for e in same if e["owner"] not in (me, "legacy")]
            if foreign:
                errors.append(f"{x['src']} {x['svc']} {slot[1]}: this chant is already in the slot, loaded by "
                              f"{foreign[0]['owner']} (text_id {foreign[0]['text_id']}): one page must own it")
                continue
            clash = [e for e in existing[slot] if e["option_num"] == x["option_num"] and e["ident"] != ident(x)
                     and e["text_id"] not in {m["text_id"] for m in mine}]
            for e in clash:
                if e["owner"] not in (me, "legacy"):
                    errors.append(f"{x['src']} {x['svc']} {slot[1]} option {x['option_num']}: held by "
                                  f"{e['ident']} from {e['owner']} (text_id {e['text_id']}) — set option_num")
            moved = [] if mine else [
                e for e in legacy_by_chant[(ident(x), x["part_id"], x["jurisdiction"]) + tuple(x[k] for k in DAY_FIELDS + ("rank_code",))]
                if e["lit_epoch_slug"] in ancestors(x["lit_epoch_slug"]) and e["text_id"] not in touched]
            if mine:
                t = mine[0]
                touched.add(t["text_id"])
                actions.append(("adopt" if t["owner"] == "legacy" else "keep", x, t))
            elif moved:
                touched.add(moved[0]["text_id"])
                actions.append(("adopt-move", x, moved[0]))
            else:
                actions.append(("insert", x, None))
            for e in clash:
                if e["owner"] == "legacy" and e["text_id"] not in touched:
                    touched.add(e["text_id"])
                    actions.append(("replace-legacy", x, e))
    stale = [e for es in existing.values() for e in es if e["owner"] == me and e["text_id"] not in touched]
    # an alternative alone in its slot hides nothing only once a primary exists (maybe from a later page)
    gone = {e["text_id"] for k, _, e in actions if k == "replace-legacy"} | {s["text_id"] for s in stale}
    for slot, xs in by_slot.items():
        if not any(x["option_num"] == 1 for x in xs) and not any(
                e["option_num"] == 1 and e["text_id"] not in gone for e in existing[slot]):
            errors.append(f"NOTE {xs[0]['svc']} {slot[1]}: no option 1 in this slot yet (options "
                          f"{sorted(x['option_num'] for x in xs)}) — fine if a later page prints the primary")
    return actions, stale, errors


WRITE_COLS = ("jurisdiction", "lit_epoch_slug", "part_id", "wkday", "wknum_mod_2", "wknum_mod_4", "rank_code",
              "cycle_sun", "cycle_wkday", "option_num", "option_txt", "chant_uuid", "chant_group_id",
              "printed_page_num", "ref_page_num", "ref_book", "notes", "display_name")


def write(c, actions, stale):
    """Apply a plan inside the caller's transaction."""
    if stale:
        c.execute(text("DELETE FROM lit_part_sources WHERE text_id IN (" + ",".join(str(s["text_id"]) for s in stale) + ")"))
    for kind, x, e in actions:
        if kind == "replace-legacy":
            c.execute(text("DELETE FROM lit_part_sources WHERE text_id=:t"), {"t": e["text_id"]})
    # park adopted rows' option numbers first so renumbering inside a slot can't collide
    for kind, x, e in actions:
        if kind in ("adopt", "keep", "adopt-move"):
            c.execute(text("UPDATE lit_part_sources SET option_num=option_num+100 WHERE text_id=:t"), {"t": e["text_id"]})
    upd = ", ".join(f"{k}=:{k}" for k in WRITE_COLS if k not in SLOT and k != "part_id")
    for kind, x, e in actions:
        vals = {k: x[k] for k in WRITE_COLS}
        if kind in ("adopt", "keep"):
            c.execute(text(f"UPDATE lit_part_sources SET {upd} WHERE text_id=:tid"), {**vals, "tid": e["text_id"]})
        elif kind == "adopt-move":
            c.execute(text(f"UPDATE lit_part_sources SET lit_epoch_slug=:lit_epoch_slug, {upd} WHERE text_id=:tid"),
                      {**vals, "tid": e["text_id"]})
        elif kind == "insert":
            c.execute(text(f"INSERT INTO lit_part_sources ({', '.join(WRITE_COLS)}, book, assignment_authority_code, "
                           "original_lang, review_status) VALUES (" + ", ".join(f":{k}" for k in WRITE_COLS)
                           + ", 'OCO', 'OCO', 'la', 'draft')"), vals)


def fmt(x):
    day = "".join(f" {k}={x[k]}" for k in DAY_FIELDS + ("rank_code",) if x[k] is not None)
    ref = f" xref→{x['ref_book']} p{x['ref_page_num']}" if x["ref_page_num"] else " engraved"
    return (f"  [{x['src']}] {x['lit_epoch_slug'] or 'PSALTER'} {x['svc']} opt{x['option_num']}{day}{ref} "
            f"{x['incipit']!r} -> {ident(x)} ({x['how']})" + (f" [{x['option_txt']}]" if x["option_txt"] else ""))


def legacy_report(c):
    rows = c.execute(text(
        "SELECT l.text_id, l.lit_epoch_slug, CONCAT(sp.service_code,'.',sp.part_code) svc, l.option_num, "
        "l.printed_page_num, l.chant_uuid, l.chant_group_id, l.notes FROM lit_part_sources l JOIN service_part sp "
        "USING (part_id) WHERE l.book='OCO' AND l.assignment_authority_code='OCO' AND (l.notes IS NULL OR l.notes NOT LIKE 'OCO p%') "
        "ORDER BY CAST(l.printed_page_num AS UNSIGNED), l.text_id")).all()
    for r in rows:
        print(f"{r.text_id}\tp{r.printed_page_num}\t{r.lit_epoch_slug}\t{r.svc}\topt{r.option_num}\t"
              f"{r.chant_uuid or 'group:%s' % r.chant_group_id}\t{r.notes}")
    print(json.dumps({"legacy_rows": len(rows)}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--legacy-report", action="store_true")
    a = ap.parse_args()
    if a.legacy_report:
        with engine().connect() as c:
            legacy_report(c)
        return 0
    if not a.spec:
        ap.error("--spec is required")
    summary = {"spec": os.path.basename(a.spec), "mode": "verify" if a.verify else "dry-run" if a.dry_run else "load"}
    try:
        spec = load_spec(a.spec)
        summary.update(page=spec["page"], page_kind=spec["page_kind"])
        with engine().connect() as c:
            res = Resolver(c)
            rows, notes, unacked = build_rows(spec, res)
            actions, stale, errors = plan(c, rows, spec["page"])
        for kind, x, e in actions:
            print(fmt(x) + {"insert": "  NEW", "keep": "", "waits": "  WAITS (identity from the cited page)", "adopt": f"  ADOPTS legacy text_id {e['text_id'] if e else ''}",
                            "adopt-move": f"  ADOPTS legacy text_id {e['text_id'] if e else ''} from {(e or {}).get('lit_epoch_slug')} "
                                          f"({(e or {}).get('notes') or ''})",
                            "replace-legacy": f"  REPLACES legacy text_id {e['text_id'] if e else ''} "
                                              f"({e['ident'] if e else ''}, {(e or {}).get('notes') or ''})"}[kind])
        for n in notes:
            print(n)
        for s in stale:
            print(f"  stale: text_id {s['text_id']} {s['lit_epoch_slug']} opt{s['option_num']} {s['ident']} (pruned on load)")
        notes_only = [e for e in errors if e.startswith("NOTE ")]
        errors = [e for e in errors if not e.startswith("NOTE ")]
        for e in notes_only:
            print("  ℹ", e[5:])
        for e in errors:
            print("  ✗", e)
        for d in res.deps:
            print("  DEPENDENCY:", d)
        cnt = defaultdict(int)
        for kind, _, _ in actions:
            cnt[kind] += 1
        summary.update(rows=len(rows), xref=sum(1 for x in rows if x["ref_page_num"]),
                       unresolved=sum(1 for x in rows if not (x["chant_uuid"] or x["chant_group_id"])),
                       **dict(cnt), stale=len(stale), questions=len(spec["questions"]),
                       inherits=len(spec["inherits"]), check_warnings=len(unacked), errors=len(errors))
        if spec["questions"]:
            print("OPEN QUESTIONS (page not loadable until answered):")
            for q in spec["questions"]:
                print("  ?", q if isinstance(q, str) else json.dumps(q, ensure_ascii=False))
        if a.verify:
            bad = [x["src"] for kind, x, _ in actions if kind not in ("keep", "replace-legacy")]
            ok = not bad and not stale
            print(f"VERIFY {'PASS' if ok else 'FAIL'}: {len(rows)} rows, {len(bad)} not loaded as this page's, "
                  f"{len(stale)} stale")
            summary["verify"] = "PASS" if ok else "FAIL"
            print(json.dumps(summary, ensure_ascii=False))
            return 0 if ok else 5
        if errors:
            raise SpecError(f"{len(errors)} slot error(s) above")
        if res.deps:
            raise DependencyError(f"{len(res.deps)} cue(s) wait on unloaded pages: "
                                  + ", ".join(sorted({d.split('cites ')[1].split(',')[0] for d in res.deps})))
        if a.dry_run:
            print(f"DRY-RUN OK: {len(rows)} rows ({cnt['insert']} new, {cnt['adopt'] + cnt['adopt-move']} adopt legacy, "
                  f"{cnt['replace-legacy']} replace legacy, {cnt['keep']} unchanged), {len(stale)} stale")
            print(json.dumps(summary, ensure_ascii=False))
            return 3 if spec["questions"] else 0
        if spec["questions"]:
            print(json.dumps(summary, ensure_ascii=False))
            return 3
        if unacked:
            raise SpecError(f"unacknowledged ⚠ CHECK on {unacked}: fix the chant or add 'verified_despite' after "
                            "checking the engraving")
        with engine(rw=True).begin() as c:
            write(c, actions, stale)
        print(f"LOADED: {cnt['insert']} inserted, {cnt['adopt']} adopted, {cnt['replace-legacy']} legacy replaced, "
              f"{cnt['keep']} refreshed, {len(stale)} stale pruned")
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except DependencyError as e:
        print("DEPENDENCY:", e)
        summary["error"] = f"dependency: {e}"
        print(json.dumps(summary, ensure_ascii=False))
        return 4
    except (SpecError, json.JSONDecodeError) as e:
        print("ERROR:", e)
        summary["error"] = str(e)[:400]
        print(json.dumps(summary, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
