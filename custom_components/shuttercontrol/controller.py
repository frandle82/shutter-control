"""Numbers to control shutter positions."""
from __future__ import annotations
import inspect

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CLOSE_POSITION,
    CONF_OPEN_POSITION,
    CONF_SHADING_POSITION,
    CONF_VENTILATE_POSITION,
    DOMAIN,
)
from .controller import ControllerManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register configurable number entities."""

    entities: list[NumberEntity] = [
        ShutterPositionNumber(entry, CONF_OPEN_POSITION, "open_position"),
        ShutterPositionNumber(entry, CONF_CLOSE_POSITION, "close_position"),
        ShutterPositionNumber(entry, CONF_VENTILATE_POSITION, "ventilate_position"),
        ShutterPositionNumber(entry, CONF_SHADING_POSITION, "shading_position"),
    ]

    async_add_entities(entities)

    # Refresh controllers so they honor updated options as soon as they exist.
    manager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    manager.async_update_options()


class ShutterPositionNumber(NumberEntity):
    """Number entity that updates config entry options for positions."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, entry: ConfigEntry, key: str, translation_key: str) -> None:
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {}
        self._attr_name = f"Shutter {translation_key}"  # replaced via translations

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="Shutter Control",
            manufacturer="CCA-derived",
        )

    @property
    def native_value(self) -> float | None:
        value = self.entry.options.get(self._key, self.entry.data.get(self._key))
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        options = {**self.entry.options, self._key: float(value)}
        update_result = self.hass.config_entries.async_update_entry(
            self.entry, options=options
        )
        if inspect.isawaitable(update_result):
            await update_result
