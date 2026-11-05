#!/usr/bin/env python
"""oco_sigla.py — OCO index codes (chant_indices.day_code / hour_code / place_code) → lit_part_sources
slot fields. Deterministic; the sigla legend is OCO pp1210–1213. Conventions follow the LH contract
(lhymn/specs/README.md): per-annum psalter = null epoch + wknum_mod_2/4 + wkday; Paschaltide variants of
a Common stay on the Common with option_txt; rank-conditioned rows carry rank_code; Advent IV and the
17–23 Dec weekday sets are ADV-II + wkday (GR precedent).

    targets(row) -> (list of slot dicts, None)  or  ([], "why it can't be mapped")

A slot dict: {slug, wkday, wknum_mod_2, wknum_mod_4, rank_codes (list → one LPS row each), cycle_sun, cycle_wkday,
              service, part, option_txt}
Anything not covered by a rule is returned as unmapped — never guessed. `python oco/oco_sigla.py`
prints coverage over all OCO index rows and the unmapped codes by frequency.
"""
import re
import sys
import os
from collections import Counter
from itertools import product

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

SEASONS = {  # whole-season / feast codes → slug list (+ optional wkday)
    "A": ["ADV"], "Adv": ["ADV"], "Al": [("ADV", 1)], "A1": [("ADV", 1)],
    "Adv ante 17/12": ["ADV-I"], "Adv post 17/12": ["ADV-II"], "Adv 24/12": ["ADV-II-00-8"],
    "N": ["NAT"], "N ante Ep": ["NAT-DAY", "NAT-IO", "NAT-OCT", "NAT-PO"], "N post Ep": ["NAT-EPI"],
    "N-25/12": ["NAT-DAY-00-0"], "N-1/1": ["NAT-OCT-02-0"], "Fam": ["NAT-IO-01-0"],
    "2N1": ["NAT-PO-02-0"], "Ep": ["NAT-EPI-00-0"], "Bapt": ["NAT-BAPT-01-0"],
    "Q": ["TQ"], "Q1": [("TQ", 1)],
    "P": ["PASC"], "TP": ["PASC"], "P ante Asc": ["PASC-OCT", "PASC-AD_ASC"], "TP ante Asc": ["PASC-OCT", "PASC-AD_ASC"],
    "P post Asc": ["PASC-ASC", "PASC-POST_ASC"], "Tp post Asc": ["PASC-ASC", "PASC-POST_ASC"],
    "P1": [("PASC", 1)], "1P": ["PASC-OCT"],
    "Asc": ["PASC-ASC-06-5"], "Pent": ["PASC-PENT-08-1"],
    "D": [("OT-OT", 1)],
    "Trn": ["OT-FOL-00-1"], "Corp": ["OT-FOL-00-2"], "Cord": ["OT-FOL-00-3"], "Reg": ["OT-FOL-00-4"],
    "Sabb-p-D2-p-Pent": ["OT-FOL-00-5"],
    "Def": ["liturgia-defunctorum"], "DefTP": ["liturgia-defunctorum"],
}
COMMONS = {
    "Ded": "COM-DED", "BMV": "COM-BMV", "BMV Sab": "COM-BMV-SAB", "Ap": "COM-APOST",
    "PlM": "COM-MART-PLUR", "UnM": "COM-MART-UNO", "Mart": "COM-MART-PLUR",
    "Past": "COM-PAST", "PastPl": "COM-PAST-PLUR", "Past Pl": "COM-PAST-PLUR", "Doct": "COM-DOCT",
    "Virg": "COM-VIRG", "VirgPl": "COM-VIRG-PLUR", "Vir": "COM-SANCT-VIR", "Viro": "COM-SANCT-VIR",
    "VirPl": "COM-SANCT-VIR-PLUR", "Vir Pl": "COM-SANCT-VIR-PLUR",
    "Mul": "COM-SANCT-MULIER", "MulPl": "COM-SANCT-MULIER-PLUR", "Mul Pl": "COM-SANCT-MULIER-PLUR",
    "Rel": "COM-SANCT-RELIG", "Mis": "COM-SANCT-MISER", "Educ": "COM-SANCT-EDUC",
    "UnaMart": "COM-MART-UNO",
}
DAY_QUALIFIERS = [  # trailing words of a day code that make an option, not another day
    (r"\s*Una\s*mart$", "pro una martyre"), (r"\s+Pl$", "pro pluribus"),
]
CV_SETS = {  # numbered sets of the Appendix "Antiphonae ad cantica vigiliarum" (pp1179–1200)
    "Av": [("ADV", 1)], "Nat": [("NAT-DAY-00-0", None)], "Fam": [("NAT-IO-01-0", None)],
    "SeM": [("NAT-OCT-02-0", None)], "Ep": [("NAT-EPI-00-0", None)], "Bapt": [("NAT-BAPT-01-0", None)],
    "Q1-5": [("TQ-LENT", 1)], "Q6": [("TQ-HOLYWEEK-00-1", None)], "P2-7": [("PASC", 1)],
    "Asc": [("PASC-ASC-06-5", None)], "Pent": [("PASC-PENT-08-1", None)],
    "D2-33": [("OT-OT", 1)], "Trn": [("OT-FOL-00-1", None)], "Corp": [("OT-FOL-00-2", None)],
    "Cord": [("OT-FOL-00-3", None)], "Reg": [("OT-FOL-00-4", None)],
    "Pres": [("the-presentation-in-the-temple", None)], "Jos": [("st-joseph", None)],
    "Ann": [("annunciation", None)], "Transf": [("transfiguration", None)], "Ass": [("assumption", None)],
    "Oss": [("all-saints", None)], "Ded": [("COM-DED", None)], "BMV": [("COM-BMV", None)],
    "Ap": [("COM-APOST", None)], "PlM": [("COM-MART-PLUR", None)], "UnM": [("COM-MART-UNO", None)],
    "Vir-Mul": [("COM-SANCT-VIR", None), ("COM-SANCT-MULIER", None)], "Virg": [("COM-VIRG", None)],
    "JBapt": "24/6", "Petr": "29/6", "NatND": "8/9", "Crux": "14/9", "Mich": "29/9",
    "D8.16.24.32": [("OT-OT-08-1", None), ("OT-OT-16-1", None), ("OT-OT-24-1", None), ("OT-OT-32-1", None)],
}
RANKS = {"mem.": ["MEMORIAL", "OPTIONAL_MEMORIAL"], "fest.": ["FEAST", "FEAST_OF_THE_LORD"],
         "soll.": ["SOLEMNITY"]}  # LH contract tiers
