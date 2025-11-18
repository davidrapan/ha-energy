from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, URL

async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    return {"can_reach_server": system_health.async_check_can_reach_url(hass, URL)}

@callback
def async_register(_: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    register.domain = DOMAIN
    register.async_register_info(system_health_info)
