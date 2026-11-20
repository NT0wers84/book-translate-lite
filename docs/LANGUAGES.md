# Adding or improving a language

1. **Typography:** add an entry to `skills/book-translate-lite/templates/languages.json`:

   ```json
   "sv": {"name": "Swedish", "quotes": "””", "typographic_apostrophe": true, "punct_outside_quotes": false,
          "replacements": [], "toc_title": "Innehåll"}
   ```

   | key | meaning |
   |---|---|
   | `name` | English name of the language, used in the prompts ("translate into Swedish") |
   | `quotes` | the dialogue quote pair. It is used by the review analysis for straight or unbalanced quotes |
   | `typographic_apostrophe` | turn `'` into `’` after a letter |
   | `punct_outside_quotes` | only for `«»` styles that put the full stop and comma after the closing quote (Italian) |
   | `replacements` | regex fixes applied on every save, for example `...` → `…` |
   | `toc_title` | title of the table of contents in the EPUB (change it with `btl config toc_title=…` if the book has its own contents page with the same name) |

2. **Rules (optional):** add `skills/book-translate-lite/templates/rules/<code>.md`.
   - Copy `generic.md`, keep the *Fidelity and format* section unchanged, and write the publishing conventions: dialogue punctuation, narrative tense, number format, forms of address.
   - Write it in English, because it is an instruction to the model.

3. **Untranslated-text detection (optional):** if the language is often a **source** language, add its frequent function words to `FUNCTION_WORDS` in `skills/book-translate-lite/scripts/review.py`.

4. Run `python3 tests/test_all.py` and open a pull request.

`init.py` copies the rules into each project's `rules.md`, so each book can still change them.