HOURS = {"1V": ["VESPERS1"], "2V": ["VESPERS"], "V": ["VESPERS"], "L": ["LAUDS"], "Ol": ["OFFREAD"],
         "T": ["TERCE"], "S": ["SEXT"], "N": ["NONE"], "Hm": ["MIDDAY"], "C": ["COMPLINE"],
         "L-V": ["LAUDS", "VESPERS"], "L V": ["LAUDS", "VESPERS"], "LV": ["LAUDS", "VESPERS"],
         "Ol V": ["OFFREAD", "VESPERS"], "1-2V": ["VESPERS1", "VESPERS"], "Ol 2V": ["OFFREAD", "VESPERS"]}
CYCLE = {"a": 1, "b": 2, "c": 3}


def _wk_range(spec):
    """'2-6' → [2..6], '5' → [5]."""
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def days(code, saints, pick=None):
    """day_code → list of partial slot dicts, or a string reason."""
    code = code.strip()
    opt = None
    m = re.fullmatch(r"(.*?)\s*\bTP$", code) or re.fullmatch(r"(.*?)TP$", code)
    if m and m.group(1) and code not in SEASONS:
        code, opt = m.group(1).strip(), "Tempore paschali"
    for pat, txt in DAY_QUALIFIERS:
        if re.search(pat, code) and re.sub(pat, "", code):
            code, opt = re.sub(pat, "", code), ", ".join(x for x in (opt, txt) if x)
    if code == "UnaMart":
        code, opt = "UnM", ", ".join(x for x in (opt, "pro una martyre") if x)
    if re.fullmatch(r"\d\.\dh\d", code):  # index typo '2h3'
        code = code.upper()
    rank = None
    m = re.fullmatch(r"(.*?)\s+(mem\.|fest\.|soll\.)(?:\s+(fest\.))?", code)
    if m:
        code, rank = m.group(1), RANKS[m.group(2)] + (RANKS["fest."] if m.group(3) else [])
    base = {"option_txt": opt, "rank_codes": rank}

    def one(slug, wkday=None, **kw):
        return {**base, "slug": slug, "wkday": wkday, **kw}

    if code == "fer TpA":  # in feriis per annum → the WEEKDAY rank tier (LH contract)
        return [{**one("OT-OT"), "rank_codes": ["WEEKDAY"]}]
    if code in ("1.3.5Q", "2.4Q"):  # Lent weeks I-III-V / II-IV (LH: season slug + wknum_mod_2)
        return [one("TQ-LENT", wknum_mod_2=1 if code == "1.3.5Q" else 0)]
    if code == "PC":
        return [one("PASC")]
    if code == "Pent C":
        return [one("PASC-PENT-08-1")]
    if code in SEASONS:
        return [one(s) if isinstance(s, str) else one(s[0], s[1]) for s in SEASONS[code]]
    if code in COMMONS:
        return [one(COMMONS[code])]
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", code)
    if m:
        hits = saints.get((int(m.group(2)), int(m.group(1))), [])
        if pick:  # the TOC (oco_toc.py) decides multi-saint dates and B1/M2-style places
            slug, why = pick(hits, f"{len(hits)} saints on {code}")
            return why if why else [one(slug)]
        if len(hits) != 1:
            return f"{len(hits)} saints on {code}"
        return [one(hits[0])]
    m = re.fullmatch(r"A-(\d{1,2})/12", code)
    if m and 17 <= int(m.group(1)) <= 24:
        return [one(f"ADV-II-00-{int(m.group(1)) - 16}")]
    m = re.fullmatch(r"N-(\d{1,2})/(12|1)", code)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        slug = {(26, 12): "NAT-IO-01-1", (27, 12): "NAT-IO-01-2", (28, 12): "NAT-IO-01-3",
                (29, 12): "NAT-IO-01-4", (30, 12): "NAT-IO-01-5", (31, 12): "NAT-IO-01-6",
                (2, 1): "NAT-PO-02-1", (3, 1): "NAT-PO-02-2", (4, 1): "NAT-PO-02-3",
                (5, 1): "NAT-PO-02-4", (6, 1): "NAT-PO-02-5", (7, 1): "NAT-PO-02-6"}.get((d, mo))
        return [one(slug)] if slug else f"no Christmastide slug for {code}"
    m = re.fullmatch(r"Ep-(\d{1,2})/1", code)
    if m and 7 <= int(m.group(1)) <= 12:
        return [one(f"NAT-EPI-00-{int(m.group(1)) - 6}")]
    m = re.fullmatch(r"(\d)A(\d)", code)  # Advent week w, day d
    if m:
        w, d = int(m.group(1)), int(m.group(2))
        if w <= 3:
            return [one(f"ADV-I-0{w}-{d}")]
        return [one("ADV-II", d)]  # 4A1 = Dom. IV; 5A2..7 = Feria II.. post 16 dec.
    m = re.fullmatch(r"(\d)Q(\d)", code)
    if m:
        w, d = int(m.group(1)), int(m.group(2))
        return [one(f"TQ-LENT-0{w}-{d}" if w <= 5 else f"TQ-HOLYWEEK-00-{d}")]
    m = re.fullmatch(r"(\d)-(\d)Q(\d)(?:-(\d))?", code)  # weeks w1..w2 of Lent, days d1..d2
    if m:
        out = []
        for w in range(int(m.group(1)), int(m.group(2)) + 1):
            for d in _wk_range(m.group(3) + ("-" + m.group(4) if m.group(4) else "")):
                if w == 0 and d < 4:
                    continue  # Lent starts on Ash Wednesday
                out.append(one(f"TQ-LENT-0{w}-{d}"))
        return out
    m = re.fullmatch(r"(\d)P(\d)", code)
    if m:
        w, d = int(m.group(1)), int(m.group(2))
        if w == 1:
            return [one(f"PASC-OCT-01-{d}")]
        if w == 6 and d >= 6:  # Fri/Sat exist before Ascension (moved to Sunday) and after it (Thursday)
            return [one(f"PASC-AD_ASC-06-{d}"), one(f"PASC-POST_ASC-06-{d}")]
        if w == 7:
            return [one(f"PASC-POST_ASC-0{w}-{d}")]
        return [one(f"PASC-AD_ASC-0{w}-{d}")]
    m = re.fullmatch(r"(\d{1,2})D", code)  # Sunday n per annum
    if m and 2 <= int(m.group(1)) <= 34:
        return [one(f"OT-OT-{int(m.group(1)):02d}-1")]
    m = re.fullmatch(r"D(\d{1,2}(?:\.\d{1,2})+)", code)  # Sundays per annum 2.10.18.26
    if m:
        return [one(f"OT-OT-{int(n):02d}-1") for n in m.group(1).split(".")]
    m = re.fullmatch(r"(1\.3|2\.4|1-4|[1-4])?H([0-7](?:-[0-7])?)?", code)  # psalter
    if m:
        weeks, dd = m.group(1), m.group(2)
        psal = {"1.3": {"wknum_mod_2": 1}, "2.4": {"wknum_mod_2": 0}}.get(weeks) or \
            ({"wknum_mod_4": int(weeks) % 4} if weeks and weeks.isdigit() else {})
        # H0 = Dominica psalterii post I Vesperas: Saturday-night Compline (the index has no H7 Compline)
        if dd == "0-7":
            wkdays = [None]
        elif dd == "0":
            wkdays = [7]
        else:
            wkdays = _wk_range(dd) if dd else [None]
        # Rank tones ('2.4H mem.', '1.3H soll.') are printed per annum, so they apply in Ordinary
        # Time only (user ruling 2026-10-20, as LH's OT-OT "in memoriis"); plain psalter stays epoch-less.
        slug = "OT-OT" if rank else None
        return [one(slug, d, **psal) for d in wkdays]
    m = re.fullmatch(r"(\d)-(\d)P(\d(?:-\d)?)?", code)  # Easter weeks w1..w2, days
    if m:
        out = []
        for w in range(int(m.group(1)), int(m.group(2)) + 1):
            for d in (_wk_range(m.group(3)) if m.group(3) else range(1, 8)):
                r = days(f"{w}P{d}", saints, pick)
                if isinstance(r, str):
                    return r
                out += [{**x, **{k: v for k, v in base.items() if v}} for x in r]
        return out
    if code == "1P1-8":
        return [one(f"PASC-OCT-01-{d}") for d in range(1, 8)] + [one("PASC-AD_ASC-02-1")]
    m = re.fullmatch(r"P(\d)-(\d) (?:ante|usque) Asc", code, re.I)
    if m:
        return [one("PASC-AD_ASC", d) for d in range(int(m.group(1)), int(m.group(2)) + 1)]
    m = re.fullmatch(r"6Q(\d)-(\d)", code)
    if m:
        return [one(f"TQ-HOLYWEEK-00-{d}") for d in range(int(m.group(1)), int(m.group(2)) + 1)]
    if code == "6Q":
        return [one("TQ-HOLYWEEK")]
    m = re.fullmatch(r"34H(\d)-(\d)", code)
    if m:
        return [one(f"OT-OT-34-{d}") for d in range(int(m.group(1)), int(m.group(2)) + 1)]
    m = re.fullmatch(r"D-(I|II|III|IV)", code)  # Dominica I-IV Psalterii, pro ecclesiis minoribus
    if m:
        k = {"I": 1, "II": 2, "III": 3, "IV": 4}[m.group(1)]
        return [{**one(None, 1, wknum_mod_4=k % 4), "option_txt": "pro ecclesiis minoribus"}]
    m = re.fullmatch(r"(Adv(?: ante 17/12| post 17/12)?) H(\d(?:-\d)?)", code)
    if m:
        slug = SEASONS[m.group(1)][0]
        return [one(slug, d) for d in _wk_range(m.group(2))]
    m = re.fullmatch(r"\d\d([A-Z].*)", code)  # numbered vigil-canticle set: 41Ded, 15D2-33
    if m and m.group(1) in CV_SETS:
        cv = CV_SETS[m.group(1)]
        if isinstance(cv, str):  # a saint by date
            return days(cv, saints, pick)
        return [one(sl, wd) for sl, wd in cv]
    if " " in code:  # a list of codes: '25/4 11/6 18/10', 'Vir Mul Rel', '6Q 14/9'
        out = []
        for tok in code.split():
            r = days(tok, saints, pick)
            if isinstance(r, str):
                return f"no rule for {code!r} ({r})"
            out += [{**x, **{k: v for k, v in base.items() if v}} for x in r]
        return out
    return f"no rule for {code!r}"


