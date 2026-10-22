#!/usr/bin/env python
"""oco_pages.py — printed page ↔ PDF page for the OCO master PDF.

Every page number stored in the DB (books, book_toc, chant_indices.page, lit_part_sources.printed_page_num)
is the PRINTED page (running head). The PDF's link targets and outline are PDF pages.

v.4 (2023): printed = PDF page, 1–1320.
v.6 (A.D. MMXXV, installed 2026-10-20): the blank verso before 'IV. Communia' (printed 974) is not in
the PDF, so PDF 1–973 = printed 1–973 and PDF 974–1319 = printed 975–1320 (verified on every running head).
"""
MISSING = 974  # printed page with no PDF page (v.6)


def printed(pdf_page):
    """1-based PDF page → printed page."""
    return pdf_page if pdf_page < MISSING else pdf_page + 1


def pdf(printed_page):
    """Printed page → 1-based PDF page, or None for the dropped blank."""
    printed_page = int(printed_page)
    if printed_page == MISSING:
        return None
    return printed_page if printed_page < MISSING else printed_page - 1


def page(doc, printed_page):
    """The fitz page for a printed page number, or None (out of range / the dropped blank)."""
    n = pdf(printed_page)
    return doc[n - 1] if n and 1 <= n <= doc.page_count else None


def last_printed(doc):
    return printed(doc.page_count)
