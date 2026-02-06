from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List


def _parse_vocab_table(lines: List[str]) -> List[Dict[str, str]]:
    """
    Given lines starting at the header row of a markdown table, parse rows into
    dicts with keys: kanji, kana, meaning, type.

    Expected header: | Word | Kanji | Meaning | Type |
    """
    out: List[Dict[str, str]] = []
    if len(lines) < 2:
        return out

    header = lines[0].strip().strip("|")
    cols = [c.strip().lower() for c in header.split("|")]
    # Basic sanity check on header columns
    if len(cols) < 3 or cols[0] != "word" or cols[1] != "kanji":
        return out

    # Skip separator row (---)
    row_lines = lines[2:]
    for line in row_lines:
        line = line.rstrip()
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        word = cells[0]  # kana / reading (may be empty)
        kanji = cells[1]
        meaning = cells[2] if len(cells) > 2 else ""
        pos = cells[3] if len(cells) > 3 else ""
        # Some rows may omit Word or Kanji; treat kanji as primary, falling back to word.
        primary = kanji or word
        if not primary:
            continue
        out.append(
            {
                "kanji": primary,
                "kana": word,
                "meaning": meaning,
                "pos": pos,
            }
        )
    return out


def parse_markdown_file(path: Path) -> List[Dict[str, str]]:
    """
    Parse a single markdown file for a '## Vocabulary' section and its table.

    Returns list of dicts: {kanji, kana, meaning, pos}.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    lines = text.splitlines()
    results: List[Dict[str, str]] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## ") and line[3:].strip().lower() == "vocabulary":
            # Collect lines until next heading or EOF
            section: List[str] = []
            j = i + 1
            while j < len(lines):
                if lines[j].startswith("#") and not lines[j].startswith("## Vocabulary"):
                    break
                section.append(lines[j])
                j += 1
            # Within section, look for the table header
            for k, sec_line in enumerate(section):
                if "| Word |" in sec_line and "| Kanji |" in sec_line:
                    table_lines = section[k : k + 2 + 100]  # header, separator, up to ~100 rows
                    results.extend(_parse_vocab_table(table_lines))
                    break
            i = j
        else:
            i += 1
    return results


def parse_markdown_folder(root: Path) -> List[Dict[str, str]]:
    """
    Walk a folder recursively and collect all vocab entries from *.md files.
    Each entry includes a 'source' key with the markdown file path.
    """
    root = Path(root)
    all_words: List[Dict[str, str]] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if not fname.lower().endswith(".md"):
                continue
            fpath = Path(dirpath) / fname
            items = parse_markdown_file(fpath)
            for item in items:
                item = dict(item)
                item["source"] = str(fpath)
                all_words.append(item)
    return all_words

