"""Expose controller state as sensor entities."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, SIGNAL_STATE_UPDATED
from .controller import ControllerManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for cover in manager.controllers:
        entities.append(ShutterControlSensor(entry, cover))
    async_add_entities(entities)


class ShutterControlSensor(SensorEntity):
    """Represent target position and reason from the controller."""

    _attr_icon = "mdi:window-shutter-settings"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        self.entry = entry
        self.cover = cover
        self._state: float | None = None
        self._reason: str | None = None
        self._manual_until: datetime | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        slug = slugify(cover.split(".")[-1])
        self._attr_unique_id = f"{entry.entry_id}-{slug}-target"
        self._attr_name = f"Shutter target {slug}"  # renamed via translations
        self._attr_translation_key = "target"
        self._attr_translation_placeholders = {"cover": slug}

    @property
    def native_value(self) -> float | None:
        """Return the last commanded position."""

        return self._state

    @property
    def extra_state_attributes(self):
        return {
            "reason": self._reason,
            "manual_override_until": self._manual_until.isoformat() if self._manual_until else None,
            "cover_entity": self.cover,
            "next_open": self._next_open.isoformat() if self._next_open else None,
            "next_close": self._next_close.isoformat() if self._next_close else None,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="Shutter Control",
            manufacturer="CCA-derived",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATE_UPDATED,
                self._handle_state_update,
            )
        )

    @callback
    def _handle_state_update(
        self,
        entry_id: str,
        cover: str,
        target: float | None,
        reason: str | None,
        manual_until: datetime | None,
        next_open: datetime | None,
        next_close: datetime | None,
    ) -> None:
        if entry_id != self.entry.entry_id or cover != self.cover:
            return
        self._state = target
        self._reason = reason
        self._manual_until = manual_until
        self._next_open = next_open
        self._next_close = next_close
        self.async_write_ha_state()
