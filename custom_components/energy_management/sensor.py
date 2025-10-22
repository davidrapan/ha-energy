from __future__ import annotations

from logging import getLogger

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, RestoreSensor
from homeassistant.const import ATTR_IDENTIFIERS, ATTR_NAME, ATTR_VIA_DEVICE

from .const import DOMAIN, TIMEZONE
from .common import slugify
from .coordinator import Coordinator
from .entity import EnergyManagementEntity

_LOGGER = getLogger(__name__)

async def async_setup_entry(_: HomeAssistant, config_entry: ConfigEntry[Coordinator], async_add_entities: AddEntitiesCallback):
    _LOGGER.debug(f"async_setup_entry: {config_entry}")

    async_add_entities([
        CompRate(config_entry.runtime_data),
        CostRate(config_entry.runtime_data),
        SpotRate(config_entry.runtime_data),
        Order(config_entry.runtime_data),
        PriceToday(config_entry.runtime_data),
        Cost(config_entry.runtime_data),
        Consumption(config_entry.runtime_data),
        Battery(config_entry.runtime_data)
    ])

class EnergyManagementSensorEntity(EnergyManagementEntity, SensorEntity):
    pass

class EnergyManagementRestoreSensor(EnergyManagementEntity, RestoreSensor):
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if last_sensor_data := await self.async_get_last_sensor_data():
            self._attr_native_value = last_sensor_data.native_value

class CompRate(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Compensation rate"
        self._attr_native_unit_of_measurement = "CZK/kWh"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (data := self.coordinator.data):
            return
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): float(v) for k, v in data.compensation_rate.items()}
        self._attr_native_value = data.compensation_rate[self.now(data.zone_info)]

class CostRate(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Cost rate"
        self._attr_native_unit_of_measurement = "CZK/kWh"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (data := self.coordinator.data):
            return
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): float(v) for k, v in data.rates_full.items()}
        self._attr_native_value = data.rates_full[self.now(data.zone_info)]

class SpotRate(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Spot rate"
        self._attr_native_unit_of_measurement = "CZK/kWh"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (data := self.coordinator.data):
            return
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): float(v) for k, v in data.spot_rate.items()}
        self._attr_native_value = data.spot_rate[self.now(data.zone_info)]

class Order(EnergyManagementSensorEntity):
    _attr_icon = "mdi:order-numeric-ascending"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Order"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if (data := self.coordinator.data) is None:
            return
        self._attr_native_value = sorted(set(data.rates.values())).index(data.rates[self.now(data.zone_info)]) + 1

class Price(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Price"
        self._attr_native_unit_of_measurement = "CZK" if coordinator.hass.config.currency in ("CZK", "Kč") else "EUR"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (data := self.coordinator.data):
            return
        self._attr_extra_state_attributes["mean"] = float(data.mean)
        self._attr_extra_state_attributes["values"] = {k.astimezone(self.coordinator.data.zone_info).isoformat(): float(v) for k, v in data.rates_full.items()}
        self._attr_native_value = data.rates_full[self.now(data.zone_info)]

class PriceToday(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Price - today"
        self._attr_native_unit_of_measurement = "CZK" if coordinator.hass.config.currency in ("CZK", "Kč") else "EUR"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)

    def update(self):
        super().update()
        self._attr_native_value = self.coordinator.price or self.coordinator.data.mean

class Consumption(EnergyManagementSensorEntity):
    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Consumption"
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_native_unit_of_measurement = "kWh"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (c := self.coordinator.consumption):
            return
        self._attr_extra_state_attributes["mean"] = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v for k, v in c.items()}
        self._attr_extra_state_attributes["latest"] = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v for k, v in self.coordinator.today_consumption.items() if v is not None}
        self._attr_native_value = c[self.now(TIMEZONE)]

class Battery(EnergyManagementSensorEntity):
    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Battery"
        self._attr_device_class = "battery"
        self._attr_native_unit_of_measurement = "%"
        super().__init__(coordinator)

    def update(self):
        super().update()
        if not (o := self.coordinator.optimization):
            return
        now_block = self.now(TIMEZONE)
        #self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[0] for k, v in zip(self.coordinator.consumption.keys(), o)}
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[0] for k, v in zip([i for i in self.coordinator.consumption.keys() if i > now_block], o[1:])}
        #self._attr_native_value = o[self.now_index(self.coordinator.data.zone_info)][0]
        self._attr_native_value = o[0][0] if now_block == self.coordinator.now_block else o[1][0]

