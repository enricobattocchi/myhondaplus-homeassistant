# Contributing to My Honda+

Thank you for your interest in contributing to the My Honda+ Home Assistant integration!

## Translations

Translation files live in `custom_components/myhondaplus/translations/` and are named by ISO 639-1 language code (e.g. `en.json`, `fr.json`, `de.json`). The reference file is [`translations/en.json`](custom_components/myhondaplus/translations/en.json).

### Via GitHub Issue (easiest)

1. Open a new issue using the **[Translation](../../issues/new?template=translation.yml)** template.
2. Select your language from the dropdown.
3. Replace the pre-filled English values with your translations (keep all JSON keys unchanged).
4. Submit the issue — a maintainer will open the PR on your behalf.

### Via Pull Request

If you prefer to submit a PR directly:

1. Copy `custom_components/myhondaplus/translations/en.json` to `custom_components/myhondaplus/translations/<lang>.json` (e.g. `fr.json` for French).
2. Translate only the **values** — do not change any keys.
3. Keep `{service}`, `{entry_id}`, and similar placeholders as-is.
4. Validate that your file is valid JSON (e.g. paste it into a JSON linter).
5. Open a pull request with the title `Add <language> translation`.
