"""
Import from Mazii dialog: file selection, deck/note type, Bunpro toggle, and import execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDesktopServices,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QUrl,
    QVBoxLayout,
)
from aqt.utils import showWarning, tooltip
from aqt.operations import QueryOp

from .parser import parse_file

# Vocab Front and Back field names (same as bunpro add-on when we use it)
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

MAZII_NOTE_URL = "https://mazii.net/en-US/note"


def _bunpro_fetch_vocab(kanji: str) -> Optional[Any]:
    """Return Bunpro data for kanji if the Bunpro add-on is available, else None."""
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
    """Return field name -> index for the given note type."""
    return {fld["name"]: i for i, fld in enumerate(model.get("flds", []))}


def _note_exists_with_kanji(col, model_name: str, kanji: str) -> bool:
    """True if a note of this type already has this kanji in the kanji field."""
    model = col.models.by_name(model_name)
    if not model:
        return False
    name_to_idx = _field_index_by_name(model)
    kanji_idx = name_to_idx.get(FIELD_KANJI)
    if kanji_idx is None:
        # No kanji field: use first field
        kanji_idx = 0
    # Search: note type and phrase (kanji). Quote model name and kanji for exact match.
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


def _create_note_from_mazii(
    col,
    model_name: str,
    deck_name: str,
    word: dict,
    use_bunpro: bool,
    name_to_idx: dict,
) -> Optional[int]:
    """Create one note. Returns note id if created, else None (e.g. duplicate)."""
    if _note_exists_with_kanji(col, model_name, word["kanji"]):
        return None
    model = col.models.by_name(model_name)
    if not model:
        return None
    note = col.new_note(model)
    kanji = word["kanji"]

    def set_fld(name: str, value: str) -> None:
        idx = name_to_idx.get(name)
        if idx is not None and value:
            note.fields[idx] = value

    if use_bunpro:
        bp = _bunpro_fetch_vocab(kanji)
        if bp:
            set_fld(FIELD_KANJI, kanji)
            set_fld(FIELD_KANJI_FURIGANA, kanji)
            set_fld(FIELD_KANA, bp.kana)
            set_fld(FIELD_POS, bp.pos)
            set_fld(FIELD_ENGLISH, bp.english)
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
            if bp.jlpt_level:
                tag = f"JLPT_{bp.jlpt_level}"
                if tag not in note.tags:
                    note.tags.append(tag)
        else:
            # Bunpro failed: use Mazii row only
            set_fld(FIELD_KANJI, kanji)
            set_fld(FIELD_KANJI_FURIGANA, kanji)
            set_fld(FIELD_KANA, word.get("kana", ""))
            set_fld(FIELD_ENGLISH, word.get("meaning", ""))
    else:
        set_fld(FIELD_KANJI, kanji)
        set_fld(FIELD_KANJI_FURIGANA, kanji)
        set_fld(FIELD_KANA, word.get("kana", ""))
        set_fld(FIELD_ENGLISH, word.get("meaning", ""))

    col.add_note(note, col.decks.id(deck_name))
    return note.id


def _run_import(
    path: str,
    deck_name: str,
    model_name: str,
    use_bunpro: bool,
) -> tuple:
    """Run import in background. Returns (created_count, skipped_duplicate_count, error_message?)."""
    col = mw.col
    if not col:
        return 0, 0, "No collection open."
    path = Path(path)
    if not path.exists():
        return 0, 0, f"File not found: {path}"
    words = parse_file(path)
    if not words:
        return 0, 0, "No words found in file. Check format (CSV or xlsx with Word/Kanji column)."
    model = col.models.by_name(model_name)
    if not model:
        return 0, 0, f"Note type not found: {model_name}"
    name_to_idx = _field_index_by_name(model)
    created = 0
    skipped = 0
    for word in words:
        if _note_exists_with_kanji(col, model_name, word["kanji"]):
            skipped += 1
            continue
        try:
            nid = _create_note_from_mazii(col, model_name, deck_name, word, use_bunpro, name_to_idx)
            if nid:
                created += 1
        except Exception:
            pass  # skip failed note; could collect and report
    return created, skipped, None


class ImportFromMaziiDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import from Mazii")
        self._log_lines: List[str] = []
        self._build_ui()
        self._bunpro_available = self._check_bunpro()

    def _check_bunpro(self) -> bool:
        try:
            from bunpro_vocab_fetch.bunpro import fetch_vocab
            return True
        except Exception:
            return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # File
        file_group = QGroupBox("Mazii export file")
        file_layout = QHBoxLayout(file_group)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Choose a CSV or Excel file exported from Mazii…")
        file_layout.addWidget(self._path_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)

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

        # Bunpro
        self._use_bunpro_cb = QCheckBox(
            "Use Bunpro for POS, English, and example sentences (when available)"
        )
        layout.addWidget(self._use_bunpro_cb)

        # Open Mazii
        open_btn = QPushButton("Open Mazii Notebooks in browser")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(MAZII_NOTE_URL)))
        layout.addWidget(open_btn)

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
        # Default to "Vocab Front and Back" if present
        idx = self._note_type_combo.findText("Vocab Front and Back")
        if idx >= 0:
            self._note_type_combo.setCurrentIndex(idx)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Mazii export file",
            "",
            "CSV or Excel (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx);;All files (*)",
        )
        if path:
            self._path_edit.setText(path)

    def _log(self, msg: str) -> None:
        self._log_lines.append(msg)
        self._log_edit.setPlainText("\n".join(self._log_lines))
        self._log_edit.verticalScrollBar().setValue(self._log_edit.verticalScrollBar().maximum())

    def _on_import(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            showWarning("Please choose a file.")
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
                "Install it for POS/examples, or uncheck the option to use only Mazii data."
            )
            return

        self._log_edit.clear()
        self._log_lines = []
        self._log("Starting import…")
        self._import_btn.setEnabled(False)

        def op(_col) -> tuple:
            return _run_import(path, deck, model, use_bunpro)

        def on_done(result: tuple) -> None:
            self._import_btn.setEnabled(True)
            created, skipped, err = result
            if err:
                self._log(f"Error: {err}")
                showWarning(err)
                return
            self._log(f"Done. Created {created} note(s), skipped {skipped} duplicate(s).")
            tooltip(f"Import done: {created} created, {skipped} skipped.")
            mw.reset()

        QueryOp(parent=self, op=op, success=on_done).run_in_background()

    def show_and_exec(self) -> None:
        self._populate_deck_and_models()
        if self._bunpro_available:
            self._use_bunpro_cb.setToolTip("Bunpro Vocab Fetch add-on detected.")
        else:
            self._use_bunpro_cb.setToolTip(
                "Bunpro add-on not installed. Only Mazii file data will be used."
            )
        self.raise_()
        self.activateWindow()
        self.exec()


def open_import_dialog() -> None:
    """Open the Import from Mazii dialog (modal). Keep a reference so it is not garbage-collected."""
    dlg = ImportFromMaziiDialog(parent=mw)
    mw.import_from_mazii_dialog = dlg
    dlg.show_and_exec()
