from __future__ import annotations

import logging

from homeassistant import loader
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .common import strepr
from .coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = config_validation.empty_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    _LOGGER.debug(f"async_setup")

    try:
        _LOGGER.info(f"Energy Management {str((await loader.async_get_integration(hass, DOMAIN)).version)}")
    except loader.IntegrationNotFound as e:
        _LOGGER.debug(f"Error reading version: {strepr(e)}")

    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry[Coordinator]):
    _LOGGER.debug(f"async_setup_entry({config_entry.as_dict()})")

    # Initiaize coordinator and fetch initial data
    #
    _LOGGER.debug(f"async_setup_entry: Coordinator.init -> async_config_entry_first_refresh")

    config_entry.runtime_data = await Coordinator(hass, config_entry).init()

    # Forward setup
    #
    _LOGGER.debug(f"async_setup_entry: hass.config_entries.async_forward_entry_setups: {_PLATFORMS}")

    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    # Add update listener
    #
    _LOGGER.debug(f"async_setup_entry: config_entry.add_update_listener(async_update_listener)")

    async def async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry[Coordinator]) -> None:
        _LOGGER.debug(f"async_update_listener({config_entry.as_dict()})")
        await hass.config_entries.async_reload(config_entry.entry_id)

    config_entry.async_on_unload(config_entry.add_update_listener(async_update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry[Coordinator]) -> bool:
    _LOGGER.debug(f"async_unload_entry({config_entry.as_dict()})")

    # Forward unload
    #
    _LOGGER.debug(f"async_unload_entry: hass.config_entries.async_unload_platforms: {_PLATFORMS}")

    return await hass.config_entries.async_unload_platforms(config_entry, _PLATFORMS)
