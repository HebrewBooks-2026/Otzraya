"""
מוחק מהריפו את כל הקבצים שמקורם הוא אחד מהבאים:
Tashma, MoreBooks, wiki_jewish_books

המקור של כל ספר נקבע לפי SourcesBooks.csv (עמודה 'תיקיית המקור').
הנתיב של כל ספר נלקח מהעמודה 'נתיב הקובץ', תוך הסרת הקידומת 'אוצריא/'.

ברירת מחדל: שואב את ה-CSV מ-GitHub (raw) של מאגר otzaria-library,
כך שאין צורך להחזיק את הקובץ בריפו הזה.
ניתן לעקוף עם --csv <נתיב מקומי> או --url <כתובת>.

הקשחה (מול הגרסה המקורית): התאמת-נתיב עמידה לתווי-כיווניות נסתרים (RLM/LRM
וכו') ולצורות Unicode שונות — בונה אינדקס של קבצי הריפו לפי נתיב מנורמל
(NFC + הסרת תווי-כיווניות), ומתאים אליו את נתיב ה-CSV באותו נירמול. כך
ספרים תחת תיקיות עם תווי-RLM נסתרים (כמו 'קובץ שיטות קמאי') כבר לא נפספסים.
"""

import argparse
import csv
import io
import sys
import unicodedata
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SOURCES_TO_DELETE = {"Tashma", "MoreBooks", "wiki_jewish_books"}
PREFIX_TO_STRIP = "אוצריא/"

# תווי-כיווניות (bidi) נסתרים שמופיעים לפעמים בשמות תיקיות/קבצים אך לא ב-CSV
# (או להפך) ולכן שוברים התאמת-נתיב מילולית.
BIDI_CHARS = "".join(chr(c) for c in (
    0x200E, 0x200F,                      # LRM, RLM
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # LRE/RLE/PDF/LRO/RLO
    0x2066, 0x2067, 0x2068, 0x2069,     # LRI/RLI/FSI/PDI
    0x061C,                             # ALM
))
_BIDI_TABLE = {ord(ch): None for ch in BIDI_CHARS}

DEFAULT_CSV_URL = (
    "https://raw.githubusercontent.com/Otzaria/otzaria-library/main/"
    "MoreBooks/%D7%A1%D7%A4%D7%A8%D7%99%D7%9D/%D7%90%D7%95%D7%A6%D7%A8%D7%99%D7%90/"
    "%D7%90%D7%95%D7%93%D7%95%D7%AA%20%D7%94%D7%AA%D7%95%D7%9B%D7%A0%D7%94/"
    "SourcesBooks.csv"
)


def norm_key(path: str) -> str:
    """מפתח-התאמה אחיד: forward-slashes, ללא קידומת/לוכסן מוביל, בלי תווי-כיווניות,
    ומנורמל ל-NFC — כדי ש-CSV ודיסק יתאימו גם כשהם נבדלים בתווים נסתרים."""
    p = path.replace("\\", "/").lstrip("/")
    if p.startswith(PREFIX_TO_STRIP):
        p = p[len(PREFIX_TO_STRIP):]
    p = unicodedata.normalize("NFC", p).translate(_BIDI_TABLE)
    return p


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


def build_disk_index() -> dict[str, Path]:
    """מפתח-מנורמל -> נתיב-קובץ-בפועל, לכל קבצי הריפו (פרט ל-.git)."""
    index: dict[str, Path] = {}
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(REPO_ROOT)
        if ".git" in rel.parts:
            continue
        index[norm_key(rel.as_posix())] = p
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="נתיב מקומי לקובץ SourcesBooks.csv (במקום הורדה).")
    parser.add_argument("--url", default=DEFAULT_CSV_URL, help="כתובת raw להורדת ה-CSV.")
    parser.add_argument("--dry-run", action="store_true", help="הדפסה בלבד, ללא מחיקה.")
    args = parser.parse_args()

    csv_text = load_csv_text(args.csv, args.url)
    disk_index = build_disk_index()
    print(f"קבצים בריפו (אינדקס): {len(disk_index):,}\n")

    deleted = 0
    missing = 0
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
        key = norm_key(file_path_in_csv)
        target = disk_index.get(key)

        if target is None:
            print(f"[לא קיים] {key}")
            missing += 1
            continue

        # שכבת בטיחות: לוודא שהיעד באמת בתוך הריפו (האינדקס בנוי כך, אבל ליתר ביטחון).
        try:
            target.relative_to(REPO_ROOT)
        except ValueError:
            print(f"[דילוג - מחוץ לריפו] {target}")
            continue

        rel_show = target.relative_to(REPO_ROOT).as_posix()
        if args.dry_run:
            print(f"[יימחק] {rel_show}  (מקור: {source})")
        else:
            try:
                target.unlink()
                print(f"[נמחק]  {rel_show}  (מקור: {source})")
                deleted += 1
            except OSError as e:
                print(f"[כשל]   {rel_show}: {e}")

    print()
    print("=" * 60)
    print(f"סך הכל סומנו למחיקה: {total_marked}")
    print(f"נמחקו בפועל:         {deleted}")
    print(f"לא נמצאו בדיסק:       {missing}")
    if args.dry_run:
        print("\n*** ריצת dry-run בלבד - שום קובץ לא נמחק. ***")


if __name__ == "__main__":
    main()
