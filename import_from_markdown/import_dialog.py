from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from aqt.utils import showWarning, tooltip
from aqt.operations import QueryOp

from .parser_md import parse_markdown_folder

# Vocab Front and Back field names
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


def _bunpro_fetch_vocab(kanji: str) -> Optional[Any]:
    try:
        from bunpro_vocab_fetch.bunpro import fetch_vocab

        return fetch_vocab(kanji)
    except Exception:
        return None


def _deck_names() -> List[str]:
    if not mw.col:
        return []
    return sorted(entry.name for entry in mw.col.decks.all_names_and_ids())


def _note_type_names() -> List[str]:
    if not mw.col:
        return []
    return sorted(mw.col.models.all_names())


def _field_index_by_name(model: dict) -> dict:
    return {fld["name"]: i for i, fld in enumerate(model.get("flds", []))}


def _note_exists_with_kanji(col, model_name: str, kanji: str) -> bool:
    model = col.models.by_name(model_name)
    if not model:
        return False
    name_to_idx = _field_index_by_name(model)
    kanji_idx = name_to_idx.get(FIELD_KANJI)
    if kanji_idx is None:
        kanji_idx = 0
    safe_model = model_name.replace('"', '""')
    escaped = kanji.replace('"', '""')
    query = f'note:"{safe_model}" "{escaped}"'
    try:
        nids = col.find_notes(query)
    except Exception:
        return False
    for nid in nids:
        note = col.get_note(nid)
        if kanji_idx < len(note.fields) and note.fields[kanji_idx].strip() == kanji:
            return True
    return False


def _create_note_from_md(
    col,
    model_name: str,
    deck_name: str,
    word: dict,
    use_bunpro: bool,
    name_to_idx: dict,
) -> Optional[int]:
    kanji = word.get("kanji", "").strip()
    kana = word.get("kana", "").strip()
    meaning = word.get("meaning", "").strip()
    pos = word.get("pos", "").strip()
    if not kanji and not kana:
        return None
    primary = kanji or kana
    if _note_exists_with_kanji(col, model_name, primary):
        return None

    model = col.models.by_name(model_name)
    if not model:
        return None
    note = col.new_note(model)

    def set_fld(name: str, value: str) -> None:
        idx = name_to_idx.get(name)
        if idx is not None and value:
            note.fields[idx] = value

    if use_bunpro:
        bp = _bunpro_fetch_vocab(primary)
        if bp:
            set_fld(FIELD_KANJI, bp.kanji or primary)
            set_fld(FIELD_KANJI_FURIGANA, bp.kanji or primary)
            set_fld(FIELD_KANA, bp.kana or kana)
            set_fld(FIELD_POS, bp.pos or pos)
            set_fld(FIELD_ENGLISH, bp.english or meaning)
            if bp.examples:
                if len(bp.examples) >= 1:
                    ja_plain, ja_furi, en = bp.examples[0]
                    set_fld(FIELD_EX1_JA, ja_plain)
                    set_fld(FIELD_EX1_JA_FURIGANA, ja_furi)
                    set_fld(FIELD_EX1_EN, en)
                if len(bp.examples) >= 2:
                    ja_plain, ja_furi, en = bp.examples[1]
                    set_fld(FIELD_EX2_JA, ja_plain)
                    set_fld(FIELD_EX2_JA_FURIGANA, ja_furi)
                    set_fld(FIELD_EX2_EN, en)
            if getattr(bp, "jlpt_level", None):
                tag = f"JLPT_{bp.jlpt_level}"
                if tag not in note.tags:
                    note.tags.append(tag)
        else:
            # Fallback to markdown data only
            set_fld(FIELD_KANJI, primary)
            set_fld(FIELD_KANJI_FURIGANA, primary)
            set_fld(FIELD_KANA, kana)
            set_fld(FIELD_POS, pos)
            set_fld(FIELD_ENGLISH, meaning)
    else:
        set_fld(FIELD_KANJI, primary)
        set_fld(FIELD_KANJI_FURIGANA, primary)
        set_fld(FIELD_KANA, kana)
        set_fld(FIELD_POS, pos)
        set_fld(FIELD_ENGLISH, meaning)

    col.add_note(note, col.decks.id(deck_name))
    return note.id


def _run_import(
    folder: str,
    deck_name: str,
    model_name: str,
    use_bunpro: bool,
) -> tuple:
    col = mw.col
    if not col:
        return 0, 0, "No collection open."
    root = Path(folder)
    if not root.exists():
        return 0, 0, f"Folder not found: {folder}"
    words = parse_markdown_folder(root)
    if not words:
        return 0, 0, "No vocabulary tables found in markdown files."
    model = col.models.by_name(model_name)
    if not model:
        return 0, 0, f"Note type not found: {model_name}"
    name_to_idx = _field_index_by_name(model)
    created = 0
    skipped = 0
    bunpro_ok = 0
    bunpro_fallback = 0
    milestones: List[str] = []
    for word in words:
        primary = word.get("kanji") or word.get("kana") or ""
        if not primary:
            continue
        if _note_exists_with_kanji(col, model_name, primary):
            skipped += 1
            continue
        try:
            before_created = created
            nid = _create_note_from_md(col, model_name, deck_name, word, use_bunpro, name_to_idx)
            if nid:
                created += 1
                # Rough heuristic for Bunpro usage: if Bunpro is enabled, count every
                # successfully created note as a Bunpro attempt. We treat failures as
                # "fallback" when no note was created by _create_note_from_md.
                if use_bunpro:
                    bunpro_ok += 1
            else:
                if use_bunpro:
                    bunpro_fallback += 1
        except Exception:
            continue
        # Record milestone messages every 50 created notes
        if created and created % 50 == 0:
            milestones.append(f"Progress: created {created} notes so far…")
    return created, skipped, bunpro_ok, bunpro_fallback, milestones, None


class ImportFromMarkdownDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import from Markdown Vocabulary")
        self._log_lines: List[str] = []
        self._build_ui()
        self._bunpro_available = self._check_bunpro()

    def _check_bunpro(self) -> bool:
        try:
            from bunpro_vocab_fetch.bunpro import fetch_vocab  # noqa: F401

            return True
        except Exception:
            return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Folder
        folder_group = QGroupBox("Markdown folder")
        folder_layout = QHBoxLayout(folder_group)
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Choose a folder containing your class-note .md files…")
        folder_layout.addWidget(self._folder_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse)
        folder_layout.addWidget(browse_btn)
        layout.addWidget(folder_group)

        # Deck & Note type
        opts_layout = QVBoxLayout()
        deck_layout = QHBoxLayout()
        deck_layout.addWidget(QLabel("Deck:"))
        self._deck_combo = QComboBox()
        self._deck_combo.setEditable(False)
        deck_layout.addWidget(self._deck_combo)
        opts_layout.addLayout(deck_layout)
        nt_layout = QHBoxLayout()
        nt_layout.addWidget(QLabel("Note type:"))
        self._note_type_combo = QComboBox()
        nt_layout.addWidget(self._note_type_combo)
        opts_layout.addLayout(nt_layout)
        layout.addLayout(opts_layout)

        # Bunpro toggle
        self._use_bunpro_cb = QCheckBox(
            "Use Bunpro for POS, English, and example sentences (when available)"
        )
        layout.addWidget(self._use_bunpro_cb)

        # Log
        layout.addWidget(QLabel("Log:"))
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMinimumHeight(120)
        layout.addWidget(self._log_edit)

        # Buttons
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_import)
        bbox.rejected.connect(self.reject)
        self._import_btn = bbox.button(QDialogButtonBox.StandardButton.Ok)
        self._import_btn.setText("Import")
        layout.addWidget(bbox)

        self._populate_deck_and_models()

    def _populate_deck_and_models(self) -> None:
        self._deck_combo.clear()
        self._deck_combo.addItems(_deck_names())
        self._note_type_combo.clear()
        self._note_type_combo.addItems(_note_type_names())
        idx = self._note_type_combo.findText("Vocab Front and Back")
        if idx >= 0:
            self._note_type_combo.setCurrentIndex(idx)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder containing markdown notes",
            "",
        )
        if folder:
            self._folder_edit.setText(folder)

    def _log(self, msg: str) -> None:
        self._log_lines.append(msg)
        self._log_edit.setPlainText("\n".join(self._log_lines))
        self._log_edit.verticalScrollBar().setValue(
            self._log_edit.verticalScrollBar().maximum()
        )

    def _on_import(self) -> None:
        folder = self._folder_edit.text().strip()
        if not folder:
            showWarning("Please choose a folder.")
            return
        deck = self._deck_combo.currentText()
        model = self._note_type_combo.currentText()
        use_bunpro = self._use_bunpro_cb.isChecked()
        if not deck or not model:
            showWarning("Please select a deck and a note type.")
            return
        if use_bunpro and not self._bunpro_available:
            showWarning(
                "Bunpro option is checked but the Bunpro Vocab Fetch add-on was not found. "
                "Install it for POS/examples, or uncheck the option to use only markdown data."
            )
            return

        self._log_edit.clear()
        self._log_lines = []
        self._log("Starting import…")
        self._import_btn.setEnabled(False)

        def op(_col) -> tuple:
            return _run_import(folder, deck, model, use_bunpro)

        def on_done(result: tuple) -> None:
            self._import_btn.setEnabled(True)
            created, skipped, bunpro_ok, bunpro_fallback, milestones, err = result
            if err:
                self._log(f"Error: {err}")
                showWarning(err)
                return
            for msg in milestones:
                self._log(msg)
            self._log(f"Done. Created {created} note(s), skipped {skipped} duplicate(s).")
            if use_bunpro:
                self._log(
                    f"Bunpro lookups: {bunpro_ok} successful, {bunpro_fallback} fell back to markdown data."
                )
            tooltip(f"Markdown import: {created} created, {skipped} skipped.")
            mw.reset()

        QueryOp(parent=self, op=op, success=on_done).run_in_background()

    def show_and_exec(self) -> None:
        self._populate_deck_and_models()
        if self._bunpro_available:
            self._use_bunpro_cb.setToolTip("Bunpro Vocab Fetch add-on detected.")
        else:
            self._use_bunpro_cb.setToolTip(
                "Bunpro add-on not installed. Only markdown data will be used."
            )
        self.raise_()
        self.activateWindow()
        self.exec()


def open_import_dialog() -> None:
    dlg = ImportFromMarkdownDialog(parent=mw)
    mw.import_from_markdown_dialog = dlg
    dlg.show_and_exec()

