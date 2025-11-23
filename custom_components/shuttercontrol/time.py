"""Time entities to configure open/close windows."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_TIME_UP_WORKDAY,
    CONF_TIME_UP_NON_WORKDAY,
    CONF_TIME_DOWN_WORKDAY,
    CONF_TIME_DOWN_NON_WORKDAY,
    DOMAIN,
)
from .controller import ControllerManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register time entities for scheduling."""

    entities: list[TimeEntity] = [
        ShutterTimeEntity(entry, CONF_TIME_UP_WORKDAY, "time_up_workday"),
        ShutterTimeEntity(entry, CONF_TIME_DOWN_WORKDAY, "time_down_workday"),
        ShutterTimeEntity(entry, CONF_TIME_UP_NON_WORKDAY, "time_up_non_workday"),
        ShutterTimeEntity(entry, CONF_TIME_DOWN_NON_WORKDAY, "time_down_non_workday"),
    ]

    async_add_entities(entities)

    manager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    manager.async_update_options()


class ShutterTimeEntity(TimeEntity):
    """Time entity that stores schedule windows in config entry options."""

    _attr_should_poll = False

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
    def native_value(self) -> time | None:
        value = self.entry.options.get(self._key, self.entry.data.get(self._key))
        if not value:
            return None
        try:
            return dt_util.parse_time(value)
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        options = {**self.entry.options, self._key: value.isoformat()}
        await self.hass.config_entries.async_update_entry(self.entry, options=options)
