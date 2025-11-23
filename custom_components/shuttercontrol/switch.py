"""Switch entities to control automation toggles."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_COLD,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
)


AUTOMATION_TOGGLES: tuple[tuple[str, str], ...] = (
    (CONF_AUTO_UP, "auto_up"),
    (CONF_AUTO_DOWN, "auto_down"),
    (CONF_AUTO_BRIGHTNESS, "auto_brightness"),
    (CONF_AUTO_SUN, "auto_sun"),
    (CONF_AUTO_VENTILATE, "auto_ventilate"),
    (CONF_AUTO_SHADING, "auto_shading"),
    (CONF_AUTO_COLD, "auto_cold"),
)

TOGGLE_ICONS: dict[str, str] = {
    CONF_AUTO_UP: "mdi:arrow-up-bold-circle",
    CONF_AUTO_DOWN: "mdi:arrow-down-bold-circle",
    CONF_AUTO_BRIGHTNESS: "mdi:brightness-auto",
    CONF_AUTO_SUN: "mdi:weather-sunny",
    CONF_AUTO_VENTILATE: "mdi:fan-auto",
    CONF_AUTO_SHADING: "mdi:theme-light-dark",
    CONF_AUTO_COLD: "mdi:snowflake-variant",
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register automation toggle switches."""

    entities: list[SwitchEntity] = [
        AutomationToggleSwitch(entry, key, translation_key)
        for key, translation_key in AUTOMATION_TOGGLES
    ]

    async_add_entities(entities)


class AutomationToggleSwitch(SwitchEntity):
    """Switch to enable or disable automation features."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, key: str, translation_key: str) -> None:
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_translation_key = translation_key
        self._attr_icon = TOGGLE_ICONS.get(key)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=entry.options.get(CONF_NAME, entry.data.get(CONF_NAME, entry.title or DEFAULT_NAME)),
            manufacturer="CCA-derived",
        )

    @property
    def is_on(self) -> bool:
        value = self.entry.options.get(self._key, self.entry.data.get(self._key))
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: True}
        await self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: False}
        await self.hass.config_entries.async_update_entry(self.entry, options=options)