PLACE_QUALIFIERS = [  # suffixes of a place code → option_txt (order matters)
    (r"ad lib\.?(?: ?\d+)?(?: ?TP)?", None), (r"TP", "Tempore paschali"), (r"TQ", "Tempore Quadragesimae"),
    (r"exTpA", "Extra tempus per annum"), (r"TpA", "Tempore per annum"),
    (r"ante Asc", "Ante Ascensionem"), (r"post Asc", "Post Ascensionem"),
    (r"(?<=[BM])\*", "cum Evangelio de Lazaro"),  # only 5Q1 B*/M*; not tied to Year A (intake #13, #17)
    (r"pro eccl\. minor\.", "pro ecclesiis minoribus"), (r"pro plur\.", "pro pluribus"),
    (r"pro una mart\.", "pro una martyre"), (r"pro mart\.", "pro martyre"),
    (r"pro religiosa", "pro religiosa"), (r"pro pap\. vel episc\.", "pro papa vel episcopo"),
    (r"pro presb\.", "pro presbytero"),
]


# Subject qualifiers are modelled as sub-epochs, not option_txt (user, 2026-10-23: "any time option text can be
# modelled by our data structure, do that. They should go in sub-epochs"). Unambiguous ones are mapped here;
# the rest stay option_txt in the proposal and page_draft.py notes them for the producer to place from the page.
SUBJECT_EPOCHS = {
    ("COM-SANCT-VIR", "pro pluribus"): ["COM-SANCT-VIR-PLUR"],
    ("COM-SANCT-MULIER", "pro pluribus"): ["COM-SANCT-MULIER-PLUR"],
    ("COM-PAST", "pro pluribus"): ["COM-PAST-PLUR"],
    ("COM-VIRG", "pro pluribus"): ["COM-VIRG-PLUR"],
    ("COM-PAST", "pro papa vel episcopo"): ["COM-PAST-UNO-PAPA", "COM-PAST-UNO-EPISC"],
    ("COM-PAST", "pro presbytero"): ["COM-PAST-UNO-PRESB"],
}
SUBJECT_WORDS = re.compile(r"^pro (?!ecclesiis)", re.I)  # 'pro ecclesiis minoribus' is no subject


