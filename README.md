# My Honda+ for Home Assistant

Home Assistant custom component for Honda Connect Europe vehicles (My Honda+ app).

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested — contributions welcome!

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "My Honda+"
3. Restart Home Assistant
4. Add the integration via Settings > Integrations > Add Integration > "My Honda+"

### Manual

Copy `custom_components/myhondaplus` to your Home Assistant `custom_components` directory.

## Configuration

The integration will ask for:
- **Email**: Your My Honda+ account email
- **Password**: Your My Honda+ account password
- **VIN**: Your vehicle identification number

On first setup, Honda will send a verification email. Copy the link URL (don't click it) and paste it in the verification step.

## Entities

### Sensors
- Battery level, Range, Charge status, Plug status
- Climate active, Cabin temperature
- Odometer, Doors locked, Windows closed
- Last updated

### Buttons
- Lock doors, Unlock doors, Horn & lights
- Climate start/stop, Refresh from car

### Numbers
- Charge limit (home), Charge limit (away)
