"""
Split oco.pdf into a tree of mini-PDFs mirroring its embedded TOC (bookmark outline).

Each TOC leaf becomes a file; each TOC node with children becomes a directory.
If a node has its own content before its first child begins (parent start page <
first child start page), that intro content becomes a "00 - <title> (intro).pdf"
file inside that node's own directory.

Every mini-PDF includes one extra trailing page (the first page of whatever
follows it) to capture widows/orphans that spill across the split boundary.

Run with the canonical venv:
  C:\\Users\\johna\\liturgio\\.venv\\Scripts\\python.exe split_oco_by_toc.py
"""
import os
import re
from dataclasses import dataclass, field
from pypdf import PdfReader, PdfWriter

SRC = os.path.join(os.path.dirname(__file__), "oco.pdf")
OUT_ROOT = os.path.join(os.path.dirname(__file__), "oco_split")

INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize(title: str) -> str:
    title = INVALID_CHARS.sub("-", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.rstrip(". ")
    return title[:120]  # keep names reasonably short


@dataclass
class Node:
    title: str
    start_page: int
    children: list = field(default_factory=list)


@dataclass
class Unit:
    dir_path: list
    filename: str
    start_page: int


def build_tree(reader: PdfReader) -> list:
    def walk(outline):
        nodes = []
        i = 0
        while i < len(outline):
            item = outline[i]
            if isinstance(item, list):
                # nested list belongs to the previous sibling
                if nodes:
                    nodes[-1].children = walk(item)
                i += 1
                continue
            page_num = reader.get_destination_page_number(item)
            nodes.append(Node(title=str(item.title), start_page=page_num))
            i += 1
        return nodes

    return walk(reader.outline)


def build_units(node: Node, index: int, parent_dir_path: list) -> list:
    name = f"{index:02d} - {sanitize(node.title)}"
    if node.children:
        this_dir_path = parent_dir_path + [name]
        units = []
        if node.start_page < node.children[0].start_page:
            units.append(
                Unit(
                    dir_path=this_dir_path,
                    filename=f"00 - {sanitize(node.title)} (intro).pdf",
                    start_page=node.start_page,
                )
            )
        for i, child in enumerate(node.children, start=1):
            units.extend(build_units(child, i, this_dir_path))
        return units
    else:
        return [
            Unit(
                dir_path=parent_dir_path,
                filename=f"{name}.pdf",
                start_page=node.start_page,
            )
        ]


def main():
    reader = PdfReader(SRC)
    total_pages = len(reader.pages)
    top_nodes = build_tree(reader)

    units = []
    for i, node in enumerate(top_nodes, start=1):
        units.extend(build_units(node, i, []))

    # sanity: start pages should be non-decreasing in document order
    for a, b in zip(units, units[1:]):
        assert a.start_page <= b.start_page, (a, b)

    # front matter before the first TOC entry, if any
    if units[0].start_page > 0:
        units.insert(
            0,
            Unit(dir_path=[], filename="00 - Front Matter.pdf", start_page=0),
        )

    os.makedirs(OUT_ROOT, exist_ok=True)

    manifest = []
    for i, unit in enumerate(units):
        start = unit.start_page
        if i + 1 < len(units):
            next_start = units[i + 1].start_page
            widow_end = next_start if next_start <= total_pages - 1 else total_pages - 1
        else:
            widow_end = total_pages - 1
        end = max(widow_end, start)

        out_dir = os.path.join(OUT_ROOT, *unit.dir_path)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, unit.filename)

        writer = PdfWriter()
        for p in range(start, end + 1):
            writer.add_page(reader.pages[p])
        with open(out_path, "wb") as f:
            writer.write(f)

        rel = os.path.relpath(out_path, OUT_ROOT)
        manifest.append((rel, start, end, end - start + 1))

    print(f"Wrote {len(units)} PDFs under {OUT_ROOT}")
    print(f"Total source pages: {total_pages}")
    with open(os.path.join(OUT_ROOT, "_manifest.tsv"), "w", encoding="utf-8") as f:
        f.write("path\tstart_page_0idx\tend_page_0idx\tpage_count\n")
        for rel, start, end, count in manifest:
            f.write(f"{rel}\t{start}\t{end}\t{count}\n")


if __name__ == "__main__":
    main()
