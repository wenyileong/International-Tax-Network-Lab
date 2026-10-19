# Adding a language

Interface text is never written into the code. It is loaded at run time from `src/taxnetlab/web/locales/<tag>.json`, where `<tag>` is a BCP 47 language tag such as `zh-CN`, `ms-MY` or `fr-FR`.

## Steps

1. Copy `en-GB.json` to `<tag>.json`.
2. Edit the `_meta` block:

   ```json
   "_meta": {"name": "Chinese (Simplified)", "native_name": "中文（简体）", "dir": "ltr",
             "fallback": "en-GB", "complete": false}
   ```

   * `dir` is `ltr` or `rtl` (the whole interface mirrors for right-to-left scripts);
   * `fallback` names the locale used for any key you have not translated yet;
   * set `complete` to `true` once every string is translated (the About page lists incomplete languages).
3. Translate the values in `strings`. Keep every `{placeholder}` exactly as written; they are filled in at run time (for example `{n}`, `{table}`, `{column}`).
4. Restart the application. The language menu in the top bar picks up the new file. The choice is remembered on the computer.

Keys may be deleted from a partial translation: they fall back along the `fallback` chain to English.

## What is translated

* every label, heading, button, message and chart title in the interface;
* validation messages: the server sends a stable code and parameters (for example `issue.missing_column` with `{column}`), and the interface looks up the text, so data-quality reports appear in the chosen language;
* numbers and percentages are formatted for the chosen locale.

Data values (names, identifiers, sources) and engine documentation strings (purpose, boundary) are not translated.

## Checks

`tests/test_server_and_i18n.py` fails if the interface uses a key that `en-GB.json` lacks, if a validation code has no message, or if placeholders are unbalanced. Run `python -m pytest tests/test_server_and_i18n.py` after editing.
