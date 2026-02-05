JLPT Tag Deck Auto-Sorter
==========================

This Anki add-on automatically moves cards into JLPT decks based on their tags.

### How it works

- If a note has one of the JLPT tags below (case-insensitive), its cards are moved to the corresponding deck:
  - `JLPT_N2` → `0_JLPT N2`
  - `JLPT_N1` → `1_JLPT N1`
  - `JLPT_N3` → `JLPT N3`
  - `JLPT_N4` → `JLPT N4`
  - `JLPT_N5` → `JLPT N5`
- Priority when multiple JLPT tags are present on the same note:
  - `JLPT_N2` (current focus)
  - `JLPT_N1`
  - `JLPT_N3`
  - `JLPT_N4`
  - `JLPT_N5`
- The following decks are **never** auto-moved by this add-on, even if the cards carry JLPT tags:
  - `Government Agencies`
  - `Food`
  - `Linguistics`
  - `People`

New cards are auto-sorted right after you add them, and you also get a **Tools → JLPT: Auto-sort decks from tags** menu action to sort your entire collection on demand.

### Installation

1. Quit Anki.
2. Copy the `jlpt_auto_sort` folder into your Anki add-ons directory:
   - On macOS: `~/Library/Application Support/Anki2/addons21/`
3. Start Anki again.
4. You should now see:
   - A Tools menu entry: **JLPT: Auto-sort decks from tags**
   - New JLPT cards being placed into the correct deck automatically based on their `JLPT_N*` tags.

