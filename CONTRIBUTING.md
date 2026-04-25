# Contributing to My Honda+

Thank you for your interest in contributing to the My Honda+ Home Assistant integration!

## Reporting issues

If something isn't working, please [open an issue](https://github.com/enricobattocchi/myhondaplus-homeassistant/issues) with:

- Your Home Assistant version
- Your vehicle model (e.g. Honda e, ZR-V, e:Ny1)
- A description of the problem (with personal data redacted)
- Relevant log output if any

## Development setup

```bash
git clone https://github.com/enricobattocchi/myhondaplus-homeassistant.git
cd myhondaplus-homeassistant
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests and linting

```bash
python -m pytest tests/ -x -q
ruff check custom_components/ tests/
```

A 95% coverage gate is enforced in CI.

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Every code change must extend test coverage to exercise the new or modified behavior. Tests go in the same commit/PR as the code — assume existing tests cover only what they explicitly assert. If something genuinely can't be tested, explain why in the PR description.
3. Run `pytest` and `ruff check` locally.
4. Open a pull request with a clear description of what you changed and why.

## Architecture

This is a Home Assistant custom integration for Honda vehicles, distributed via HACS.

- **Library**: [`pymyhondaplus`](https://github.com/enricobattocchi/pymyhondaplus) (separate repo) handles all Honda API communication. This integration does not talk to the Honda API directly.
- **Token persistence**: `_ConfigEntryTokenStorage` in `__init__.py` bridges the library's storage interface to Home Assistant's config entry system. Tokens merge with current `entry.data` on the event loop to avoid stale snapshots.
- **Coordinators**: `HondaDataUpdateCoordinator` (dashboard / vehicle status, 10 min default) and `HondaTripCoordinator` (trip stats, 1 hour default) in `coordinator.py`.
- **Entity base**: All entities extend `MyHondaPlusEntity` in `entity.py` — provides `device_info`, `unique_id`, scheduled refresh helpers.
- **Platforms**: `binary_sensor`, `button`, `device_tracker`, `lock`, `number`, `select`, `sensor`, `switch`.
- **Services**: `set_charge_schedule`, `set_climate_schedule`, `climate_on` registered in `__init__.py`.
- **Translations**: `strings.json` is the source of truth. 13 language files in `translations/`. Timeout notification strings live under the `exceptions` key (not `notifications` — hassfest rejects that).
- **Config flow**: email/password login with device verification link, reauth on 401, options flow for intervals.

### Library coupling

- The library normalizes EV status enums (`charge_status`, `home_away`, `climate_temp`) to canonical values. The integration's ENUM sensors declare options that align with those canonical sets — do not list raw values like `"running"` or `"unavailable"`.
- The library returns coordinates as floats. No conversion needed in the integration.
- `VehicleCapabilities` is raw-backed in `pymyhondaplus`. The integration's gating pattern `getattr(vehicle.capabilities, desc.capability, True)` works transparently — known attribute names resolve through `__getattr__` to a bool, unknown names raise `AttributeError` and `getattr` falls through to the default. No code change is needed when capability fields are added on the library side.

### Translation drift

`tests/test_translation_drift.py` compares HA-side strings (entity names, state values, config flow labels) against `pymyhondaplus.translations.TRANSLATIONS` for every shared key in every locale. Two buckets:

- `ENFORCED_OVERLAPS` — pairs that currently match in all locales. New drift fails CI.
- `_KNOWN_DRIFT` — pairs with pre-existing wording divergence. A counter-assertion fails if any of these now match — that's the cue to promote them to `ENFORCED_OVERLAPS`.

When updating a translation on either side, run the drift test. If a key crosses from drifted to matching, move it from `_KNOWN_DRIFT` to `ENFORCED_OVERLAPS` in the same PR.

### Error handling conventions

- `401` / `HondaAuthError` → `ConfigEntryAuthFailed` (triggers reauth flow).
- `5xx` with cached data → return cached, log once.
- `5xx` without cached data → `UpdateFailed`.
- Service errors → `HomeAssistantError` with `translation_key`.
- `_log_unavailable_once` / `_log_recovered_once` pattern prevents log spam.

### Entity conventions

- `to_bool()` in `entity.py` handles API values that arrive as strings (`"true"`/`"false"`), ints, or actual bools.
- Enum sensors must list all possible values in `options`. The library normalizes values; this integration does not re-normalize.
- Dynamic units (km/miles, km/h/mph, C/F) come from `data.distance_unit` via `UNIT_MAP` in `sensor.py`.
- Optimistic updates: entity commands mutate `coordinator.data` before API confirmation, revert on failure.
- Capability gating: sensors check `_sensor_enabled()` against `VehicleCapabilities` before being created.

## Translations

Translation files live in `custom_components/myhondaplus/translations/` and are named by ISO 639-1 language code (e.g. `en.json`, `fr.json`, `de.json`). The reference file is [`translations/en.json`](custom_components/myhondaplus/translations/en.json).

### Via GitHub Issue (easiest)

1. Open a new issue using the **[Translation](../../issues/new?template=translation.yml)** template.
2. Select your language and contribution type (**New translation** or **Fix / improve existing translation**).
3. **New translation** — copy [`en.json`](custom_components/myhondaplus/translations/en.json), translate the values, and paste the full JSON.
4. **Correction** — list only the keys that need fixing and their corrected values in the Corrections field.
5. Submit the issue — a maintainer will open the PR on your behalf.

### Via Pull Request

1. **New language** — copy `custom_components/myhondaplus/translations/en.json` to `custom_components/myhondaplus/translations/<lang>.json` and translate the values.
2. **Correction** — edit the existing `<lang>.json` file directly.
3. Translate only the **values** — do not change any keys.
4. Keep `{service}`, `{entry_id}`, and similar placeholders as-is.
5. Validate that your file is valid JSON.
6. Open a pull request.

## Code style

- Tags use bare version numbers (`5.2.0`), not `v5.2.0`. The version in `manifest.json` must match the tag.
- The `pymyhondaplus` pin in `manifest.json` always uses `==X.Y.Z` (Home Assistant convention).

## CI

Three GitHub Actions workflows; all run on push to `main` and on PRs:

- `lint.yml` — Ruff
- `test.yml` — Pytest with 95% coverage gate
- `validate.yml` — Hassfest + HACS validation

Branch protection requires all four checks (Lint / Tests / Hassfest / HACS Validation) to pass before merge.

## Release process

1. Bump `version` in `manifest.json`.
2. Bump the `pymyhondaplus` requirement in `manifest.json` if a new library version is needed.
3. Verify all CI checks pass.
4. PR → merge to `main` (merge commit).
5. Tag `X.Y.Z` on the merge commit. Push.
6. `gh release create X.Y.Z` — HACS picks up the new release automatically.