def sub_epochs(slug, option_txt):
    """(slugs, option_txt) after moving subject qualifiers into sub-epochs; ambiguous ones are kept."""
    opts = [o for o in (option_txt or "").split(", ") if o]
    slugs = [slug]
    for o in list(opts):
        hit = SUBJECT_EPOCHS.get((slug, o.lower()))
        if hit:
            slugs = hit
            opts.remove(o)
    # Ante/Post Ascensionem is already said by the PASC-AD_ASC / PASC-POST_ASC epoch
    if slug and slug.startswith(("PASC-AD_ASC", "PASC-OCT")) and "Ante Ascensionem" in opts:
        opts.remove("Ante Ascensionem")
    if slug and slug.startswith(("PASC-POST_ASC", "PASC-ASC")) and "Post Ascensionem" in opts:
        opts.remove("Post Ascensionem")
    return slugs, ", ".join(opts) or None


def split_place(place):
    """'Mbc ad lib' → ('M', 'bc', None, ['Ad libitum']); '2TpA' → ('2', '', None, [...])."""
    p, opts = (place or "").strip(), []
    while True:
        for pat, txt in PLACE_QUALIFIERS:
            m = re.search(r"\s*(" + pat + r")$", p)
            if m and m.start() > 0 or (m and pat.startswith("ad lib")):
                if pat.startswith("ad lib"):
                    num = re.search(r"\d+", m.group(1))
                    opts.insert(0, "Ad libitum" + (f" {num.group(0)}" if num else ""))
                    if m.group(1).endswith("TP"):
                        opts.append("Tempore paschali")
                else:
                    opts.insert(0, txt)
                p = p[:m.start()].strip()
                break
        else:
            break
    p = re.sub(r"^([BM])[1-3]$", r"\1", p)  # B1/M2: n-th saint of the date (oco_toc, toc_saint)
    m = re.fullmatch(r"(Nunc|[123BM])?([abc]*)(?:-?(I|II))?", p)
    if not m:
        return None
    return m.group(1) or "", m.group(2), m.group(3), opts


