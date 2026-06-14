import json
from pathlib import Path

from liturgio_tools.cli import get_rw_engine
from sqlalchemy import text

import argparse
parser= argparse.ArgumentParser(description="Upload Graduale TOC data to database")
parser.add_argument("input_json", nargs="?", default=Path(__file__).parent / "graduale" / "1" / "all_subsections.json", help="Path to JSON file containing TOC data")
args = parser.parse_args()

INPUT_JSON = Path(args.input_json)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS GRADUALE_TOC (
    IDX          SMALLINT UNSIGNED NOT NULL PRIMARY KEY,
    Y            FLOAT,
    LEVEL        TINYINT UNSIGNED NOT NULL,
    TEXT         VARCHAR(255) NOT NULL,
    PDF_PAGE     SMALLINT UNSIGNED NOT NULL,
    PRINTED_PAGE SMALLINT UNSIGNED NOT NULL
)
"""


def main():
    data = json.load(open(INPUT_JSON, encoding='utf-8'))
    minlevel = min(e['level'] for e in data)

    rows = [
        {
            "idx": idx,
            "y": e['y'],
            "level": e['level'] - minlevel,
            "text": e['text'],
            "pdf_page": e['pdf_page'],
            "printed_page": e['printed_page'],
        }
        for idx, e in enumerate(data)
    ]

    insert_sql = text("""
        INSERT INTO GRADUALE_TOC
            (IDX, Y, LEVEL, TEXT, PDF_PAGE, PRINTED_PAGE)
        VALUES
            (:idx, :y, :level, :text, :pdf_page, :printed_page)
    """)

    engine = get_rw_engine()
    with engine.connect() as conn:
        conn.execute(text(CREATE_TABLE))
        conn.execute(text("DELETE FROM GRADUALE_TOC"))
        for row in rows:
            conn.execute(insert_sql, row)
        conn.commit()

    print(f"Inserted {len(rows)} rows into liturgio.GRADUALE_TOC")


if __name__ == "__main__":
    main()
