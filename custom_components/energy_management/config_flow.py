from __future__ import annotations

import voluptuous as vol

from typing import Any
from logging import getLogger

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = getLogger(__name__)

SUGGESTED_VALUE = "suggested_value"

DATA_SCHEMA = vol.Schema({
    vol.Required("area", default = "CEZ", description = {SUGGESTED_VALUE: "CEZ"}): str,
    vol.Required("rate", default = "D57d", description = {SUGGESTED_VALUE: "D57d"}): str,
    vol.Required("tariff", default = "EVV1", description = {SUGGESTED_VALUE: "EVV1"}): str,
    vol.Required("spot_hourly", default = False, description = {SUGGESTED_VALUE: False}): bool,
    vol.Required("cost_fee", default = 0.3, description = {SUGGESTED_VALUE: 0.3}): float,
    vol.Required("compensation_fee", default = 0.4, description = {SUGGESTED_VALUE: 0.4}): float,
    vol.Optional("key", default = "", description = {SUGGESTED_VALUE: ""}): str,
})

class ConfigFlowHandler(ConfigFlow, domain = DOMAIN):
    MINOR_VERSION = 0
    VERSION = 0

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlowHandler:
        _LOGGER.debug(f"ConfigFlowHandler.async_get_options_flow: {entry}")
        return OptionsFlowHandler(entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        _LOGGER.debug(f"ConfigFlowHandler.async_step_user: {user_input}")
        if user_input is None:
            return self.async_show_form(step_id = "user", data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input))
        return self.async_create_entry(title = "Energy Management", data = {}, options = user_input)

class OptionsFlowHandler(OptionsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        _LOGGER.debug(f"OptionsFlowHandler.__init__: {entry}")
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        _LOGGER.debug(f"OptionsFlowHandler.async_step_init: {user_input}, options: {self.entry.options}")
        if user_input is None:
            return self.async_show_form(step_id = "init", data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, self.entry.options))
        return self.async_create_entry(data = user_input)