def parts(section_type, hour, place):
    """→ (list of (service, part, extra), reason). extra: cycle_sun / cycle_wkday / option_txt."""
    if hour and re.fullmatch(r"M[1-3]?", hour):  # 'M'/'M2' in the hour column = Magnificat, hour omitted (intake
        hour, place = "V", hour + (place or "")  # #18, #19; pp763, 424 (v.6): '13/4 | M | TP', '13D | M | a ad lib')
    if section_type == "invitatorium":
        return [("INVITATORY", "invan", {})], None
    if hour == "C" and re.fullmatch(r"Ma([1-4])(b?)", place or ""):  # final Marian antiphon n (b: 2nd setting)
        m = re.fullmatch(r"Ma([1-4])(b?)", place)
        return [("COMPLINE", "antMar", {"option_txt": f"Antiphona finalis {m.group(1)}"
                                        + (" (altera melodia)" if m.group(2) else "")})], None
    if hour in ("V", "C") and re.fullmatch(r"Ma5[bc]?", place or ""):  # Regina caeli, TP; 'V' is a misprint for C
        return [("COMPLINE", "antMar", {"option_txt": {"Ma5": None, "Ma5b": "Tonus simplex (modus 6)",  # (intake #15)
                                                        "Ma5c": "Tonus simplex (modus 1)"}[place]})], None
    if hour == "Sab":  # 'Antiphona ad libitum pro memoria S. Mariae in sabbato' n
        return [("LAUDS", "antB", {"option_txt": f"Ad libitum {place}" if place else "Ad libitum"})], None
    if hour is None and re.fullmatch(r"ad lib\.? ?\d+(?: ?TP)?(?: ?pro plur\.)?", place or ""):
        sp = split_place(place)  # ad libitum for the Gospel canticles: Benedictus and Magnificat
        txt = ", ".join(sp[3]) if sp else place
        return [(s, pt, {"option_txt": txt}) for s, pt in
                (("LAUDS", "antB"), ("VESPERS1", "antM"), ("VESPERS", "antM"))], None
    services = HOURS.get(hour or "")
    if not services:
        return [], f"hour {hour!r}"
    if section_type == "hymnus":
        return [(s, "hymn", {}) for s in services], None
    if section_type == "responsorium breve":
        if place:
            return [], f"rb with place {place!r}"
        return [(s, "resp", {}) for s in services], None
    if hour == "Ol" and place in ("C", "CV"):
        return [("VIGILIAE", "antcv", {})], None
    sp = split_place(place)
    if sp is None:
        return [], f"place {place!r}"
    core, cyc, yr, opts = sp
    nth = re.match(r"[BM]([1-3])", place or "")  # B1/B2, M1/M2: alternatives, option n (intake #12/#16)
    if nth and "Tempore per annum" in opts:
        return [], f"place {place!r}: TpA on a B/M alternative is not settled yet (intake #12)"
    extra = {"option_txt": ", ".join(opts) or None,
             "cycle_wkday": {"I": 1, "II": 2}.get(yr),
             "option_num": int(nth.group(1)) if nth else None}
    cycles = [CYCLE[c] for c in cyc] or [None]
    out = []
    for s in services:
        if s in ("TERCE", "SEXT", "NONE") and core == "":
            part = "ant"
        elif core in ("1", "2", "3"):  # T/S/N ant1-3: complementary psalmody (intake #14)
            part = f"ant{core}"
        elif core == "B" and s == "LAUDS":
            part = "antB"
        elif core == "M" and s in ("VESPERS", "VESPERS1"):
            part = "antM"
        elif core == "Nunc" and s == "COMPLINE":
            part = "antN"
        else:
            return [], f"place {place!r} at {s}"
        out += [(s, part, {**extra, "cycle_sun": c}) for c in cycles]
    return out, None


