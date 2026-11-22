<img src="custom_components/ecoflow_rtc/brand/icon.png" width="88" alt="EcoFlow RTC">

# EcoFlow RTC

A Home Assistant integration for the Raspberry Pi 5 native RTC. It gives the
EcoFlow safe shutdown blueprint the same periodic wake mechanism used by
Argon UPS. The blueprint verifies the UPS telemetry and decides when to act.
This integration only manages the local clock alarm.

## Install

Use Home Assistant 2026.3 or later on a Raspberry Pi 5 with a writable native RTC.

1. In HACS, open **Custom repositories** and add
   `https://github.com/rpmlourenco/EcoflowRTC` as an **Integration**.
2. Download **EcoFlow RTC** in HACS and restart Home Assistant.
3. Add **EcoFlow RTC** from **Settings → Devices & services → Add integration**.

Prepare and verify the bootloader before enabling periodic wake. Follow the
[EcoFlow shutdown and wake guide](https://github.com/rpmlourenco/HomeAssistant/blob/main/docs/ECOFLOW-SAFE-SHUTDOWN.md).

- `ecoflow_rtc.schedule_wake` arms and reads back an alarm. It takes
  `retry_minutes` from 5 to 1440 and returns the scheduled time.
- `ecoflow_rtc.cancel_wake` clears only an alarm owned by this integration.
- An alarm owned by another application is left alone.

The driver is reused from [ArgonUPS](https://github.com/rpmlourenco/ArgonUPS)
under the MIT license. The icon is supplied locally in the `brand` directory.

## Tests

Run `python -m pytest tests` with pytest installed. The clock is simulated.
