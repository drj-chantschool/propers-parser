"""Shared DB + path helpers for the book-agnostic tools in propers-parser/tools/.

    from _db import engine, PP_ROOT, REPO_ROOT
    with engine().connect() as c: ...        # liturgio_ro (reads)
    with engine(rw=True).begin() as c: ...   # jcost (writes)

Scripts in this directory are run directly (`python tools/<x>.py`), so `tools/` is on sys.path.
"""
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
PP_ROOT = os.path.dirname(TOOLS)            # propers-parser/
REPO_ROOT = os.path.dirname(PP_ROOT)        # liturgio/
TMP = os.path.join(PP_ROOT, "_tmp")         # director-owned scratch (fitz can't write /tmp)

os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def engine(rw=False):
    import keyring
    from sqlalchemy import create_engine
    user = "jcost" if rw else "liturgio_ro"
    pw = keyring.get_password("liturgio-mysql", user)
    if not pw:
        raise RuntimeError(f"no keyring password for ('liturgio-mysql', {user!r})")
    return create_engine(f"mysql+mysqlconnector://{user}:{pw}@localhost:3306/liturgio", future=True)


def book_dir(book):
    """The per-book working directory under propers-parser/ (created by book-intake)."""
    known = {"GRADUALE": "graduale", "GREGORIAN_MISSAL": "GM", "LIBER_HYMNARIUS": "lhymn",
             "OCO": "oco", "OCM": "OCM"}
    return os.path.join(PP_ROOT, known.get(book, book.lower()))
