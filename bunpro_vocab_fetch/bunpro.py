# Fetch and parse Bunpro vocab page data from __NEXT_DATA__ JSON.
# Bunpro uses Next.js and embeds vocab + example sentences in the initial HTML.

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) compatible; Anki Bunpro Vocab Fetch"


@dataclass
class BunproVocab:
    """Parsed vocab entry from Bunpro."""

    kanji: str
    kana_furigana: str
    kana: str
    pos: str  # comma-separated, e.g. "n" or "n, vs, vt"
    english: str  # comma-separated definitions
    jlpt_level: Optional[str]  # "N1", "N2", ... or None
    examples: List[tuple]  # [(ja_plain, ja_furigana, en), ...]


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").strip()
    return text


def _ja_plain_from_content(content: str, kanji_answer: Optional[str], kana_answer: str) -> str:
    """Convert Bunpro sentence content to plain Japanese (no furigana).
    Content looks like: 日本（にほん）の学生（がくせい）は____を着（き）ています。
    We remove (reading) and replace ____ with kanji or kana.
    """
    if not content:
        return ""
    # Replace the blank placeholder with the word (prefer kanji if we have it)
    word = kanji_answer if kanji_answer else kana_answer
    content = re.sub(r"<span[^>]*>____</span>", word, content, flags=re.IGNORECASE)
    content = content.replace("____", word)
    # Remove furigana in parentheses: 日本（にほん） -> 日本
    content = re.sub(r"（[^）]+）", "", content)
    content = _strip_html(content)
    return content.strip()


def _ja_furigana_from_content(content: str, kanji_answer: Optional[str], kana_answer: str) -> str:
    """Convert to Japanese with <ruby> furigana for Anki.
    Bunpro format: 日本（にほん）の学生（がくせい）は____を着（き）ています。
    We want: <ruby>日本<rt>にほん</rt></ruby>の<ruby>学生<rt>がくせい</rt></ruby>は制服を<ruby>着<rt>き</rt></ruby>ています。
    """
    if not content:
        return ""
    word = kanji_answer if kanji_answer else kana_answer
    content = re.sub(r"<span[^>]*>____</span>", word, content, flags=re.IGNORECASE)
    content = content.replace("____", word)
    # Replace each 漢字（reading） with <ruby>漢字<rt>reading</rt></ruby>
    # The base is the run of non-space, non-（ characters immediately before （
    # Base must be kanji or katakana so we don't group particles (の, は) with the word
    kanji_katakana = r"[\u4e00-\u9fff\u30a0-\u30ff]+"
    result: List[str] = []
    i = 0
    while i < len(content):
        m = re.match(r"(" + kanji_katakana + r")（([^）]+)）", content[i:])
        if m:
            base, reading = m.group(1), m.group(2)
            result.append(f"<ruby>{base}<rt>{reading}</rt></ruby>")
            i += len(m.group(0))
        else:
            # No match: emit one character and continue (so we reach 学生 in "の学生（がくせい）")
            result.append(content[i : i + 1])
            i += 1
    # Strip only non-ruby HTML (e.g. <span>) so Anki can render <ruby>
    out = "".join(result)
    out = re.sub(r"<span[^>]*>.*?</span>", "", out, flags=re.IGNORECASE | re.DOTALL)
    return out.strip()


def _en_from_translation(translation: str) -> str:
    """Strip <strong> etc. from English translation."""
    return _strip_html(translation or "").strip()


def fetch_vocab(kanji: str) -> Optional[BunproVocab]:
    """Fetch Bunpro vocab page for the given kanji and parse __NEXT_DATA__.

    URL format: https://bunpro.jp/vocabs/<url_encoded_kanji>
    Returns None if the page fails or doesn't contain vocab data.
    """
    encoded = urllib.parse.quote(kanji.strip())
    url = f"https://bunpro.jp/vocabs/{encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError):
        return None

    # Extract __NEXT_DATA__
    marker = '__NEXT_DATA__" type="application/json">'
    if marker not in html:
        return None
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    try:
        data = json.loads(html[start:end])
    except json.JSONDecodeError:
        return None

    page_props = data.get("props", {}).get("pageProps", {})
    reviewable = page_props.get("reviewable") or {}
    included = page_props.get("included") or {}
    study_questions = included.get("studyQuestions") or []

    # Basic fields
    title = (reviewable.get("title") or kanji).strip()
    kana = (reviewable.get("kana") or "").strip()
    jlpt_level = reviewable.get("jlpt_level")  # "N1", "N2", ...
    meaning = (reviewable.get("meaning") or "").strip()

    # English: prefer 'meaning', else from jmdict_data gloss
    if not meaning and reviewable.get("jmdict_data"):
        senses = reviewable.get("jmdict_data", {}).get("sense", [])
        glosses = []
        for s in senses:
            for g in s.get("gloss", []):
                if g.get("lang") == "eng" and g.get("text"):
                    glosses.append(g["text"])
        meaning = ", ".join(glosses)

    # POS: from jmdict_data sense[].partOfSpeech (already codes like n, vs, vt, adj-i, adj-na)
    pos_parts = []
    seen = set()
    for sense in reviewable.get("jmdict_data", {}).get("sense", []) or []:
        for p in sense.get("partOfSpeech", []) or []:
            if p and p not in seen:
                seen.add(p)
                pos_parts.append(p)
    pos = ", ".join(pos_parts) if pos_parts else ""

    # Examples (at least 2)
    examples = []
    for q in study_questions[:5]:
        content = q.get("content") or ""
        translation = q.get("translation") or ""
        answer_kana = q.get("answer") or ""
        kanji_ans = q.get("kanji_answer")
        if not content or not translation:
            continue
        ja_plain = _ja_plain_from_content(content, kanji_ans, answer_kana)
        ja_furigana = _ja_furigana_from_content(content, kanji_ans, answer_kana)
        en = _en_from_translation(translation)
        if ja_plain and en:
            examples.append((ja_plain, ja_furigana, en))
        if len(examples) >= 2:
            break

    return BunproVocab(
        kanji=title,
        kana=kana,
        pos=pos,
        english=meaning,
        jlpt_level=jlpt_level,
        examples=examples,
    )
