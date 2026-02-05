"""
Anki add-on: JLPT Tag Deck Auto-Sorter

Automatically moves cards into JLPT decks based on their JLPT_* tags.

By default, the mapping and behavior are:

Mapping (tag -> deck name):
- JLPT_N2 -> 0_JLPT N2
- JLPT_N1 -> 1_JLPT N1
- JLPT_N3 -> JLPT N3
- JLPT_N4 -> JLPT N4
- JLPT_N5 -> JLPT N5

Priority (when multiple JLPT_* tags are present on a note):
- JLPT_N2, then JLPT_N1, JLPT_N3, JLPT_N4, JLPT_N5

Special decks that are never auto-moved even if tagged:
- Government Agencies
- Food
- Linguistics
- People

All of the above can be customized from
Add-ons → JLPT Tag Deck Auto-Sorter → Config.
"""

from typing import Dict, Iterable, List, Optional, Sequence, Set

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import qconnect, tooltip


# Default configuration; users can override this in the add-on's config.json UI.
DEFAULT_CONFIG = {
    # Map normalized JLPT tag -> desired deck name
    "tag_to_deck": {
        "jlpt_n2": "0_JLPT N2",
        "jlpt_n1": "1_JLPT N1",
        "jlpt_n3": "JLPT N3",
        "jlpt_n4": "JLPT N4",
        "jlpt_n5": "JLPT N5",
    },
    # Priority when multiple JLPT tags are present on a note.
    "priority": [
        "jlpt_n2",
        "jlpt_n1",
        "jlpt_n3",
        "jlpt_n4",
        "jlpt_n5",
    ],
    # Decks that should never be auto-moved by this add-on.
    "protected_decks": [
        "Government Agencies",
        "Food",
        "Linguistics",
        "People",
    ],
    # If false, new cards will not be auto-sorted; you can still run
    # the manual Tools → JLPT: Auto-sort decks from tags action.
    "auto_sort_on_add": True,
}


def _get_config() -> Dict:
    """Return the current configuration, merged with defaults.

    Values in the user's config override the defaults.
    """
    user_cfg = mw.addonManager.getConfig(__name__) or {}
    cfg = DEFAULT_CONFIG.copy()

    # Shallow-merge dictionaries like tag_to_deck and protected_decks.
    for key, value in user_cfg.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            merged = cfg[key].copy()
            merged.update(value)
            cfg[key] = merged
        else:
            cfg[key] = value
    return cfg


def _normalize_tags(tags: Sequence[str]) -> Set[str]:
    """Return a lowercased set of tags."""
    return {t.lower() for t in tags}


def _best_jlpt_tag(normalized_tags: Set[str]) -> Optional[str]:
    """Return the 'highest priority' JLPT tag, or None if none are present.

    Priority is based on the user's desired study order:
    N2 (current focus) > N1 > N3 > N4 > N5 by default.
    The exact order is configurable.
    """
    cfg = _get_config()
    priority: Sequence[str] = cfg.get("priority", [])
    for tag in priority:
        tag_norm = str(tag).lower()
        if tag_norm in normalized_tags:
            return tag_norm
    return None


def _deck_name_for_tag(jlpt_tag: str) -> Optional[str]:
    """Map a JLPT tag like 'jlpt_n2' to a deck name."""
    cfg = _get_config()
    mapping = cfg.get("tag_to_deck", {}) or {}
    if not isinstance(mapping, dict):
        return None
    # Normalize keys once
    normalized_mapping = {str(k).lower(): v for k, v in mapping.items()}
    return normalized_mapping.get(jlpt_tag)


def _is_protected_deck(deck_name: str) -> bool:
    """Return True if a deck should never be auto-moved."""
    cfg = _get_config()
    protected = cfg.get("protected_decks", []) or []
    return deck_name in protected


def _move_cards_to_deck(card_ids: Iterable[int], deck_name: str) -> int:
    """Move the given card IDs into the target deck. Returns count moved."""
    card_ids = list(card_ids)
    if not card_ids:
        return 0

    col = mw.col
    # This will create the deck if it does not exist yet.
    deck_id = col.decks.id(deck_name)

    # Anki 2.1.36+ API
    col.set_deck(card_ids, deck_id)
    return len(card_ids)


def _sort_note_cards_by_tags(note_id: int) -> int:
    """Apply JLPT tag-based deck sorting to all cards of a single note.

    Returns the number of cards moved.
    """
    col = mw.col
    note = col.get_note(note_id)
    normalized_tags = _normalize_tags(note.tags)

    jlpt_tag = _best_jlpt_tag(normalized_tags)
    if not jlpt_tag:
        return 0

    deck_name = _deck_name_for_tag(jlpt_tag)
    if not deck_name:
        return 0

    to_move: List[int] = []
    for card in note.cards():
        deck = col.decks.get(card.did)
        deck_name_current = deck.get("name", "")
        # Skip protected decks entirely.
        if _is_protected_deck(deck_name_current):
            continue
        to_move.append(card.id)

    if not to_move:
        return 0

    return _move_cards_to_deck(to_move, deck_name)


def sort_entire_collection() -> None:
    """Sort all notes in the collection based on JLPT tags.

    This is exposed as a Tools menu action so you can run it on demand.
    """
    col = mw.col

    note_ids = col.db.list("SELECT id FROM notes")
    moved_total = 0

    for nid in note_ids:
        moved_total += _sort_note_cards_by_tags(nid)

    col.reset()
    mw.reset()

    if moved_total:
        tooltip(f"JLPT auto-sort: moved {moved_total} cards.")
    else:
        tooltip("JLPT auto-sort: no cards needed moving.")


def _on_note_added(note) -> None:
    """Hook callback: run after cards have been added from the Add dialog.

    This ensures new cards are immediately placed into the correct JLPT deck
    based on their tags, without manual deck selection (if enabled in config).
    """
    cfg = _get_config()
    if not cfg.get("auto_sort_on_add", True):
        return

    moved = _sort_note_cards_by_tags(note.id)
    if moved:
        # Keep collection UI up to date when cards move.
        mw.col.reset()
        mw.reset()


def _add_tools_menu_action() -> None:
    """Add 'JLPT: Auto-sort decks from tags' to the Tools menu."""
    action = QAction("JLPT: Auto-sort decks from tags", mw)
    qconnect(action.triggered, sort_entire_collection)
    mw.form.menuTools.addAction(action)


def _on_profile_did_open() -> None:
    """Initialize menu actions when profile opens."""
    _add_tools_menu_action()


def _register_config_action() -> None:
    """Use custom config dialog instead of raw JSON editor."""
    from .config_dialog import open_config_dialog

    mw.addonManager.setConfigAction(__name__, open_config_dialog)


# Register hooks when the add-on is loaded.
_register_config_action()
gui_hooks.add_cards_did_add_note.append(_on_note_added)
gui_hooks.profile_did_open.append(_on_profile_did_open)
# note_did_update was removed in newer Anki; editor_did_update_tags runs when
# tags are changed in the editor. Bulk tag changes in the browser can be
# handled by running the Tools menu action.
gui_hooks.editor_did_update_tags.append(lambda note: _sort_note_cards_by_tags(note.id))

