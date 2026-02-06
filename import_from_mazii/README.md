# Import from Mazii

An Anki add-on that creates cards from vocabulary exported from [Mazii](https://mazii.net) notebooks. You can use Mazii’s definitions only, or pair this with the **Bunpro Vocab Fetch** add-on to fill POS, English, and example sentences from Bunpro.

## How to use

1. **Export from Mazii**  
   In Mazii, open your notebook (e.g. [N2 Studying](https://mazii.net/en-US/note)), then use **Download vocabulary list (Excel)** (or export as CSV if available). Save the file.

2. **Import in Anki**  
   In Anki: **Tools → Import from Mazii**. In the dialog:
   - **Browse** to the CSV or Excel file you exported from Mazii.
   - Choose **Deck** and **Note type** (e.g. *Vocab Front and Back*).
   - Optionally enable **Use Bunpro for POS, English, and example sentences** (requires the [Bunpro Vocab Fetch](https://github.com/...) add-on).
   - Click **Import**.

3. **Result**  
   The add-on creates one note per word in the file. Words that already exist in your collection (same note type and same kanji in the kanji field) are skipped. If “Use Bunpro” is on and Bunpro has the word, fields (kana, pos, english, example sentences, JLPT tag) are filled from Bunpro; otherwise only data from the Mazii file is used (kanji, and kana/meaning if your export has those columns).

## File format

Supported: **CSV** and **Excel (.xlsx)**. The first row is treated as a header. The add-on looks for columns named like:

- **Word/Kanji**: `word`, `kanji`, `vocabulary`, `term`, `expression`, etc.
- **Kana**: `kana`, `reading`, `furigana`, etc.
- **Meaning**: `meaning`, `definition`, `english`, `translation`, etc.

If no header is recognized, the first column is used as the word (kanji), second as kana, third as meaning.

## Bunpro integration

- If the **Bunpro Vocab Fetch** add-on is installed, a checkbox **Use Bunpro for POS, English, and example sentences** is available.
- When checked, each imported word is looked up on Bunpro; when found, the note is filled with kana, pos, english, two example sentences (with furigana), and JLPT tag, same as when you use the Bunpro button in the Add window.
- When unchecked (or when Bunpro is not installed), only the Mazii export data is used, so the add-on stays useful without Bunpro.

## Install

Copy the `import_from_mazii` folder into your Anki add-ons directory, or run this repo’s `./sync-anki-addons.sh` and restart Anki.

## Requirements

- Anki 2.1.49+
- For **Excel (.xlsx)** import: the `openpyxl` package (e.g. `pip install openpyxl` in the same Python environment Anki uses). CSV works with the standard library only.
