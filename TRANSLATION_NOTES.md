# Translation Notes

## Source of translations

### From official My Honda+ app
- Charging states: charging, not charging, unplugged
- Lock states: locked, unlocked
- Binary sensor labels: doors, windows, lights
- Charge speed: fast charging
- Climate temperature: "Warmer" (not "Hotter")
- Labels: battery, climate, total distance

### Generated (no official source)

Everything else was generated and may need native speaker review.

## Confidence by language

### High confidence
- **de** (German) — common HA language, well-established automotive vocabulary
- **fr** (French) — common HA language, well-established automotive vocabulary
- **es** (Spanish) — common HA language, well-established automotive vocabulary
- **nl** (Dutch) — common HA language, well-established automotive vocabulary

### Medium confidence
- **sv** (Swedish) — less certain about config flow descriptions and compound words
- **da** (Danish) — similar to Swedish; some strings may mix Norwegian phrasing
- **pl** (Polish) — declension and case may be wrong in longer sentences
- **no** (Norwegian) — official app has almost no Norwegian strings; Bokmal assumed

### Lower confidence — native review recommended
- **cs** (Czech) — declension-heavy language; longer sentences may have case errors
- **sk** (Slovak) — same concerns as Czech
- **hu** (Hungarian) — agglutinative grammar; longer descriptive strings are the most likely to be awkward
- **it** (Italian) — *mostly sourced from official app and desktop app*; high confidence

## Strings most likely to need correction

The following string categories are the most complex and most likely to contain errors in the lower-confidence languages:

### Config flow `data_description` (long help text)
- `config.step.user.data_description.scan_interval`
- `config.step.user.data_description.car_refresh_interval`
- `config.step.user.data_description.location_refresh_interval`
- `config.step.select_vehicle.data_description.vin`
- `config.step.manual_vin.data_description.vin`
- `config.step.verify.data_description.verification_link`
- `config.step.verify.description` (contains "do NOT click" instruction)

### Config flow error messages
- `config.error.account_locked`
- `config.error.invalid_link`

### Exception messages with placeholders
- `exceptions.config_entry_not_found.message`
- `exceptions.config_entry_not_loaded.message`
- `exceptions.config_entry_no_data.message`

### Entity names that are domain-specific
- `entity.sensor.warnings` — "Warning lamps" may not translate well literally
- `entity.switch.auto_refresh` — "Auto refresh from car" is integration-specific
- `entity.sensor.charge_schedule` / `entity.sensor.climate_schedule`
- `entity.sensor.trips_this_month` / `distance_this_month` / `driving_time_this_month` / `avg_consumption_this_month`