# Lent III-V Sundays: after the Year-A antiphons OCO prints "Quae antiphonae etiam aliis annis adhibendae sunt,
# si legatur evangelium de Samaritana / de caeco nato / de Lazaro" (v.6 pp178, 194, 211). So their 'a' places
# carry no cycle_sun, only this option_txt (user, intake #23; B*/M* likewise, #13/#17).
LENT_A_GOSPEL = {"3Q1": "cum Evangelio de Samaritana", "4Q1": "cum Evangelio de caeco nato",
                 "5Q1": "cum Evangelio de Lazaro"}


class Saints(dict):
    """(month, day) → [slug]; .toc = oco_toc.saint_entries (the date's saints in book order + pages)."""
    toc = {}


# B1/B2/B3, M1/M2/M3: the user ruled they are ALTERNATIVES (options 1/2/3) for one office, and the
# agent picks the date's saint(s) from the page (intake #12, #16, #22). The n-th-saint reading (TOC
# order) stays here, off, as evidence only.
NTH_SAINT_RULE = False


def toc_saint(row, saints, hits, why):
    """A date's slug: B1/M2 places → the n-th saint in the TOC; one saint → it; several → the TOC
    section holding the row's page; else say why not."""
    m = re.match(r"(\d{1,2})/(\d{1,2})", row.day_code or "")
    es = saints.toc.get((int(m.group(2)), int(m.group(1)))) if m else None
    place = (row.hour_code if re.fullmatch(r"M[1-3]", row.hour_code or "") else "") + (row.place_code or "")
    n = re.match(r"[BM]([1-3])", place)
    if n and not es:
        return None, f"place {place} on a date with no TOC heading"
    if not n and len(hits) == 1:
        return hits[0], None
    if not es:
        return None, why
    if n:
        if not NTH_SAINT_RULE:
            return None, (f"{why} (place {place} = option {n.group(1)} of an office on this date: "
                          "the agent gives the slug(s) from the page — intake #22)")
        e = es[int(n.group(1)) - 1] if int(n.group(1)) <= len(es) else None
        return (e[0], None) if e and e[0] else (None, f"{why} (no slug for saint {n.group(1)} in the TOC)")
    if row.page is None:
        return None, why
    p = int(row.page)
    inside = [e for e in es if e[2] <= p <= e[3]]
    if len(inside) == 1 and inside[0][0]:
        return inside[0][0], None
    if inside:
        return None, f"{why} (p{p} shared by TOC sections {', '.join(e[1] for e in inside)})"
    return None, f"{why} (p{p} outside the date's TOC sections — engraved elsewhere)"


