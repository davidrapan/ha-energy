from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .coordinator import Coordinator

async def async_get_config_entry_diagnostics(_: HomeAssistant, config_entry: ConfigEntry[Coordinator]):
    return {
        "config": config_entry,
        "now": {
            "time": config_entry.runtime_data.now.isoformat(),
            "battery": config_entry.runtime_data.battery
        },
        "triad": {k.isoformat(): (float(v), config_entry.runtime_data.forecast[k], config_entry.runtime_data.consumption[k]) for k, v in config_entry.runtime_data.data.rates_full.items()},
        "optimization": config_entry.runtime_data.optimization
    }
