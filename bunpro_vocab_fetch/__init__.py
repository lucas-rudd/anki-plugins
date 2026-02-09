"""
Anki add-on: Bunpro Vocab Fetch

When adding a "Vocab Front and Back" note, type the kanji in the kanji field,
then click the "Bunpro" button in the editor. The add-on fetches the word from
bunpro.jp and suggests kana, pos, english, two example sentences (with and
without furigana), and adds the JLPT_* tag when applicable.

From the Browser: select notes, then right-click and choose "Fill from Bunpro", or use
Tools → Fill selected from Bunpro, to fetch and fill all selected notes at once.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from aqt import gui_hooks, mw
from aqt.operations import QueryOp
from aqt.qt import QAction
from aqt.utils import qconnect, tooltip

from .bunpro import fetch_vocab

# Note type we support; must have these field names (or we fill only those that exist).
VOCAB_NOTE_TYPE = "Vocab Front and Back"
FIELD_KANJI = "kanji"
FIELD_KANJI_FURIGANA = "kanji_furigana"
FIELD_KANA = "kana"
FIELD_POS = "pos"
FIELD_ENGLISH = "english"
FIELD_EX1_JA = "ex1_ja"
FIELD_EX1_JA_FURIGANA = "ex1_ja_furigana"
FIELD_EX1_EN = "ex1_en"
FIELD_EX2_JA = "ex2_ja"
FIELD_EX2_JA_FURIGANA = "ex2_ja_furigana"
FIELD_EX2_EN = "ex2_en"

FIELD_ORDER = [
    FIELD_KANJI,
    FIELD_KANA,
    FIELD_POS,
    FIELD_ENGLISH,
    FIELD_EX1_JA,
    FIELD_EX1_JA_FURIGANA,
    FIELD_EX1_EN,
    FIELD_EX2_JA,
    FIELD_EX2_JA_FURIGANA,
    FIELD_EX2_EN,
]


def _field_index_by_name(editor) -> Optional[dict]:
    """Return a dict mapping field name -> index for the current note type, or None."""
    note = editor.note
    if not note:
        return None
    model = editor.note_type()
    if not model or not model.get("flds"):
        return None
    return {fld["name"]: i for i, fld in enumerate(model["flds"])}


def _set_field_if_present(editor, name_to_index: dict, field_name: str, value: str) -> None:
    """Set a note field by name if it exists on the note type."""
    idx = name_to_index.get(field_name)
    if idx is not None and value:
        editor.note.fields[idx] = value


def _name_to_index_for_note(note) -> Optional[dict]:
    """Return field name -> index for the note's model."""
    model = note.note_type()
    if not model or not model.get("flds"):
        return None
    return {fld["name"]: i for i, fld in enumerate(model["flds"])}


def _set_note_field(note, name_to_index: dict, field_name: str, value: str) -> None:
    """Set a note field by name if it exists on the note type."""
    idx = name_to_index.get(field_name)
    if idx is not None and value and idx < len(note.fields):
        note.fields[idx] = value


def _jlpt_tag_for_level(level: Optional[str]) -> Optional[str]:
    """Map Bunpro jlpt_level to the tag we add. Unclassified → no tag; A/E/other → JLPT_N1; N1–N5 → JLPT_N1–N5."""
    if not level or not str(level).strip():
        return None
    s = str(level).strip()
    if s.lower() == "unclassified":
        return None
    # Standard JLPT: N1, N2, N3, N4, N5 → keep as JLPT_N1, JLPT_N2, ...
    if s.upper().startswith("N") and len(s) >= 2 and s[1:].isdigit():
        n = int(s[1:])
        if 1 <= n <= 5:
            return f"JLPT_N{n}"
    # A1, A2, A10, E1, etc. (vocab A1 and above) → JLPT_N1
    return "JLPT_N1"


def _normalize_pos(pos: str) -> str:
    """Map JMdict adj-f (prenominal adjective) to 'adj'; keep adj-i and adj-na as-is."""
    if not pos:
        return pos
    return pos.replace("adj-f", "adj")


def _fill_note_from_vocab(note, name_to_index: dict, kanji: str, vocab: Any) -> None:
    """Fill a note's fields and tags from Bunpro vocab data. Modifies note in place."""
    _set_note_field(note, name_to_index, FIELD_KANJI_FURIGANA, kanji)
    _set_note_field(note, name_to_index, FIELD_KANA, vocab.kana)
    _set_note_field(note, name_to_index, FIELD_POS, _normalize_pos(vocab.pos))
    _set_note_field(note, name_to_index, FIELD_ENGLISH, vocab.english)
    if vocab.examples:
        if len(vocab.examples) >= 1:
            ja_plain, ja_furi, en = vocab.examples[0]
            _set_note_field(note, name_to_index, FIELD_EX1_JA, ja_plain)
            _set_note_field(note, name_to_index, FIELD_EX1_JA_FURIGANA, ja_furi)
            _set_note_field(note, name_to_index, FIELD_EX1_EN, en)
        if len(vocab.examples) >= 2:
            ja_plain, ja_furi, en = vocab.examples[1]
            _set_note_field(note, name_to_index, FIELD_EX2_JA, ja_plain)
            _set_note_field(note, name_to_index, FIELD_EX2_JA_FURIGANA, ja_furi)
            _set_note_field(note, name_to_index, FIELD_EX2_EN, en)
    tag = _jlpt_tag_for_level(vocab.jlpt_level)
    if tag:
        tags = list(note.tags)
        if tag not in tags:
            tags.append(tag)
            note.tags = tags


