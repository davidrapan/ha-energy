from __future__ import annotations

from logging import getLogger

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import BinarySensorEntity

from .coordinator import Coordinator
from .entity import EnergyManagementEntity

_LOGGER = getLogger(__name__)

async def async_setup_entry(_: HomeAssistant, config_entry: ConfigEntry[Coordinator], async_add_entities: AddEntitiesCallback):
    _LOGGER.debug(f"async_setup_entry: {config_entry}")

    async_add_entities([
        BatteryChargeFromGridSensor(config_entry.runtime_data),
        BatteryDischargeToGridSensor(config_entry.runtime_data),
        SuppressExportSensor(config_entry.runtime_data),
        CostRateBelowMeanElectricitySensor(config_entry.runtime_data)
    ])

class EnergyManagementBinarySensorEntity(EnergyManagementEntity, BinarySensorEntity):
    pass

class BatteryChargeFromGridSensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:power-plug-battery"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Battery - charge from Grid"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (o := self.coordinator.optimization):
            return
        #self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[3] for k, v in zip(self.coordinator.consumption.keys(), o)}
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[3] for k, v in zip([i for i in self.coordinator.consumption.keys() if i > self.coordinator.data.now], o[1:])}
        #self._attr_is_on = o[self.now_index(self.coordinator.data.zone_info)][3]
        self._attr_is_on = o[0][3] if self.coordinator.now == self.coordinator.data.now else o[1][3]

class BatteryDischargeToGridSensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:power-plug-battery-outline"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Battery - discharge to Grid"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (o := self.coordinator.optimization):
            return
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[4] for k, v in zip([i for i in self.coordinator.consumption.keys() if i > self.coordinator.data.now], o[1:])}
        self._attr_is_on = o[0][4] if self.coordinator.now == self.coordinator.data.now else o[1][4]

class SuppressExportSensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Suppress export"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (data := self.coordinator.data):
            return
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v < 0 for k, v in data.compensation_rate.items()}
        self._attr_is_on = data.compensation_rate[data.now] < 0

class CostRateBelowMeanElectricitySensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:cash-clock"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Cost rate - below mean"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if (data := self.coordinator.data) is None:
            return
        self._attr_is_on = False
        self._attr_extra_state_attributes["mean"] = float(data.mean)
        self._attr_is_on = data.rates_full[data.now] < data.mean
