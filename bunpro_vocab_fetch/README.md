# Bunpro Vocab Fetch

An Anki add-on that fills "Vocab Front and Back" note fields from [Bunpro](https://bunpro.jp/vocabs) when you add a new card.

## How it works

1. In the **Add** window, choose the note type **Vocab Front and Back** and type the **kanji** in the kanji field.
2. Click the **Bunpro** button in the editor toolbar.
3. The add-on fetches the word from `https://bunpro.jp/vocabs/<word>` and fills:
   - **kana**
   - **pos** (part of speech, e.g. `n`, `vs`, `adj-na`)
   - **english**
   - **ex1_ja**, **ex1_ja_furigana**, **ex1_en** (first example sentence)
   - **ex2_ja**, **ex2_ja_furigana**, **ex2_en** (second example sentence)
   - **Tags**: adds **JLPT_N1** / **JLPT_N2** / … when Bunpro has a JLPT level.

You can edit any suggested content before adding the card.

## Requirements

- Note type **Vocab Front and Back** with at least a **kanji** field. Other fields are filled only if they exist.
- Internet connection (Bunpro is fetched when you click the button).
- For MVP, the word must have a Bunpro page at `https://bunpro.jp/vocabs/<url-encoded-kanji>`.

## Install

- Copy the `bunpro_vocab_fetch` folder into your Anki add-ons directory, or use this repo’s `./sync-anki-addons.sh` and restart Anki.

## Privacy / terms

- The add-on only reads the kanji you enter and requests the public Bunpro vocab page. It does not send any other data. Use of Bunpro is subject to [Bunpro’s terms](https://bunpro.jp/terms).
