# My Honda+ for Home Assistant

Home Assistant custom component for Honda Connect Europe vehicles (My Honda+ app).

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested — contributions welcome!

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=enricobattocchi&repository=myhondaplus-homeassistant&category=integration)

1. Click the button above, or search for "My Honda+" in HACS under Integrations
2. Install "My Honda+"
3. Restart Home Assistant
4. Add the integration via Settings > Integrations > Add Integration > "My Honda+"

HACS will track updates automatically, making it easy to upgrade.

### Manual installation

<details>
<summary>More details</summary>

1. Download the `myhondaplus.zip` from the [latest release](https://github.com/enricobattocchi/myhondaplus-homeassistant/releases/latest)
2. Extract the `custom_components/myhondaplus` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant
4. Add the integration via Settings > Integrations > Add Integration > "My Honda+"

</details>

## Configuration

The integration will ask for:
- **Email**: Your My Honda+ account email
- **Password**: Your My Honda+ account password
- **Update interval**: How often to poll Honda's cached data (default: 600 seconds / 10 minutes)
- **Refresh from car interval**: How often to wake the TCU for fresh data (default: 43200 seconds / 12 hours, 0 to disable)

These intervals can be changed later from **Settings > Integrations > My Honda+ > Configure**.

Vehicles on your account are auto-detected. If you have multiple vehicles, you'll be asked to pick one. The vehicle's Honda+ nickname is used as the device name in Home Assistant.

On first setup, Honda will send a verification email. Copy the link URL (don't click it) and paste it in the verification step.

## Entities

Units are dynamic — the integration uses whatever the vehicle reports (km/miles, °C/°F).

Remote commands update the UI optimistically (the state changes immediately) and revert if the command fails. The lock entity shows "Locking..."/"Unlocking..." transition states.

### Sensors
- **Battery & charging**: Battery level, Range, Total range, Charge status, Plug status, Charge mode, Time to full charge
- **Climate**: Climate active, Climate temperature, Climate duration, Climate defrost, Cabin temperature, Interior temperature
- **Vehicle**: Odometer, Speed, Ignition, Doors locked, Headlights, Parking lights
- **Other**: Warning lamps, Last updated
- **Trips**: Trips this month, Distance this month, Driving time this month, Avg consumption this month
- **Schedules**: Charge schedule (active rules count + full rules in attributes), Climate schedule (active rules count + full rules in attributes)

### Binary Sensors
- **Doors** — open/closed
- **Windows** — open/closed
- **Hood** — open/closed
- **Trunk** — open/closed
- **Lights** — on/off

### Device Tracker
- **Location** — vehicle GPS position, shown on the HA map

### Lock
- **Doors** — lock/unlock with state from vehicle

### Switches
- **Climate** — start/stop pre-conditioning
- **Charging** — start/stop charging (reflects both manually and externally started charging)
- **Climate defrost** — enable/disable defrost setting on the vehicle
- **Auto refresh from car** — enable/disable the recurring refresh from car

### Selects
- **Climate temperature** — cooler / normal / hotter
- **Climate duration** — 10 / 20 / 30 minutes

### Buttons
- **Horn & lights** — flash lights and honk horn
- **Refresh** — re-fetch cached data from Honda's servers (instant, no car wake-up)
- **Refresh from car** — request fresh data from the vehicle (wakes the TCU)

### Numbers
- **Charge limit (home)** — 80-100% in steps of 5
- **Charge limit (away)** — 80-100% in steps of 5

## Services

### `myhondaplus.climate_on`

Start climate pre-conditioning with specific settings. Applies the settings and starts climate.

```yaml
service: myhondaplus.climate_on
data:
  temp: "normal"      # cooler, normal, hotter
  duration: 30         # 10, 20, 30
  defrost: true
```

### `myhondaplus.set_charge_schedule`

Set the charge prohibition schedule (up to 2 rules). All fields are required. Pass `rules: []` to clear.

```yaml
service: myhondaplus.set_charge_schedule
data:
  rules:
    - days: "mon,tue,wed,thu,fri"
      location: "home"       # home, all
      start_time: "22:00"
      end_time: "06:00"
```

### `myhondaplus.set_climate_schedule`

Set the climate pre-conditioning schedule (up to 7 rules). `days` and `start_time` are required. Pass `rules: []` to clear.

```yaml
service: myhondaplus.set_climate_schedule
data:
  rules:
    - days: "mon,tue,wed,thu,fri"
      start_time: "07:00"
```

## Related projects

- [pymyhondaplus](https://github.com/enricobattocchi/pymyhondaplus) — Python client library and CLI for the Honda Connect Europe API
- [myhondaplus-desktop](https://github.com/enricobattocchi/myhondaplus-desktop) — Desktop GUI application

## Disclaimer

This project is **unofficial** and **not affiliated with, endorsed by, or connected to Honda Motor Co., Ltd.** in any way.

- Use at your own risk. The authors accept no responsibility for any damage to your vehicle, account, or warranty.
- Honda may change their API at any time, which could break this integration without notice.
- Sending remote commands (lock, unlock, climate, charging) to your vehicle is your responsibility.
- This integration does not store or transmit your credentials to any third party. Authentication is performed directly with Honda's servers.
