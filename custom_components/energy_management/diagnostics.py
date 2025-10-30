from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .coordinator import Coordinator

async def async_get_config_entry_diagnostics(_: HomeAssistant, config_entry: ConfigEntry[Coordinator]):
    return {
        "config": config_entry,
        "now": config_entry.runtime_data.now,
        "data": config_entry.runtime_data.data,
        "battery": config_entry.runtime_data.battery,
        "consumption": config_entry.runtime_data.consumption,
        "optimization": config_entry.runtime_data.optimization
    }
