from __future__ import annotations

from typing import Any
from decimal import Decimal
from datetime import date, datetime, time

from homeassistant.util import slugify
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import StateType

from .coordinator import Coordinator

class EnergyManagementEntity(CoordinatorEntity[Coordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: Coordinator):
        super().__init__(coordinator)
        self._attr_device_info = self.coordinator.default_service_info.copy()
        self._attr_unique_id = slugify('_'.join(filter(None, (self.coordinator.config_entry.entry_id, self._attr_name))))
        self._attr_native_value: StateType | str | date | datetime | time | float | Decimal | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._attr_is_on: bool | None = None
        self.update()

    @property
    def available(self) -> bool:
        return self._attr_native_value is not None or self._attr_is_on is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        self.update()
        self.async_write_ha_state()

    def update(self):
        self._attr_extra_state_attributes = {}
        self._attr_native_value = None
        self._attr_is_on = False
