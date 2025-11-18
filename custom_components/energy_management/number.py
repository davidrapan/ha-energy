from __future__ import annotations

from logging import getLogger

from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import RestoreNumber, NumberDeviceClass, NumberMode

from .coordinator import Coordinator
from .entity import EnergyManagementEntity

_LOGGER = getLogger(__name__)

async def async_setup_entry(_: HomeAssistant, config_entry: ConfigEntry[Coordinator], async_add_entities: AddEntitiesCallback):
    _LOGGER.debug(f"async_setup_entry: {config_entry}")

    async_add_entities([
        ChargePowerNumberEntity(config_entry.runtime_data),
        DischargePowerNumberEntity(config_entry.runtime_data),
        MinSOCNumberEntity(config_entry.runtime_data),
        MaxSOCNumberEntity(config_entry.runtime_data)
    ])

class EnergyManagementRestoreNumber(EnergyManagementEntity, RestoreNumber):
    pass

class MaxSOCNumberEntity(EnergyManagementRestoreNumber):
    def __init__(self, coordinator):
        self._attr_name = "Battery - maximum"
        self._attr_device_class = NumberDeviceClass.BATTERY
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_unit_of_measurement = "%"
        self._attr_mode = NumberMode.BOX
        self._attr_max_value = 100
        self._attr_min_value = 0
        super().__init__(coordinator)

    @property
    def native_value(self):
        return self.coordinator.number_soc_max

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if last_number_data := await self.async_get_last_number_data():
            self.coordinator.number_soc_max = int(last_number_data.native_value)

    async def async_set_native_value(self, value: float):
        self.coordinator.number_soc_max = int(value)
        self.async_write_ha_state()

class MinSOCNumberEntity(EnergyManagementRestoreNumber):
    def __init__(self, coordinator):
        self._attr_name = "Battery - minimum"
        self._attr_device_class = NumberDeviceClass.BATTERY
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_unit_of_measurement = "%"
        self._attr_mode = NumberMode.BOX
        self._attr_max_value = 100
        self._attr_min_value = 0
        super().__init__(coordinator)

    @property
    def native_value(self):
        return self.coordinator.number_soc_min

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if last_number_data := await self.async_get_last_number_data():
            self.coordinator.number_soc_min = int(last_number_data.native_value)

    async def async_set_native_value(self, value: float):
        self.coordinator.number_soc_min = int(value)
        self.async_write_ha_state()

class ChargePowerNumberEntity(EnergyManagementRestoreNumber):
    def __init__(self, coordinator):
        self._attr_name = "Battery - charge power"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_class = NumberDeviceClass.POWER
        self._attr_native_unit_of_measurement = "kW"
        self._attr_suggested_display_precision = 1
        self._attr_mode = NumberMode.BOX
        self._attr_native_step = 0.1
        self._attr_min_value = 0.0
        super().__init__(coordinator)

    @property
    def native_value(self):
        return self.coordinator.number_charge_power

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if last_number_data := await self.async_get_last_number_data():
            self.coordinator.number_charge_power = last_number_data.native_value

    async def async_set_native_value(self, value: float):
        self.coordinator.number_charge_power = value
        self.async_write_ha_state()

class DischargePowerNumberEntity(EnergyManagementRestoreNumber):
    def __init__(self, coordinator):
        self._attr_name = "Battery - discharge power"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_class = NumberDeviceClass.POWER
        self._attr_native_unit_of_measurement = "kW"
        self._attr_suggested_display_precision = 1
        self._attr_mode = NumberMode.BOX
        self._attr_native_step = 0.1
        self._attr_min_value = 0.0
        super().__init__(coordinator)

    @property
    def native_value(self):
        return self.coordinator.number_discharge_power

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if last_number_data := await self.async_get_last_number_data():
            self.coordinator.number_discharge_power = last_number_data.native_value

    async def async_set_native_value(self, value: float):
        self.coordinator.number_discharge_power = value
        self.async_write_ha_state()
