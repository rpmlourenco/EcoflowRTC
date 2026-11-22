<img src="custom_components/ecoflow_rtc/brand/icon.png" width="88" alt="EcoFlow RTC">

# EcoFlow RTC

A Home Assistant integration for the Raspberry Pi 5 native RTC. It gives the
EcoFlow safe shutdown blueprint the same periodic wake mechanism used by
Argon UPS. The blueprint verifies the UPS telemetry and decides when to act.
This integration only manages the local clock alarm.

## Install

Use Home Assistant 2026.3 or later on a Raspberry Pi 5 with a writable native RTC.

[![Open EcoFlow RTC in the Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=rpmlourenco&repository=EcoflowRTC&category=integration)

1. In **Settings → Marketplace**, select **Add from link** and enter
   `https://github.com/rpmlourenco/EcoflowRTC`.
2. Open **EcoFlow RTC** and select **Install**.
3. Add **EcoFlow RTC** from **Settings → Devices & services → Add integration**.

The Marketplace uses its public catalog for icons before installation.
A repository added from a link may show a placeholder in the Marketplace list.
The installed integration uses the icon shipped with the release.

## Import the shutdown blueprint

[![Import the EcoFlow RIVER 3 blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frpmlourenco%2FEcoflowRTC%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fecoflow_safe_shutdown.yaml)

Create one automation for the host and choose the **EcoFlow** that physically
powers it. The blueprint resolves the telemetry on that device. If replacing
an existing shutdown automation, disable the old one before arming the new one.

Before enabling periodic wake, verify the Pi bootloader has
`POWER_OFF_ON_HALT=1`, `WAKE_ON_GPIO=0`, and `WAIT_FOR_POWER_BUTTON` unset or
zero. Follow the [Argon native RTC guide](https://github.com/rpmlourenco/ArgonUPS/blob/main/docs/NATIVE-RTC-WAKE.md)
for the host preparation and supervised wake test.

- `ecoflow_rtc.schedule_wake` arms and reads back an alarm. It takes
  `retry_minutes` from 5 to 1440 and returns the scheduled time.
- `ecoflow_rtc.cancel_wake` clears only an alarm owned by this integration.
- An alarm owned by another application is left alone.

The driver is reused from [ArgonUPS](https://github.com/rpmlourenco/ArgonUPS)
under the MIT license. The icon is supplied locally in the `brand` directory.

## Tests

Run `python -m pytest tests` with pytest, PyYAML and Jinja2 installed. The clock is simulated.
