from __future__ import annotations

from logging import getLogger

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import TIMEZONE
from .coordinator import Coordinator
from .entity import EnergyManagementEntity

_LOGGER = getLogger(__name__)

async def async_setup_entry(_: HomeAssistant, config_entry: ConfigEntry[Coordinator], async_add_entities: AddEntitiesCallback):
    _LOGGER.debug(f"async_setup_entry: {config_entry}")

    async_add_entities([
        ChargeFromGridSensor(config_entry.runtime_data),
        BelowMeanElectricitySensor(config_entry.runtime_data)
    ])

class EnergyManagementBinarySensorEntity(EnergyManagementEntity, BinarySensorEntity):
    pass

class ChargeFromGridSensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:power-plug-battery"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Charge from Grid"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (o := self.coordinator.optimization):
            return
        now_block = self.now(TIMEZONE)
        #self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[3] for k, v in zip(self.coordinator.consumption.keys(), o)}
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[3] for k, v in zip([i for i in self.coordinator.consumption.keys() if i > now_block], o[1:])}
        #self._attr_is_on = o[self.now_index(self.coordinator.data.zone_info)][3]
        self._attr_is_on = o[0][3] if now_block == self.coordinator.now_block else o[1][3]

class BelowMeanElectricitySensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:cash-clock"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Price below mean"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if (data := self.coordinator.data) is None:
            return
        self._attr_is_on = False
        self._attr_extra_state_attributes["mean"] = float(data.mean)
        self._attr_is_on = data.rates_full[self.now(data.zone_info)] < data.mean

class CheapestElectricitySensor(EnergyManagementBinarySensorEntity):
    _attr_icon = "mdi:cash-clock"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Price cheapest"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if (data := self.coordinator.data) is None:
            return
        self._attr_is_on = data.rates_full[self.now(data.zone_info)] < sorted(list(data.rates.values()))[3]
        #self._attr_extra_state_attributes["rates"] = data.rates_full
        #self._attr_is_on = False
        #now = self.now(data.zone_info)
        ##keys = list(rate_data.rates.keys())[:12] if now.hour < 11 else list(rate_data.rates.keys())[12:] rates = {k: v for k, v in rate_data.rates.items() if k in keys}
        #rates = list(data.rates.items())[:12] if now.hour < 11 else list(data.rates.items())[12:]
        #rates_max = max(rates, key = lambda x: x[1])
        #rates_scoped = rates[:rates.index(rates_max)]
        #if rates_max[1] - min(rates_scoped, key = lambda x: x[1])[1]:
        #    self._attr_is_on = now in dict(sorted(rates_scoped, key = lambda x: x[1])[:1 if now.hour < 11 else 2])
