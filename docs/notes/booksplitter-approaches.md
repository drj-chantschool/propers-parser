# Notes from `~/python/booksplitter/` (pre-pipeline experiments)

Before the current `split_chapters.py` / `split_sections.py` /
`detect_subsections.py` + `merge_subsections.py` / `split_subsections.py`
pipeline existed, `~/python/booksplitter/` held three early, unfinished
scripts exploring how to split a scanned book PDF into per-chant pieces.
None of them produced usable output; summarized here before deleting that
directory.

## `AI-one.py`

- Converts the PDF to page images via `pdf2image.convert_from_path`
  (poppler), OCRs each page with Tesseract, and looks for a line matching
  `^\s*(INT|GRADUAL|ALLE|TRAC|OFF|COMM)` to use as a title for that page's
  saved PNG.
- `split_page()` is a stub that just returns `[image]` (no actual
  sub-splitting).
- Effectively a "rename each page PNG after its detected chant-type
  heading" tool. Superseded by `split_chapters.py`'s blank-page + OCR
  title detection, which operates on PDF page ranges rather than rasterized
  page images.

## `AI-two.py`

- Attempts *content-based* splitting of a page into sub-images using OpenCV:
  `cv2.Canny` + `cv2.HoughLinesP` to find line segments, intending to crop
  each detected region separately.
- Never finished: `split_image()` collects raw Hough line endpoint tuples
  (not crop rectangles), saves a debug image (`tmp.png`), prints the line
  list, and calls `quit()` on the first page. No multi-page run ever
  completed.

## `pdf_split.py`

- A merge of the two approaches above with duplicated imports. Its
  `split_image()` is the same Hough-line approach as `AI-two.py`, but feeds
  the raw `(x1, y1, x2, y2)` line endpoints directly into `image.crop(...)`,
  which for near-collinear points produces degenerate (near-zero-area)
  crops — i.e. still broken.
- Contains dead code after the `process_pdf()` call: a second copy of the
  per-page OCR/split loop referencing undefined `images`/`titles` variables
  that would raise `NameError` if reached.

## Why these were abandoned

The Hough-line "crop sub-images out of a page raster" idea was never made to
work and turned out not to be necessary: the current pipeline operates on
whole PDF pages/page-ranges (via `fitz`), splitting at chapter/section/
subsection boundaries identified by heading OCR or embedded ToC entries,
rather than trying to isolate individual chant blocks as cropped images.
Page-number bookkeeping is handled separately by `pdf_page_mapper.py`.
