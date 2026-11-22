"""Expose the Argon native RTC backend independently of UPS telemetry."""

import asyncio
import logging
from datetime import UTC, datetime

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .rtc import NativeRTC, RTCError

DOMAIN = "ecoflow_rtc"
_LOGGER = logging.getLogger(__name__)
_SCHEDULE_SCHEMA = vol.Schema(
    {vol.Required("retry_minutes"): vol.All(cv.positive_int, vol.Range(min=5, max=1440))}
)


async def async_setup_entry(hass, entry):
    rtc = NativeRTC()
    store = Store(hass, 1, f"{DOMAIN}.native_wake")
    try:
        saved = await store.async_load()
    except (HomeAssistantError, OSError, ValueError) as err:
        _LOGGER.warning("Cannot restore native wake alarm ownership: %s", err)
        saved = None
    owned_alarm = saved.get("alarm") if isinstance(saved, dict) else None
    if type(owned_alarm) is not int:
        owned_alarm = None
    lock = asyncio.Lock()

    async def schedule(call):
        nonlocal owned_alarm
        async with lock:
            try:
                deadline = await hass.async_add_executor_job(
                    rtc.schedule, call.data["retry_minutes"], owned_alarm
                )
                owned_alarm = deadline
                await store.async_save({"alarm": deadline})
            except (RTCError, OSError) as err:
                raise HomeAssistantError(str(err)) from err
            wake_time = datetime.fromtimestamp(deadline, UTC).isoformat()
            _LOGGER.info("EcoFlow RTC wake scheduled for %s", wake_time)
            return {"wake_timestamp": deadline, "wake_time": wake_time}

    async def cancel(_call):
        nonlocal owned_alarm
        async with lock:
            try:
                cancelled = await hass.async_add_executor_job(rtc.cancel, owned_alarm)
                owned_alarm = None
                await store.async_save({"alarm": None})
            except (RTCError, OSError) as err:
                raise HomeAssistantError(str(err)) from err
            return {"cancelled": cancelled}

    hass.services.async_register(
        DOMAIN, "schedule_wake", schedule, schema=_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, "cancel_wake", cancel, schema=vol.Schema({}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.BINARY_SENSOR])
    return True


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, [Platform.BINARY_SENSOR]):
        return False
    hass.services.async_remove(DOMAIN, "schedule_wake")
    hass.services.async_remove(DOMAIN, "cancel_wake")
    return True
