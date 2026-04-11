# Contributing to My Honda+

Thank you for your interest in contributing to the My Honda+ Home Assistant integration!

## Translations

Translation files live in `custom_components/myhondaplus/translations/` and are named by ISO 639-1 language code (e.g. `en.json`, `fr.json`, `de.json`). The reference file is [`translations/en.json`](custom_components/myhondaplus/translations/en.json).

### Via GitHub Issue (easiest)

1. Open a new issue using the **[Translation](../../issues/new?template=translation.yml)** template.
2. Select your language and contribution type (**New translation** or **Fix / improve existing translation**).
3. **New translation** — copy [`en.json`](custom_components/myhondaplus/translations/en.json), translate the values, and paste the full JSON.
4. **Correction** — list only the keys that need fixing and their corrected values in the Corrections field (no need to paste the entire file).
5. Submit the issue — a maintainer will open the PR on your behalf.

### Via Pull Request

If you prefer to submit a PR directly:

1. **New language** — copy `custom_components/myhondaplus/translations/en.json` to `custom_components/myhondaplus/translations/<lang>.json` (e.g. `fr.json` for French) and translate the values.
2. **Correction** — edit the existing `<lang>.json` file directly.
3. Translate only the **values** — do not change any keys.
4. Keep `{service}`, `{entry_id}`, and similar placeholders as-is.
5. Validate that your file is valid JSON (e.g. paste it into a JSON linter).
6. Open a pull request.
