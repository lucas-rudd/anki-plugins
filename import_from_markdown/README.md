# Import from Markdown Vocabulary

An Anki add-on that scans your Japanese class-note markdown files for a
`## Vocabulary` section with the table:

`| Word | Kanji | Meaning | Type |`

and creates cards from each row.

It can optionally use the **Bunpro Vocab Fetch** add-on to fill POS, English,
example sentences, and JLPT tags for each word.

## Usage

1. Make sure your notes follow the pattern:

```markdown
## Vocabulary

| Word | Kanji | Meaning | Type |
| --- | --- | --- | --- |
| しょうがいしゃ | 障害者 | Disabled person |  |
|  | 教科 | subject |  |
| のうさんぶつ | 農産物 | Farm products |  |
...
```

2. In Anki, choose **Tools → Import from Markdown Vocabulary**.

3. In the dialog:
   - Select the **folder** that contains your `.md` files (all subfolders are scanned).
   - Choose the **Deck** and **Note type** (e.g. `Vocab Front and Back`).
   - Optionally check **Use Bunpro for POS, English, and example sentences**.

4. Click **Import**.

The add-on:

- Reads every `## Vocabulary` section in all `.md` files.
- Extracts `Word` (kana/reading), `Kanji`, `Meaning`, and `Type`.
- For each row, picks `Kanji` if present, otherwise `Word`, as the primary key.
- Skips notes that already exist in the chosen note type (same primary key in the `kanji` field).
- When **Use Bunpro** is enabled and a Bunpro vocab entry is found, fills:
  - `kanji`, `kanji_furigana`, `kana`, `pos`, `english`,
  - example fields (`ex1_ja`, `ex1_ja_furigana`, `ex1_en`, `ex2_ja`, `ex2_ja_furigana`, `ex2_en`),
  - and adds `JLPT_N*` tags.
- Otherwise, it fills from the markdown data only:
  - `kanji` / `kanji_furigana`, `kana`, `pos` (from `Type`), and `english` (from `Meaning`).

## Requirements

- Anki 2.1.49+.
- Works best with the `Vocab Front and Back` note type and the `bunpro_vocab_fetch` add-on installed (for Bunpro integration).

