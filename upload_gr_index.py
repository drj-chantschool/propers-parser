import csv
from pathlib import Path

from liturgio_tools.cli import get_rw_engine
from sqlalchemy import text

INPUT_CSV = Path(__file__).parent / "gr_chant_index_reviewed.csv"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS gr_index_entry (
    row_id       INT AUTO_INCREMENT PRIMARY KEY,
    id           INT NOT NULL,
    page_idx     SMALLINT NOT NULL,
    col          ENUM('left','right') NOT NULL,
    bbox_x0      SMALLINT,
    bbox_y0      SMALLINT,
    bbox_x1      SMALLINT,
    bbox_y1      SMALLINT,
    section_type VARCHAR(64),
    mode         TINYINT,
    incipit      TEXT,
    page         SMALLINT,
    UNIQUE KEY uq_id_page (id, page)
)
"""


def _int_or_none(val):
    try:
        return int(val) if val not in (None, "") else None
    except (ValueError, TypeError):
        return None


def main():
    rows = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "id":           _int_or_none(row["id"]),
                "page_idx":     _int_or_none(row["page_idx"]),
                "col":          row["column"],
                "bbox_x0":      _int_or_none(row["bbox_x1"]),
                "bbox_y0":      _int_or_none(row["bbox_y1"]),
                "bbox_x1":      _int_or_none(row["bbox_x2"]),
                "bbox_y1":      _int_or_none(row["bbox_y2"]),
                "section_type": row["chant_type"],
                "mode":         _int_or_none(row["mode"]),
                "incipit":      row["incipit"],
                "page":         _int_or_none(row["page"]),
            })

    engine = get_rw_engine()
    with engine.connect() as conn:
        conn.execute(text(CREATE_TABLE))
        conn.execute(text("DELETE FROM gr_index_entry"))
        conn.execute(text("""
            INSERT INTO gr_index_entry
                (id, page_idx, col, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                 section_type, mode, incipit, page)
            VALUES
                (:id, :page_idx, :col, :bbox_x0, :bbox_y0, :bbox_x1, :bbox_y1,
                 :section_type, :mode, :incipit, :page)
        """), rows)
        conn.commit()

    print(f"Inserted {len(rows)} rows into liturgio.gr_index_entry")


if __name__ == "__main__":
    main()
