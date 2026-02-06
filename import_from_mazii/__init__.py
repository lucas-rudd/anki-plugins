"""
Anki add-on: Import from Mazii

Import vocabulary from a Mazii notebook export (Excel or CSV) into Anki.
Optionally use the Bunpro Vocab Fetch add-on to fill POS, English, and
example sentences for each word.
"""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import qconnect

from .import_dialog import open_import_dialog


def _on_import_from_mazii() -> None:
    """Open the Import from Mazii dialog."""
    open_import_dialog()


def _add_tools_menu_action() -> None:
    action = QAction("Import from Mazii", mw)
    qconnect(action.triggered, _on_import_from_mazii)
    mw.form.menuTools.addAction(action)


def _on_profile_did_open() -> None:
    _add_tools_menu_action()


gui_hooks.profile_did_open.append(_on_profile_did_open)
