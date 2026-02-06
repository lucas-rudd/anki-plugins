"""
Anki add-on: Import from Markdown Vocabulary

Scan a folder of class-note markdown files for a '## Vocabulary' section with
the table '| Word | Kanji | Meaning | Type |', and create notes from those
entries. Optionally use the Bunpro Vocab Fetch add-on to fill POS, English,
and example sentences.
"""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import qconnect

from .import_dialog import open_import_dialog


def _on_import_from_markdown() -> None:
    open_import_dialog()


def _add_tools_menu_action() -> None:
    action = QAction("Import from Markdown Vocabulary", mw)
    qconnect(action.triggered, _on_import_from_markdown)
    mw.form.menuTools.addAction(action)


def _on_profile_did_open() -> None:
    _add_tools_menu_action()


gui_hooks.profile_did_open.append(_on_profile_did_open)

