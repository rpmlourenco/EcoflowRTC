"""Add the local RTC backend as a single config entry."""

from homeassistant.config_entries import ConfigFlow


class NativePiRTCConfigFlow(ConfigFlow, domain="ecoflow_rtc"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("ecoflow_rtc")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="EcoFlow RTC", data={})