class Cost(EnergyManagementRestoreSensor):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Cost"
        self._attr_state_class = "total_increasing"
        self._attr_native_unit_of_measurement = "CZK" if coordinator.hass.config.currency in ("CZK", "Kč") else "EUR"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)

    def update(self):
        if (cost_values := list(self.coordinator.cost_total.values())) and (cost_total := cost_values[0]) is not None:
            super().update()
            self._attr_native_value = cost_total

class PredictedCost(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Cost"
        self._attr_state_class = "total"
        self._attr_native_unit_of_measurement = "CZK" if coordinator.hass.config.currency in ("CZK", "Kč") else "EUR"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)
        i = slugify(coordinator.config_entry.entry_id, "Predicted")
        self._attr_unique_id = slugify(i, self._attr_name)
        self._attr_device_info |= {
            ATTR_IDENTIFIERS: {(DOMAIN, i)},
            ATTR_NAME: f"{self._attr_device_info[ATTR_NAME]} Predicted",
            ATTR_VIA_DEVICE: (DOMAIN, coordinator.config_entry.entry_id)
        }

    def update(self):
        super().update()
        self._attr_native_value = self.coordinator.predicted_cost

class PredictedAmortization(EnergyManagementSensorEntity):
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Amortization"
        self._attr_state_class = "total"
        self._attr_native_unit_of_measurement = "CZK" if coordinator.hass.config.currency in ("CZK", "Kč") else "EUR"
        self._attr_suggested_display_precision = 2
        super().__init__(coordinator)
        i = slugify(coordinator.config_entry.entry_id, "Predicted")
        self._attr_unique_id = slugify(i, self._attr_name)
        self._attr_device_info |= {
            ATTR_IDENTIFIERS: {(DOMAIN, i)},
            ATTR_NAME: f"{self._attr_device_info[ATTR_NAME]} Predicted",
            ATTR_VIA_DEVICE: (DOMAIN, coordinator.config_entry.entry_id)
        }

    def update(self):
        super().update()
        self._attr_native_value = self.coordinator.predicted_amortization

class PredictedBattery(EnergyManagementSensorEntity):
    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Battery"
        self._attr_device_class = "battery"
        self._attr_native_unit_of_measurement = "%"
        super().__init__(coordinator)
        i = slugify(coordinator.config_entry.entry_id, "Predicted")
        self._attr_unique_id = slugify(i, self._attr_name)
        self._attr_device_info |= {
            ATTR_IDENTIFIERS: {(DOMAIN, i)},
            ATTR_NAME: f"{self._attr_device_info[ATTR_NAME]} Predicted",
            ATTR_VIA_DEVICE: (DOMAIN, coordinator.config_entry.entry_id)
        }

    def update(self):
        super().update()
        if not (o := self.coordinator.optimization):
            return
        now_block = self.now(TIMEZONE)
        #self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[1] for k, v in zip(self.coordinator.consumption.keys(), o)}
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[1] for k, v in zip([i for i in self.coordinator.consumption.keys() if i > now_block], o[1:])}
        #self._attr_native_value = o[self.now_index(self.coordinator.data.zone_info)][1]
        self._attr_native_value = o[0][1] if now_block == self.coordinator.now_block else o[1][1]

class PredictedEnergy(EnergyManagementSensorEntity):
    def __init__(self, coordinator: Coordinator) -> None:
        self._attr_name = "Energy"
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_native_unit_of_measurement = "kWh"
        super().__init__(coordinator)
        i = slugify(coordinator.config_entry.entry_id, "Predicted")
        self._attr_unique_id = slugify(i, self._attr_name)
        self._attr_device_info |= {
            ATTR_IDENTIFIERS: {(DOMAIN, i)},
            ATTR_NAME: f"{self._attr_device_info[ATTR_NAME]} Predicted",
            ATTR_VIA_DEVICE: (DOMAIN, coordinator.config_entry.entry_id)
        }

    def update(self):
        super().update()
        if not (o := self.coordinator.optimization):
            return
        now_block = self.now(TIMEZONE)
        #self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[2] for k, v in zip(self.coordinator.consumption.keys(), o)}
        self._attr_extra_state_attributes = {k.astimezone(self.coordinator.data.zone_info).isoformat(): v[2] for k, v in zip([i for i in self.coordinator.consumption.keys() if i > now_block], o[1:])}
        #self._attr_native_value = o[self.now_index(self.coordinator.data.zone_info)][2]
        self._attr_native_value = o[0][2] if now_block == self.coordinator.now_block else o[1][2]
