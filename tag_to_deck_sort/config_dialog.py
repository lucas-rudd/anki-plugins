"""
Config dialog for Tag → Deck Sort add-on.

Lets users pick tags and decks from their collection instead of editing JSON.
"""

from typing import Any, Dict, List

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    Qt,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showWarning, tooltip

# Add-on module name for getConfig/writeConfig (this file is tag_to_deck_sort.config_dialog)
ADDON_MODULE = __name__.rsplit(".", 1)[0]


def _deck_names() -> List[str]:
    """Return sorted list of deck names in the collection."""
    if not mw.col:
        return []
    return sorted(
        entry.name for entry in mw.col.decks.all_names_and_ids()
    )


def _tag_list() -> List[str]:
    """Return sorted list of tags in the collection."""
    if not mw.col:
        return []
    return sorted(mw.col.tags.all())


def _get_current_config() -> Dict[str, Any]:
    """Return current add-on config (merged with defaults)."""
    from . import DEFAULT_CONFIG

    user = mw.addonManager.getConfig(ADDON_MODULE) or {}
    cfg = dict(DEFAULT_CONFIG)
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg[key], **value}
        else:
            cfg[key] = value
    return cfg


def _save_config(cfg: Dict[str, Any]) -> None:
    """Persist config so getConfig() will return it (meta.json)."""
    mw.addonManager.writeConfig(ADDON_MODULE, cfg)


class TagDeckConfigDialog(QDialog):
    """Dialog to edit tag→deck mapping, priority, protected decks, and auto-sort."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tag → Deck Sort — Config")
        self._tag_deck_rows: List[tuple] = []  # (row_layout, tag_combo, deck_combo, remove_btn)
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Tag → Deck mapping ---
        map_group = QGroupBox("Tag → Deck mapping (priority = row order)")
        map_layout = QVBoxLayout(map_group)
        map_layout.addWidget(
            QLabel("Each row: when a note has the tag, move its cards to the deck. First row = highest priority if note has multiple tags.")
        )
        self._mapping_layout = QVBoxLayout()
        map_layout.addLayout(self._mapping_layout)
        row_buttons = QHBoxLayout()
        add_btn = QPushButton("Add mapping")
        add_btn.clicked.connect(self._add_mapping_row)
        row_buttons.addWidget(add_btn)
        row_buttons.addStretch()
        map_layout.addLayout(row_buttons)
        layout.addWidget(map_group)

        # --- Protected decks ---
        prot_group = QGroupBox("Protected decks")
        prot_layout = QVBoxLayout(prot_group)
        prot_layout.addWidget(
            QLabel("Cards in these decks are never moved by this add-on.")
        )
        self._protected_list = QListWidget()
        self._protected_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        prot_layout.addWidget(self._protected_list)
        layout.addWidget(prot_group)

        # --- Auto-sort ---
        self._auto_sort_check = QCheckBox("Auto-sort when adding new cards")
        layout.addWidget(self._auto_sort_check)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_mapping_rows(self) -> None:
        for row_layout, tag_combo, deck_combo, remove_btn in self._tag_deck_rows:
            self._mapping_layout.removeItem(row_layout)
            row_layout.deleteLater()
            tag_combo.deleteLater()
            deck_combo.deleteLater()
            remove_btn.deleteLater()
        self._tag_deck_rows.clear()

    def _add_mapping_row(self, tag: str = "", deck: str = "") -> None:
        tags = _tag_list()
        decks = _deck_names()
        tag_combo = QComboBox()
        tag_combo.setEditable(True)
        tag_combo.addItem("")
        tag_combo.addItems(tags)
        if tag:
            idx = tag_combo.findText(tag)
            if idx >= 0:
                tag_combo.setCurrentIndex(idx)
            else:
                tag_combo.setCurrentText(tag)
        deck_combo = QComboBox()
        deck_combo.setEditable(True)
        deck_combo.addItem("")
        deck_combo.addItems(decks)
        if deck:
            idx = deck_combo.findText(deck)
            if idx >= 0:
                deck_combo.setCurrentIndex(idx)
            else:
                deck_combo.setCurrentText(deck)
        remove_btn = QPushButton("Remove")
        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel("Tag:"))
        row_layout.addWidget(tag_combo, 1)
        row_layout.addWidget(QLabel("→ Deck:"))
        row_layout.addWidget(deck_combo, 1)
        row_layout.addWidget(remove_btn)

        def on_remove() -> None:
            self._mapping_layout.removeItem(row_layout)
            row_layout.deleteLater()
            tag_combo.deleteLater()
            deck_combo.deleteLater()
            remove_btn.deleteLater()
            self._tag_deck_rows.remove((row_layout, tag_combo, deck_combo, remove_btn))

        remove_btn.clicked.connect(on_remove)
        self._mapping_layout.addLayout(row_layout)
        self._tag_deck_rows.append((row_layout, tag_combo, deck_combo, remove_btn))

    def _load_config(self) -> None:
        cfg = _get_current_config()
        self._clear_mapping_rows()
        mapping = cfg.get("tag_to_deck") or {}
        priority = cfg.get("priority") or []
        # Show rows in priority order; if priority missing, use mapping order
        order = priority if priority else list(mapping.keys())
        seen = set()
        for tag in order:
            tag_lower = str(tag).lower()
            if tag_lower in seen:
                continue
            seen.add(tag_lower)
            deck = mapping.get(tag_lower) or mapping.get(tag) or ""
            self._add_mapping_row(tag=tag if isinstance(tag, str) else tag_lower, deck=deck)
        for tag, deck in mapping.items():
            if tag.lower() not in seen:
                self._add_mapping_row(tag=tag, deck=deck)

        # Protected decks
        protected = set(cfg.get("protected_decks") or [])
        self._protected_list.clear()
        for name in _deck_names():
            item = QListWidgetItem(name)
            item.setCheckState(
                Qt.CheckState.Checked if name in protected else Qt.CheckState.Unchecked
            )
            self._protected_list.addItem(item)

        self._auto_sort_check.setChecked(bool(cfg.get("auto_sort_on_add", True)))

    def _on_accept(self) -> None:
        tag_to_deck: Dict[str, str] = {}
        priority: List[str] = []
        for _, tag_combo, deck_combo, _ in self._tag_deck_rows:
            tag = (tag_combo.currentText() or "").strip()
            deck = (deck_combo.currentText() or "").strip()
            if not tag:
                continue
            tag_norm = tag.lower()
            tag_to_deck[tag_norm] = deck
            priority.append(tag_norm)
        protected_decks: List[str] = []
        for i in range(self._protected_list.count()):
            item = self._protected_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                protected_decks.append(item.text())
        cfg = {
            "tag_to_deck": tag_to_deck,
            "priority": priority,
            "protected_decks": protected_decks,
            "auto_sort_on_add": self._auto_sort_check.isChecked(),
        }
        _save_config(cfg)
        tooltip("Config saved.")
        self.accept()


def open_config_dialog() -> None:
    """Open the config dialog (called when user clicks Config on the add-on)."""
    if not mw.col:
        showWarning("Please open a profile first.")
        return
    dlg = TagDeckConfigDialog(mw)
    mw.tag_to_deck_sort_config_dialog = dlg  # keep reference
    dlg.exec()  # modal: stays on top, blocks add-ons window until closed
