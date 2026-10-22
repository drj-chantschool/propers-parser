"""Shared helpers for the chant-index stage (load_index.py, resolve_index.py)."""
import re
import unicodedata

# chant_indices.section_type (the index's own Latin heading, normalized) -> gregobase `office-part`.
# Invitatories are filed as antiphons ('an', "Ad Invitatorium") in gregobase.
SECTION_TO_OFFICE_PART = {
    "introitus": "in", "graduale": "gr", "alleluia": "al", "tractus": "tr", "offertorium": "of",
    "communio": "co", "sequentia": "se", "antiphona": "an", "invitatorium": "an", "hymnus": "hy",
    "responsorium": "re", "responsorium breve": "rb", "psalmus": "ps", "canticum": "ca",
    "kyrie": "ky", "varia": "va", "tropus": "tp", "praefatio": "pr", "oratio": "or",
}

_VERSE_MARKER = re.compile(r"(?<![^\s])[v℣℟]\.?(?![^\s])")
_FOLD = str.maketrans("jv", "iu")


def condense(s):
    """Case/space/punctuation/diacritic-insensitive key; folds æ→ae, œ→oe, j→i, v→u and drops a
    bare verse marker. (Unlike the GR loader's condense(), this one also strips accents — a
    page-accurate 'Lætámini' must still hit the index's 'Laetamini'.)"""
    s = (s or "").strip().lower().replace("æ", "ae").replace("œ", "oe")
    s = _VERSE_MARKER.sub(" ", s)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[\W_]+", "", s, flags=re.UNICODE)
    return s.translate(_FOLD)


def prefix_match(a, b):
    """The rule the loaders use: one condensed incipit is a prefix of the other."""
    a, b = condense(a), condense(b)
    return bool(a and b) and (a.startswith(b) or b.startswith(a))
