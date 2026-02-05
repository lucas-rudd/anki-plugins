"""
Anki add-on: Bunpro Vocab Fetch

When adding a "Vocab Front and Back" note, type the kanji in the kanji field,
then click the "Bunpro" button in the editor. The add-on fetches the word from
bunpro.jp and suggests kana, pos, english, two example sentences (with and
without furigana), and adds the JLPT_* tag when applicable.
"""

from __future__ import annotations

from typing import Optional

from aqt import gui_hooks, mw
from aqt.utils import tooltip

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

    # Fill fields (only those that exist on the note type)
    # kanji_furigana: same as kanji (no furigana); you can add furigana manually if needed
    _set_field_if_present(editor, name_to_index, FIELD_KANJI_FURIGANA, kanji)
    _set_field_if_present(editor, name_to_index, FIELD_KANA, vocab.kana)
    _set_field_if_present(editor, name_to_index, FIELD_POS, vocab.pos)
    _set_field_if_present(editor, name_to_index, FIELD_ENGLISH, vocab.english)

    if vocab.examples:
        if len(vocab.examples) >= 1:
            ja_plain, ja_furi, en = vocab.examples[0]
            _set_field_if_present(editor, name_to_index, FIELD_EX1_JA, ja_plain)
            _set_field_if_present(editor, name_to_index, FIELD_EX1_JA_FURIGANA, ja_furi)
            _set_field_if_present(editor, name_to_index, FIELD_EX1_EN, en)
        if len(vocab.examples) >= 2:
            ja_plain, ja_furi, en = vocab.examples[1]
            _set_field_if_present(editor, name_to_index, FIELD_EX2_JA, ja_plain)
            _set_field_if_present(editor, name_to_index, FIELD_EX2_JA_FURIGANA, ja_furi)
            _set_field_if_present(editor, name_to_index, FIELD_EX2_EN, en)

    # Add JLPT tag if present
    if vocab.jlpt_level:
        tag = f"JLPT_{vocab.jlpt_level}"
        tags = list(editor.note.tags)
        if tag not in tags:
            tags.append(tag)
            editor.note.tags = tags

    # Refresh editor so the user sees the filled fields
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


gui_hooks.editor_did_init_buttons.append(_add_bunpro_button)
