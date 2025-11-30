"""Set up the Shutter Control integration."""
from __future__ import annotations

import asyncio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_COVERS,
    CONF_CLOSE_POSITION,
    CONF_EXPOSE_SWITCH_SETTINGS,
    CONF_FULL_OPEN_POSITION,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_OPEN_POSITION,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_POSITION,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_VENTILATE_POSITION,
    DOMAIN,
    PLATFORMS,
)
from .controller import ControllerManager

SERVICE_MANUAL_OVERRIDE = "set_manual_override"
SERVICE_ACTIVATE_SHADING = "activate_shading"
SERVICE_CLEAR_MANUAL_OVERRIDE = "clear_manual_override"
SERVICE_RECALIBRATE = "recalibrate_cover"
SERVICE_CHANGE_SWITCH_SETTINGS = "change_switch_settings"

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
    if SERVICE_CHANGE_SWITCH_SETTINGS not in hass.services.async_services_for_domain(DOMAIN):
        time_keys = {
            CONF_TIME_UP_EARLY_WORKDAY,
            CONF_TIME_UP_LATE_WORKDAY,
            CONF_TIME_DOWN_EARLY_WORKDAY,
            CONF_TIME_DOWN_LATE_WORKDAY,
            CONF_TIME_UP_EARLY_NON_WORKDAY,
            CONF_TIME_UP_LATE_NON_WORKDAY,
            CONF_TIME_DOWN_EARLY_NON_WORKDAY,
            CONF_TIME_DOWN_LATE_NON_WORKDAY,
        }

        switch_settings = {
            CONF_AUTO_UP: time_keys,
            CONF_AUTO_DOWN: time_keys,
            CONF_AUTO_VENTILATE: {
                CONF_VENTILATE_POSITION,
                CONF_POSITION_TOLERANCE,
            },
            CONF_AUTO_SHADING: {
                CONF_SHADING_POSITION,
                CONF_SHADING_BRIGHTNESS_START,
                CONF_SHADING_BRIGHTNESS_END,
                CONF_SUN_AZIMUTH_START,
                CONF_SUN_AZIMUTH_END,
                CONF_SUN_ELEVATION_MIN,
                CONF_SUN_ELEVATION_MAX,
            },
            CONF_AUTO_BRIGHTNESS: {
                CONF_BRIGHTNESS_SENSOR,
                CONF_BRIGHTNESS_OPEN_ABOVE,
                CONF_BRIGHTNESS_CLOSE_BELOW,
            },
            CONF_AUTO_SUN: {
                CONF_SUN_ELEVATION_OPEN,
                CONF_SUN_ELEVATION_CLOSE,
                CONF_SUN_AZIMUTH_START,
                CONF_SUN_AZIMUTH_END,
            },
        }

        async def handle_change_switch_settings(call):
            entity_id = call.data.get(ATTR_ENTITY_ID)
            settings = call.data.get("settings")
            if not isinstance(settings, dict):
                raise ValueError("settings must be a mapping")

            registry = er.async_get(hass)
            entity = registry.async_get(entity_id)
            if not entity or entity.platform != DOMAIN:
                raise ValueError(f"No shuttercontrol switch found for {entity_id}")

            entry = hass.config_entries.async_get_entry(entity.config_entry_id)
            if not entry:
                raise ValueError(f"No config entry found for {entity_id}")

            key = None
            if entity.unique_id and entry.entry_id in entity.unique_id:
                parts = entity.unique_id.split(f"{entry.entry_id}-", 1)
                if len(parts) == 2:
                    key = parts[1]
            allowed = switch_settings.get(key)
            if not allowed:
                raise ValueError(f"Switch {entity_id} does not support editable settings")

            filtered = {k: v for k, v in settings.items() if k in allowed}
            if not filtered:
                raise ValueError("No valid settings provided for this switch")

            options = {**entry.options, **filtered}
            hass.config_entries.async_update_entry(entry, options=options)

        hass.services.async_register(
            DOMAIN,
            SERVICE_CHANGE_SWITCH_SETTINGS,
            handle_change_switch_settings,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
                    vol.Required("settings"): dict,
                }
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        if entity_entry.domain in {"number", "text", "time"}:
            registry.async_remove(entity_entry.entity_id)
    
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
