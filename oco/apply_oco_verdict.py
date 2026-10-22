#!/usr/bin/env python
"""apply_oco_verdict.py — director step for one reviewed OCO index-rows verdict:
identity → chant_indices (tools/apply_index_verdict.py), assignment override → oco/index/lps_overrides.json,
then the row's lit_part_sources rows (oco/load_oco_lps.py) and their verify.

    python oco/apply_oco_verdict.py oco/index/resolve/r6128.json             # dry-run of every step
    python oco/apply_oco_verdict.py … --commit [--apply-index-fix]

Exit 0 = applied (or would apply) and verified; non-zero = stop and look (the step's output says why).
An `ambiguous` verdict writes match_status only; raise its question with tools/intake.py raise.
conflicts stage: `option` (+ option_txt) → option-only override, the row loads as the slot's next option;
`hold` → nothing written, raise its question. `assign` (row already identified): only the
`assignment` override + LPS.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def run(*args):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1"})
    print(r.stdout.rstrip())
    if r.returncode:
        print(r.stderr.rstrip())
        sys.exit(f"step failed: {' '.join(args)}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--apply-index-fix", action="store_true")
    a = ap.parse_args()
    v = json.load(open(a.file, encoding="utf-8"))
    flags = (["--commit"] if a.commit else []) + (["--apply-index-fix"] if a.apply_index_fix else [])
    if v["verdict"] == "assign":  # identity already set; the verdict only gives the epoch(s) (`assignment`)
        if not (v.get("assignment") or {}).get("slugs"):
            sys.exit("assign verdict without assignment.slugs")
    elif v["verdict"] == "option":  # conflicts stage: identity already set; the page names a further option
        if not v.get("option_txt"):
            sys.exit("option verdict without option_txt")
        v["assignment"] = {"option_txt": v["option_txt"]}
    else:
        run("tools/apply_index_verdict.py", a.file, *flags)
        if a.commit:
            run("tools/apply_index_verdict.py", a.file, "--verify")
    if v["verdict"] == "hold":  # conflicts stage, not obvious: the director raises v["question"]
        print("hold → raise the question with tools/intake.py raise; no LPS change")
        return
    if v["verdict"] in ("unmatched", "ambiguous"):
        print("no identity → no LPS rows")
        return
    from sqlalchemy import text
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from _db import engine
    with engine().connect() as c:
        idx_id = c.execute(text("SELECT id FROM chant_indices WHERE row_id=:i"), {"i": v["row_id"]}).scalar()
    if v.get("assignment"):
        asg = {k: v["assignment"].get(k) for k in ("slugs", "wkday", "option_txt", "rank_codes")
               if v["assignment"].get(k) is not None}
        path = os.path.join(HERE, "index", "lps_overrides.json")
        ov = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        if ov.get(str(idx_id)) not in (None, asg):
            sys.exit(f"override for index #{idx_id} already differs: {ov[str(idx_id)]}")
        print(f"override #{idx_id}: {asg}")
        if a.commit:
            ov[str(idx_id)] = asg
            json.dump(ov, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    run("oco/load_oco_lps.py", "--rows", str(idx_id), *([] if a.commit else ["--dry-run"]))
    if a.commit:
        run("oco/load_oco_lps.py", "--rows", str(idx_id), "--verify")


if __name__ == "__main__":
    main()
