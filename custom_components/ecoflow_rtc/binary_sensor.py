"""Report whether the native RTC actions are registered."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NativePiRTCServiceReady()])


class NativePiRTCServiceReady(BinarySensorEntity):
    _attr_name = "EcoFlow RTC services ready"
    _attr_unique_id = "ecoflow_rtc_services_ready"
    _attr_should_poll = False
    _attr_entity_registry_visible_default = False

    @property
    def is_on(self):
        return all(
            self.hass.services.has_service(DOMAIN, action)
            for action in ("schedule_wake", "cancel_wake")
        )
