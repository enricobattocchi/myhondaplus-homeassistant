# AGENTS.md

Fast orientation for AI agents working on this repo. Humans should start with [`CONTRIBUTING.md`](CONTRIBUTING.md), which documents the architecture, conventions, test layout, and release process in full. This file complements that with quick-navigation pointers for agents starting cold; defer to CONTRIBUTING.md when in doubt.

Sections 2, 3, and 5 mirror the canonical text in [`pymyhondaplus/AGENTS.md`](https://github.com/enricobattocchi/pymyhondaplus/blob/main/AGENTS.md) — update there first, then propagate.

## 1. What this repo is

The Home Assistant custom integration for My Honda+ / Honda Connect Europe vehicles, distributed via HACS. It consumes the [`pymyhondaplus`](https://github.com/enricobattocchi/pymyhondaplus) library for all upstream API work and surfaces vehicle data and remote controls as Home Assistant entities and services.

## 2. Naming

*Mirrored from `pymyhondaplus/AGENTS.md` — update there first.*

Refer to the upstream service as "the My Honda+ API" or "the Honda Connect Europe API" in code, comments, commit messages, PR descriptions, log strings, and test names — matching the framing used in the public READMEs. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full style guide.

## 3. The three-repo ecosystem

*Mirrored from `pymyhondaplus/AGENTS.md` — update there first.*

[`pymyhondaplus`](https://github.com/enricobattocchi/pymyhondaplus) (Python library + CLI) is consumed by:

- `myhondaplus-homeassistant` (this repo) — Home Assistant integration, pinned `==X.Y.Z` (HA convention).
- [`myhondaplus-desktop`](https://github.com/enricobattocchi/myhondaplus-desktop) — PyQt6 desktop app, pinned `>=X.Y.Z`.

**Ownership boundaries** — each concern lives in exactly one repo:

- **Library owns**: API request/response shapes, auth flow, `EVStatus` parsing, enum normalization (`charge_status`, `home_away`, `climate_temp`, geofence states), `VehicleCapabilities` resolution, capability raw-API-key labels, geofence state labels, geofence error messages, library-side translations (CLI strings + the `t_lib()` keys consumers bridge to).
- **HA integration owns**: entity descriptors, coordinators, config flow, services, `strings.json` + `translations/*.json`, error-handling conventions for HA.
- **Desktop owns**: view layer (MainWindow / widgets), controller, workers, dashboard / trip / geofence / vehicle UI, desktop `translations/*.json`, PyInstaller bundling.

If a task feels like it crosses boundaries, default to "the library owns the API/parsing/canonical enums; consumers are presentation" and confirm with the maintainer before editing across repos.

**Triage rule.** When investigating an issue or fix in a consumer repo (HA or desktop), use the ownership boundaries above. If the symptom is in library-owned territory (API request/response shape, parsing, enum normalization, capability resolution, library-owned translation strings), the issue or PR should be opened in `pymyhondaplus` — even if it was first surfaced through a consumer. When in doubt, a short Python repro against the library is the fastest way to confirm.

## 4. Where to touch code

| Task | Files |
|---|---|
| Add a new entity / sensor / button | platform module under `custom_components/myhondaplus/` (`binary_sensor.py` / `button.py` / `device_tracker.py` / `lock.py` / `number.py` / `select.py` / `sensor.py` / `switch.py`); shared helpers in `entity.py`; user-visible labels in `strings.json`; translations in `custom_components/myhondaplus/translations/<lang>.json` for all 13 locales; tests in `tests/` (95% coverage gate) |
| Add a new service | register in `custom_components/myhondaplus/__init__.py`; schema in `services.yaml`; descriptions under `services` in `strings.json`; translations; tests |
| Config-flow change | `custom_components/myhondaplus/config_flow.py`; labels under `config.step` in `strings.json`; translations |
| New translated string paired with a library string | `strings.json` + `translations/<lang>.json`; if it pairs with a `pymyhondaplus.translations.TRANSLATIONS` key, run `tests/test_translation_drift.py` and move the pair into `ENFORCED_OVERLAPS` (or out of `_KNOWN_DRIFT`) when wording converges |
| Bump library dep | `custom_components/myhondaplus/manifest.json` `requirements` — exact pin `pymyhondaplus==X.Y.Z`; manifest `version` for the integration release |
| New enum sensor value | `options` list on the platform descriptor; the library normalizes — don't re-normalize here |
| Coordinator change | `coordinator.py` (`HondaDataUpdateCoordinator`, `HondaTripCoordinator`); follow the error-handling conventions in [`CONTRIBUTING.md`](CONTRIBUTING.md) |

## 5. Cross-repo workflows

*Mirrored from `pymyhondaplus/AGENTS.md` — update there first.*

- **Release order is library first, then consumers.** Bump `pymyhondaplus`, tag, GitHub-release; then update HA `manifest.json` `requirements` (`==X.Y.Z`) and/or desktop `pyproject.toml` + `README.md` (`>=X.Y.Z`), then release each consumer.
- **Pin update rule**: HA pins exact (Home Assistant convention); desktop pins minimum.
- **Translation-drift PRs** may span library + HA. When a string converges in wording, move the pair from `_KNOWN_DRIFT` to `ENFORCED_OVERLAPS` in the same PR (HA test: `tests/test_translation_drift.py`).

## 6. Common pitfalls

- Hassfest rejects timeout/notification strings under the `notifications` key. They go under `exceptions` in `strings.json`.
- `VehicleCapabilities` access is raw-backed: `getattr(vehicle.capabilities, desc.capability, True)` is the correct gating pattern. Unknown names raise `AttributeError` and `getattr` falls through to the default — no integration code change is needed when the library adds capability flags.
- The library returns coordinates as floats — no conversion in the integration.
- `_log_unavailable_once` / `_log_recovered_once` exist for a reason; don't add ad-hoc logging that re-spams.
- Optimistic updates mutate `coordinator.data` before the API confirms; revert on failure.
- All 13 locale files must stay current — auditing them is a blocking pre-tag step.

## 7. Gates

`Lint` (ruff), `Test` (pytest with 95% coverage), `Hassfest`, `HACS Validation` — all four required before merge. Tag is the bare version (e.g. `5.2.0`, not `v5.2.0`); `manifest.json` integration `version` must match the tag.

## 8. Full reference

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full architecture, library-coupling details, translation-drift test conventions, error-handling rules, entity conventions, CI workflows, and release process. The same guidance that applies to human contributors applies to agents.
