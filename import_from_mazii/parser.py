# Parse Mazii export files (CSV or Excel) into rows of word data.

from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional

# Optional xlsx support (preferred when available)
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# XML namespaces in xlsx
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


# Common header names that we map to our keys (lowercase match)
# Mazii export uses: word, phonetic, mean, comment
KANJI_HEADERS = ("word", "kanji", "vocabulary", "term", "vocab", "japanese", "expression")
KANA_HEADERS = ("kana", "reading", "readings", "furigana", "hiragana", "phonetic")
MEANING_HEADERS = ("meaning", "definition", "english", "translation", "gloss", "def", "mean")


def _normalize_header(h: str) -> str:
    return (h or "").strip().lower()


def _detect_columns(headers: List[str]) -> dict:
    """Map our keys (kanji, kana, meaning) to column indices (0-based)."""
    out = {}
    for i, h in enumerate(headers):
        n = _normalize_header(h)
        if n in KANJI_HEADERS and "kanji" not in out:
            out["kanji"] = i
        elif n in KANA_HEADERS and "kana" not in out:
            out["kana"] = i
        elif n in MEANING_HEADERS and "meaning" not in out:
            out["meaning"] = i
    return out


def _row_to_word(row: List[str], col_map: dict) -> Optional[dict]:
    """Convert a row to {kanji, kana?, meaning?}. Returns None if kanji is empty."""
    ki = col_map.get("kanji")
    if ki is None:
        # No kanji column: use first column as word
        kanji = (row[0] or "").strip() if row else ""
    else:
        kanji = (row[ki] or "").strip() if ki < len(row) else ""
    if not kanji:
        return None
    out = {"kanji": kanji}
    if "kana" in col_map and col_map["kana"] < len(row):
        out["kana"] = (row[col_map["kana"]] or "").strip()
    if "meaning" in col_map and col_map["meaning"] < len(row):
        out["meaning"] = (row[col_map["meaning"]] or "").strip()
    return out


def parse_csv(path: Path) -> List[dict]:
    """Parse a CSV file. First row is treated as header. Returns list of {kanji, kana?, meaning?}."""
    rows: List[dict] = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            raw_rows = list(reader)
    except Exception:
        return []
    if not raw_rows:
        return []
    headers = raw_rows[0]
    col_map = _detect_columns(headers)
    if not col_map and len(headers) > 0:
        # No recognized headers: assume first column is kanji
        col_map = {"kanji": 0}
        if len(headers) > 1:
            col_map["kana"] = 1
        if len(headers) > 2:
            col_map["meaning"] = 2
    for row in raw_rows[1:]:
        w = _row_to_word(row, col_map)
        if w:
            rows.append(w)
    return rows


def _col_from_cell_ref(ref: str) -> int:
    """Convert cell ref (e.g. A1, B2, AA3) to column index 0-based."""
    match = re.match(r"^([A-Z]+)", ref.upper())
    if not match:
        return 0
    col_str = match.group(1)
    n = 0
    for c in col_str:
        n = n * 26 + (ord(c) - ord("A") + 1)
    return n - 1


def _read_shared_strings(z: zipfile.ZipFile) -> List[str]:
    """Read xl/sharedStrings.xml and return list of strings (if present)."""
    try:
        with z.open("xl/sharedStrings.xml") as f:
            tree = ET.parse(f)
    except KeyError:
        return []
    root = tree.getroot()
    uri = NS["main"]
    si_tag = f"{{{uri}}}si"
    t_tag = f"{{{uri}}}t"
    strings = []
    for si in root.findall(f".//{si_tag}"):
        t_el = si.find(t_tag)
        if t_el is not None and t_el.text is not None:
            strings.append(t_el.text)
        else:
            parts = [el.text or "" for el in si.findall(f".//{t_tag}")]
            strings.append("".join(parts))
    return strings


def _parse_xlsx_stdlib(path: Path) -> List[dict]:
    """Parse first sheet of xlsx using only stdlib (zipfile + xml). Used when openpyxl is missing."""
    rows: List[dict] = []
    try:
        with zipfile.ZipFile(path, "r") as z:
            shared = _read_shared_strings(z)
            try:
                with z.open("xl/worksheets/sheet1.xml") as f:
                    tree = ET.parse(f)
            except KeyError:
                return []
            root = tree.getroot()
            uri = NS["main"]
            row_tag = f"{{{uri}}}row"
            c_tag = f"{{{uri}}}c"
            v_tag = f"{{{uri}}}v"
            grid: dict = {}
            for row_el in root.findall(f".//{row_tag}"):
                r = int(row_el.get("r", 0))
                grid[r] = {}
                for c_el in row_el.findall(c_tag):
                    ref = c_el.get("r", "")
                    col = _col_from_cell_ref(ref)
                    val_el = c_el.find(v_tag)
                    if val_el is None:
                        grid[r][col] = ""
                    else:
                        raw = (val_el.text or "").strip()
                        cell_type = c_el.get("t")
                        if cell_type == "s" and shared:
                            # shared string index
                            try:
                                idx = int(raw)
                                grid[r][col] = shared[idx] if idx < len(shared) else ""
                            except ValueError:
                                grid[r][col] = raw
                        else:
                            # inline string (t="str") or number: use as-is
                            grid[r][col] = raw
            if not grid:
                return []
            max_row = max(grid.keys())
            max_col = max(max(grid[r].keys()) for r in grid) if grid else 0
            raw_rows = []
            for r in range(1, max_row + 1):
                raw_rows.append(
                    [grid.get(r, {}).get(c, "") for c in range(max_col + 1)]
                )
    except Exception:
        return []
    if not raw_rows:
        return []
    # Normalize: strip and coerce to str
    raw_rows = [[str(cell or "").strip() for cell in row] for row in raw_rows]
    headers = raw_rows[0]
    col_map = _detect_columns(headers)
    if not col_map:
        col_map = {"kanji": 0}
        if len(headers) > 1:
            col_map["kana"] = 1
        if len(headers) > 2:
            col_map["meaning"] = 2
    for row in raw_rows[1:]:
        w = _row_to_word(row, col_map)
        if w:
            rows.append(w)
    return rows


def parse_xlsx(path: Path) -> List[dict]:
    """Parse first sheet of an xlsx file. First row = header. Uses openpyxl if available."""
    if HAS_OPENPYXL:
        rows: List[dict] = []
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            sheet = wb.active
            if not sheet:
                return []
            raw_rows = [[str(c.value or "").strip() for c in row] for row in sheet.iter_rows()]
            wb.close()
        except Exception:
            return _parse_xlsx_stdlib(path)
        if not raw_rows:
            return []
        headers = raw_rows[0]
        col_map = _detect_columns(headers)
        if not col_map:
            col_map = {"kanji": 0}
            if len(headers) > 1:
                col_map["kana"] = 1
            if len(headers) > 2:
                col_map["meaning"] = 2
        for row in raw_rows[1:]:
            w = _row_to_word(row, col_map)
            if w:
                rows.append(w)
        return rows
    return _parse_xlsx_stdlib(path)


def parse_file(path: Path) -> List[dict]:
    """Parse CSV or xlsx file. Returns list of {kanji, kana?, meaning?}."""
    path = Path(path)
    suf = path.suffix.lower()
    if suf == ".csv":
        return parse_csv(path)
    if suf == ".xlsx":
        return parse_xlsx(path)  # uses openpyxl if available, else stdlib reader
    if suf == ".xls":
        return []  # .xls not supported without xlrd
    # Default try CSV
    return parse_csv(path)