def _on_bunpro_fetch(editor) -> None:
    """Fetch current kanji from Bunpro and fill note fields."""
    if not editor.note:
        tooltip("No note loaded.")
        return
    name_to_index = _field_index_by_name(editor)
    if not name_to_index:
        tooltip("Could not read note fields.")
        return
    kanji_idx = name_to_index.get(FIELD_KANJI)
    if kanji_idx is None:
        tooltip("This note type has no 'kanji' field.")
        return
    kanji = (editor.note.fields[kanji_idx] or "").strip()
    if not kanji:
        tooltip("Enter kanji in the kanji field first.")
        return

    vocab = fetch_vocab(kanji)
    if not vocab:
        tooltip("Could not find this word on Bunpro, or the page could not be loaded.")
        return

    _fill_note_from_vocab(editor.note, name_to_index, kanji, vocab)
    editor.loadNote()
    tooltip("Filled from Bunpro.")


def _add_bunpro_button(buttons: list, editor) -> None:
    """Add a 'Bunpro' button to the editor toolbar."""
    b = editor.addButton(
        None,
        "bunpro_fetch",
        _on_bunpro_fetch,
        tip="Fetch kana, POS, English, and examples from Bunpro for this word",
        label="Bunpro",
    )
    buttons.append(b)


def _run_bunpro_batch(note_ids: Sequence[int]) -> tuple:
    """Fill notes from Bunpro. Returns (filled_count, skipped_no_kanji, skipped_not_found)."""
    col = mw.col
    if not col:
        return 0, 0, 0
    filled = 0
    skipped_no_kanji = 0
    skipped_not_found = 0
    for nid in note_ids:
        try:
            note = col.get_note(nid)
        except Exception:
            continue
        name_to_index = _name_to_index_for_note(note)
        if not name_to_index:
            continue
        kanji_idx = name_to_index.get(FIELD_KANJI)
        if kanji_idx is None:
            skipped_no_kanji += 1
            continue
        kanji = (note.fields[kanji_idx] or "").strip()
        if not kanji:
            skipped_no_kanji += 1
            continue
        vocab = fetch_vocab(kanji)
        if not vocab:
            skipped_not_found += 1
            continue
        _fill_note_from_vocab(note, name_to_index, kanji, vocab)
        col.update_note(note)
        filled += 1
    return filled, skipped_no_kanji, skipped_not_found


def _on_bunpro_batch(browser) -> None:
    """Run Bunpro fill on all selected notes in the browser."""
    try:
        note_ids = list(browser.selected_notes())
    except Exception:
        tooltip("Could not get selected notes.")
        return
    if not note_ids:
        tooltip("No notes selected.")
        return

    def op(col) -> tuple:
        return _run_bunpro_batch(note_ids)

    def on_done(result: tuple) -> None:
        filled, no_kanji, not_found = result
        msg = f"Bunpro: filled {filled} note(s)."
        if no_kanji:
            msg += f" {no_kanji} skipped (no kanji)."
        if not_found:
            msg += f" {not_found} not found on Bunpro."
        tooltip(msg)
        mw.reset()

    try:
        qop = QueryOp(parent=browser, op=op, success=on_done)
        if hasattr(qop, "with_progress"):
            qop.with_progress("Fill from Bunpro…").run_in_background()
        else:
            qop.run_in_background()
    except Exception:
        tooltip("Failed to start Bunpro batch.")


def _on_tools_fill_from_bunpro() -> None:
    """Run Fill from Bunpro on the current browser selection (Tools or context menu)."""
    win = mw.app.activeWindow() if getattr(mw.app, "activeWindow", None) else None
    if win is None or not callable(getattr(win, "selected_notes", None)):
        tooltip("Open the Browser and select the notes you want to fill, then try again.")
        return
    _on_bunpro_batch(win)


def _browser_context_menu(browser, menu) -> None:
    """Add 'Fill from Bunpro' to the browser right-click menu. No browser ref kept."""
    a = QAction("Fill from Bunpro", menu)
    qconnect(a.triggered, _on_tools_fill_from_bunpro)
    menu.addAction(a)


gui_hooks.editor_did_init_buttons.append(_add_bunpro_button)
gui_hooks.browser_will_show_context_menu.append(_browser_context_menu)
_action_fill_bunpro = QAction("Fill selected from Bunpro", mw)
qconnect(_action_fill_bunpro.triggered, _on_tools_fill_from_bunpro)
mw.form.menuTools.addAction(_action_fill_bunpro)
