"""Set up the Shutter Control integration."""
from __future__ import annotations

import asyncio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .config_entities import ensure_config_entities
from .const import (
    CONF_COVERS,
    CONF_FULL_OPEN_POSITION,
    CONF_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_OPEN_POSITION,
    DOMAIN,
    PLATFORMS,
)
from .controller import ControllerManager

SERVICE_MANUAL_OVERRIDE = "set_manual_override"
SERVICE_ACTIVATE_SHADING = "activate_shading"
SERVICE_CLEAR_MANUAL_OVERRIDE = "clear_manual_override"
SERVICE_RECALIBRATE = "recalibrate_cover"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize integration-level storage and services."""
    hass.data.setdefault(DOMAIN, {})

    if SERVICE_MANUAL_OVERRIDE not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_manual_override(call):
            cover = call.data[CONF_COVERS]
            minutes = call.data.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and manager.set_manual_override(cover, minutes):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_MANUAL_OVERRIDE,
            handle_manual_override,
            schema=cv.make_entity_service_schema(
                {vol.Required(CONF_COVERS): cv.entity_id, vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES): cv.positive_int}
            ),
        )

    if SERVICE_ACTIVATE_SHADING not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_activate_shading(call):
            cover = call.data[CONF_COVERS]
            minutes = call.data.get(CONF_MANUAL_OVERRIDE_MINUTES)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and manager.activate_shading(cover, minutes):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_ACTIVATE_SHADING,
            handle_activate_shading,
            schema=cv.make_entity_service_schema(
                {vol.Required(CONF_COVERS): cv.entity_id, vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES): cv.positive_int}
            ),
        )
    if SERVICE_CLEAR_MANUAL_OVERRIDE not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_clear_manual_override(call):
            cover = call.data[CONF_COVERS]
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and manager.clear_manual_override(cover):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_MANUAL_OVERRIDE,
            handle_clear_manual_override,
            schema=cv.make_entity_service_schema({vol.Required(CONF_COVERS): cv.entity_id}),
        )
    if SERVICE_RECALIBRATE not in hass.services.async_services_for_domain(DOMAIN):
        def _resolve_cover(call) -> str:
            cover = call.data.get(CONF_COVERS) or call.data.get(ATTR_ENTITY_ID)
            if cover is None:
                raise ValueError("No cover entity provided")
            if isinstance(cover, list):
                if len(cover) != 1:
                    raise ValueError("Provide a single cover entity for recalibration")
                return cover[0]
            return cover
        async def handle_recalibrate(call):
            cover = _resolve_cover(call)
            full_open = call.data.get(CONF_FULL_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager):
                    if await manager.recalibrate_cover(cover, full_open):
                        matched = True
                        break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_RECALIBRATE,
            handle_recalibrate,
            schema=vol.Schema(
                {
                vol.Optional(CONF_COVERS): vol.Any(cv.entity_id, [cv.entity_id]),
                vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_id, [cv.entity_id]),
                vol.Optional(CONF_FULL_OPEN_POSITION, default=DEFAULT_OPEN_POSITION): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=100)
                ),
                }
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    await ensure_config_entities(hass, entry.entry_id, {**entry.data, **entry.options})
    created_entities = await ensure_config_entities(
        hass, entry.entry_id, {**entry.data, **entry.options}
    )
    if created_entities:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, **created_entities}
        )

    manager = ControllerManager(hass, entry)
    await manager.async_setup()
    hass.data[DOMAIN][entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_handle_options_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager: ControllerManager | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if manager:
        await manager.async_unload()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    manager: ControllerManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        manager.async_update_options()
