"""
מוחק מהריפו את כל הקבצים שמקורם הוא אחד מהבאים:
Tashma, MoreBooks, wiki_jewish_books

המקור של כל ספר נקבע לפי SourcesBooks.csv (עמודה 'תיקיית המקור').
הנתיב של כל ספר נלקח מהעמודה 'נתיב הקובץ', תוך הסרת הקידומת 'אוצריא/'.

ברירת מחדל: שואב את ה-CSV מ-GitHub (raw) של מאגר otzaria-library,
כך שאין צורך להחזיק את הקובץ בריפו הזה.
ניתן לעקוף עם --csv <נתיב מקומי> או --url <כתובת>.
"""

import argparse
import csv
import io
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SOURCES_TO_DELETE = {"Tashma", "MoreBooks", "wiki_jewish_books"}
PREFIX_TO_STRIP = "אוצריא/"

DEFAULT_CSV_URL = (
    "https://raw.githubusercontent.com/Otzaria/otzaria-library/main/"
    "MoreBooks/%D7%A1%D7%A4%D7%A8%D7%99%D7%9D/%D7%90%D7%95%D7%A6%D7%A8%D7%99%D7%90/"
    "%D7%90%D7%95%D7%93%D7%95%D7%AA%20%D7%94%D7%AA%D7%95%D7%9B%D7%A0%D7%94/"
    "SourcesBooks.csv"
)


def load_csv_text(csv_path: Path | None, url: str | None) -> str:
    if csv_path is not None:
        if not csv_path.exists():
            print(f"[שגיאה] לא נמצא קובץ {csv_path}")
            sys.exit(1)
        return csv_path.read_text(encoding="utf-8")

    print(f"מוריד את SourcesBooks.csv מ:\n  {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "delete-by-source-script"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    print(f"הורדו {len(data):,} בייטים.\n")
    return data.decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="נתיב מקומי לקובץ SourcesBooks.csv (במקום הורדה).")
    parser.add_argument("--url", default=DEFAULT_CSV_URL, help="כתובת raw להורדת ה-CSV.")
    parser.add_argument("--dry-run", action="store_true", help="הדפסה בלבד, ללא מחיקה.")
    args = parser.parse_args()

    csv_text = load_csv_text(args.csv, args.url)

    deleted = 0
    missing = 0
    skipped_outside_repo = 0
    total_marked = 0

    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None)  # דילוג על כותרת
    for row in reader:
        if len(row) < 3:
            continue
        file_path_in_csv = row[1].strip()
        source = row[2].strip()

        if source not in SOURCES_TO_DELETE:
            continue

        total_marked += 1

        normalized = file_path_in_csv.replace("\\", "/").lstrip("/")
        if normalized.startswith(PREFIX_TO_STRIP):
            normalized = normalized[len(PREFIX_TO_STRIP):]

        target = (REPO_ROOT / normalized).resolve()

        try:
            target.relative_to(REPO_ROOT)
        except ValueError:
            print(f"[דילוג - מחוץ לריפו] {file_path_in_csv}")
            skipped_outside_repo += 1
            continue

        if not target.exists():
            print(f"[לא קיים] {normalized}")
            missing += 1
            continue

        if args.dry_run:
            print(f"[יימחק] {normalized}  (מקור: {source})")
        else:
            try:
                target.unlink()
                print(f"[נמחק]  {normalized}  (מקור: {source})")
                deleted += 1
            except OSError as e:
                print(f"[כשל]   {normalized}: {e}")

    print()
    print("=" * 60)
    print(f"סך הכל סומנו למחיקה: {total_marked}")
    print(f"נמחקו בפועל:         {deleted}")
    print(f"לא נמצאו בדיסק:       {missing}")
    print(f"דולגו (מחוץ לריפו):    {skipped_outside_repo}")
    if args.dry_run:
        print("\n*** ריצת dry-run בלבד - שום קובץ לא נמחק. ***")


if __name__ == "__main__":
    main()
