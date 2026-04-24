"""Detect drift between HA integration translations and pymyhondaplus.

The HA integration's user-visible strings overlap with pymyhondaplus's
translations (charge_status state values, sensor names, etc.). Because the
two use architecturally different i18n mechanisms — HA core reads static
JSON at entity-registry time; pymyhondaplus CLI/desktop use its Python
TRANSLATIONS dict — they can't share a store at runtime. They stay in sync
only by manual discipline.

This test watches for silent divergence. When either side updates a shared
string and forgets the other, the test fails, pointing to the exact locale
and key.

If the test fails, the fix is *not* to blindly align the two; decide which
side is the correct wording and update the other to match.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pymyhondaplus.translations import TRANSLATIONS as LIB_TRANSLATIONS

INTEGRATION_ROOT = pathlib.Path(__file__).parent.parent / "custom_components" / "myhondaplus"
HA_TRANSLATIONS_DIR = INTEGRATION_ROOT / "translations"
HA_STRINGS_JSON = INTEGRATION_ROOT / "strings.json"

# Overlap pairs currently in sync across ALL shipped locales. New drift in
# any of these → test fails, pointing to the exact locale and key.
#
# When a currently-drifted pair in _KNOWN_DRIFT gets reconciled, move it up
# here. When a new overlap surfaces (e.g. a new sensor added to the HA
# integration that already has a library translation), add it here.
ENFORCED_OVERLAPS = {
    # HA dotted key path: library flat key
    "entity.sensor.charge_status.state.charging": "charging",
    "entity.sensor.charge_status.state.notcharging": "not_charging",
    "entity.sensor.charge_status.state.unknown": "unknown",
    "entity.sensor.plug_status.state.plugged_in": "plugged_in",
    "entity.sensor.plug_status.state.unplugged": "unplugged",
    "entity.sensor.plug_status.state.unknown": "unknown",
    "entity.sensor.home_away.state.home": "home",
    "entity.sensor.home_away.state.unknown": "unknown",
    "entity.sensor.speed.name": "speed_label",
    "entity.sensor.charge_mode.state.unconfirmed": "unconfirmed",
    "entity.device_tracker.vehicle_location.name": "location_label",
    "entity.binary_sensor.doors_open.name": "doors_label",
}

# Overlap pairs with pre-existing wording drift between HA integration and
# pymyhondaplus. These are documented here so new drift is still caught and
# existing drift becomes a reconciliation backlog. Remove from this list
# when the drift is resolved (and verify no regressions in the enforced
# assertion above).
_KNOWN_DRIFT = {
    # HA: "Ladestatus" / "Laddstatus"; lib: "Opladningsstatus" / "Laddningsstatus"
    "entity.sensor.charge_status.name": "charge_status_label",
    # HA: "plug" wording; lib: "cable" wording (different noun in 12 locales)
    "entity.sensor.plug_status.name": "plug_status_label",
    # HA/lib word-order and abbreviation differences in cs/no/pl/sk
    "entity.sensor.odometer.name": "odometer_label",
    # HA "Allumage" vs lib "Contact" in French
    "entity.sensor.ignition.name": "ignition_label",
    # HA uses "Email" verbatim in all non-en locales; lib uses native form
    "config.step.user.data.email": "profile_email",
    "config.step.reauth_confirm.data.email": "profile_email",
}


def _lookup(haystack: dict, dotted_key: str) -> str | None:
    node = haystack
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def _ha_translation(locale: str, dotted_key: str) -> str | None:
    if locale == "en":
        data = json.loads(HA_STRINGS_JSON.read_text(encoding="utf-8"))
    else:
        path = HA_TRANSLATIONS_DIR / f"{locale}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    return _lookup(data, dotted_key)


def _lib_translation(locale: str, key: str) -> str | None:
    return LIB_TRANSLATIONS.get(locale, {}).get(key)


_HA_LOCALES = ["en"] + sorted(
    p.stem for p in HA_TRANSLATIONS_DIR.glob("*.json") if p.stem != "en"
)


@pytest.mark.parametrize("locale", _HA_LOCALES)
@pytest.mark.parametrize("ha_key, lib_key", list(ENFORCED_OVERLAPS.items()))
def test_enforced_overlaps_match(locale: str, ha_key: str, lib_key: str):
    ha_value = _ha_translation(locale, ha_key)
    lib_value = _lib_translation(locale, lib_key)
    if ha_value is None or lib_value is None:
        pytest.skip(f"{locale}: HA={ha_value!r} / lib={lib_value!r} — nothing to compare")
    assert ha_value == lib_value, (
        f"Translation drift in locale {locale!r}:\n"
        f"  HA   [{ha_key}] = {ha_value!r}\n"
        f"  lib  [{lib_key}] = {lib_value!r}\n"
        f"Reconcile both to the correct wording before merging."
    )


def test_known_drift_pairs_are_still_drifted():
    """If a _KNOWN_DRIFT pair now matches, move it to ENFORCED_OVERLAPS.

    This is the reverse-direction guard: when someone reconciles a drift
    pair but forgets to promote it to enforced, this test fails and reminds
    them. Keeps _KNOWN_DRIFT honest over time.
    """
    still_drifted = []
    now_matching = []
    for ha_key, lib_key in _KNOWN_DRIFT.items():
        any_drift = False
        for locale in _HA_LOCALES:
            hv = _ha_translation(locale, ha_key)
            lv = _lib_translation(locale, lib_key)
            if hv is None or lv is None:
                continue
            if hv != lv:
                any_drift = True
                break
        (still_drifted if any_drift else now_matching).append(ha_key)

    assert not now_matching, (
        f"These _KNOWN_DRIFT pairs now match across all comparable locales:\n"
        f"  {now_matching}\n"
        f"Move them to ENFORCED_OVERLAPS so future drift is caught."
    )
