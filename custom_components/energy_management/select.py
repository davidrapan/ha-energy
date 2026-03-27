from __future__ import annotations

from logging import getLogger

from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .coordinator import Coordinator
from .entity import EnergyManagementEntity

_LOGGER = getLogger(__name__)

async def async_setup_entry(_: HomeAssistant, config_entry: ConfigEntry[Coordinator], async_add_entities: AddEntitiesCallback):
    _LOGGER.debug(f"async_setup_entry: {config_entry}")

    async_add_entities([StrategyNowSelectEntity(config_entry.runtime_data)])

class EnergyManagementSelectEntity(EnergyManagementEntity, SelectEntity):
    def update_options(self, value: str | None):
        self.coordinator.hass.config_entries.async_update_entry(self.coordinator.config_entry, options = {**self.coordinator.config_entry.options} | {self._attr_key: value})

class StrategyNowSelectEntity(EnergyManagementSelectEntity):
    def __init__(self, coordinator):
        self._attr_key = "now_strategy"
        self._attr_name = "Strategy - now"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_options = ["auto", "this_hour_max", "this_hour_avg", "daily_max"]
        super().__init__(coordinator)

    @property
    def current_option(self):
        return self.coordinator.config_now_strategy

    async def async_select_option(self, value: str):
        self.coordinator.config_now_strategy = value
        self.update_options(self.coordinator.config_now_strategy)
        self.async_write_ha_state()