def load_saints(conn):
    from sqlalchemy import text
    from oco_toc import saint_entries
    saints = Saints()
    saints.toc = saint_entries(conn)
    for slug, m, d in conn.execute(text("SELECT slug, month_nominal, day_nominal FROM proper_of_saints "
                                        "WHERE jurisdiction='UNIVERSAL' AND month_nominal IS NOT NULL")):
        saints.setdefault((m, d), []).append(slug)
    return saints


def targets(row, saints, override=None):
    """override (reviewed agent verdict, oco/index/lps_overrides.json): {"slugs": [...], "wkday": n,
    "option_txt": "..."} replaces the day-code mapping when the code can't say which day (a date
    with several saints, an odd code). An override with no "slugs" keeps the code mapping and only sets
    option_txt (a held CONFLICT row that the page shows is a further option)."""
    if override and not override.get("slugs"):
        out, why = targets(row, saints)
        return [{**x, "option_txt": override["option_txt"]} for x in out], why
    if override:
        ds = [{"slug": s, "wkday": override.get("wkday"), "option_txt": override.get("option_txt"),
               "rank_codes": override.get("rank_codes")} for s in override["slugs"]]
    elif not row.day_code:
        return [], "no day code"
    else:
        ds = days(row.day_code, saints, lambda hits, why: toc_saint(row, saints, hits, why))
    if isinstance(ds, str):
        return [], ds
    ps, why = parts(row.section_type, row.hour_code, row.place_code)
    if why:
        return [], why
    # Thu–Sat of Easter week 6 differ by whether Ascension (Thursday, or moved to Sunday) has passed:
    # the place qualifier picks PASC-AD_ASC-06-d vs PASC-POST_ASC-06-d and is then no option.
    m = None if override else re.fullmatch(r"6P([5-7])", row.day_code or "")
    if m:
        sides = {"Ante Ascensionem": "AD_ASC", "Post Ascensionem": "POST_ASC"}
        side = {sides[o] for _, _, e in ps for o in (e.get("option_txt") or "").split(", ") if o in sides}
        if len(side) != 1:
            return [], (f"{row.day_code} without 'ante/post Asc': before or after Ascension is ambiguous "
                        "(Ascension Thursday vs moved to Sunday) — the TOC heading of the page decides: pp336–339 "
                        "before 'In Ascensione Domini' = PASC-AD_ASC-06-d, p350 'Post Ascensionem' = PASC-POST_ASC-06-d")
        slug = f"PASC-{side.pop()}-06-{m.group(1)}"
        ds = [{**ds[0], "slug": slug}]
        ps = [(s, p, {**e, "option_txt": ", ".join(o for o in (e.get("option_txt") or "").split(", ")
                                                   if o and o not in sides) or None}) for s, p, e in ps]
    if row.day_code in LENT_A_GOSPEL:  # Year-A sets usable in any year (intake #23)
        ps = [(s, p, {**e, "cycle_sun": None, "option_txt": ", ".join(
            x for x in (e.get("option_txt"), LENT_A_GOSPEL[row.day_code]) if x)} if e.get("cycle_sun") == 1 else e)
              for s, p, e in ps]
    out = []
    for d, (svc, part, extra) in product(ds, ps):
        slugs, opt = sub_epochs(d["slug"], ", ".join(x for x in (d.get("option_txt"), extra.get("option_txt")) if x))
        for slug in slugs:
            out.append({"slug": slug, "wkday": d.get("wkday"), "wknum_mod_2": d.get("wknum_mod_2"),
                        "wknum_mod_4": d.get("wknum_mod_4"), "rank_codes": d.get("rank_codes"),
                        "cycle_sun": extra.get("cycle_sun"), "cycle_wkday": extra.get("cycle_wkday"),
                        "service": svc, "part": part, "option_num": extra.get("option_num"),
                        "option_txt": opt})
    return out, None


def main():
    from _db import engine
    from sqlalchemy import text
    with engine().connect() as c:
        saints = load_saints(c)
        rows = c.execute(text("SELECT row_id, page, section_type, day_code, hour_code, place_code FROM chant_indices "
                              "WHERE book='OCO'")).all()
        slugs = {x for (x,) in c.execute(text("SELECT slug FROM lit_epoch"))}
        ranks = {x for (x,) in c.execute(text("SELECT rank_code FROM p_lit_rank"))}
        parts_ok = {(a, b) for a, b in c.execute(text("SELECT service_code, part_code FROM service_part"))}
    ok, why = 0, Counter()
    for r in rows:
        t, reason = targets(r, saints)
        bad = [x for x in t if (x["slug"] and x["slug"] not in slugs) or (x["service"], x["part"]) not in parts_ok
               or any(k not in ranks for k in x["rank_codes"] or [])]
        if bad:
            t, reason = [], f"BUG: unknown slug/part/rank {bad[0]}"
        if t:
            ok += 1
        else:
            why[reason] += 1
    print(f"mapped {ok}/{len(rows)}")
    for k, n in why.most_common():
        print(f"{n:5}  {k}")


if __name__ == "__main__":
    main()
