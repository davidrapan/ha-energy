from __future__ import annotations

import voluptuous as vol

from typing import Any
from logging import getLogger

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = getLogger(__name__)

SUGGESTED_VALUE = "suggested_value"

DATA_SCHEMA = vol.Schema({
    vol.Required("area", default = "CEZ", description = {SUGGESTED_VALUE: "CEZ"}): selector.SelectSelector(selector.SelectSelectorConfig(options = ["cez", "egd", "pre"], mode = "dropdown", translation_key = "area")),
    vol.Required("rate", default = "D57d", description = {SUGGESTED_VALUE: "D57d"}): selector.SelectSelector(selector.SelectSelectorConfig(options = ["D01d", "D02d", "D25d", "D26d", "D27d", "D35d", "D45d", "D56d", "D57d", "D61d"], mode = "dropdown")),
    vol.Required("tariff", default = "EVV1", description = {SUGGESTED_VALUE: "EVV1"}): str,
    vol.Required("spot_hourly", default = False, description = {SUGGESTED_VALUE: False}): bool,
    vol.Required("fix"): section(
        vol.Schema({
            vol.Optional("t1_id", description = {SUGGESTED_VALUE: None}): selector.EntitySelector(selector.EntitySelectorConfig(multiple = False)),
            vol.Optional("t2_id", description = {SUGGESTED_VALUE: None}): selector.EntitySelector(selector.EntitySelectorConfig(multiple = False)),
        }),
        {"collapsed": True}
    ),
    vol.Required("cost_fee", default = 0.3, description = {SUGGESTED_VALUE: 0.3}): vol.Coerce(float),
    vol.Required("compensation_fee", default = 0.4, description = {SUGGESTED_VALUE: 0.4}): vol.Coerce(float),
    vol.Required("capacity", default = 9.7, description = {SUGGESTED_VALUE: 9.7}): vol.Coerce(float),
    vol.Required("amortization", default = 2.0, description = {SUGGESTED_VALUE: 2.0}): vol.Coerce(float),
    vol.Optional("battery_entity_ids", description = {SUGGESTED_VALUE: None}): selector.EntitySelector(selector.EntitySelectorConfig(device_class = SensorDeviceClass.BATTERY, multiple = True)),
    vol.Optional("exclude_entity_ids", description = {SUGGESTED_VALUE: None}): selector.EntitySelector(selector.EntitySelectorConfig(device_class = SensorDeviceClass.ENERGY, multiple = True)),
    vol.Optional("export_id", description = {SUGGESTED_VALUE: None}): selector.EntitySelector(selector.EntitySelectorConfig(device_class = SensorDeviceClass.POWER, multiple = False)),
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
