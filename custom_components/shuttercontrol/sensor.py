"""Sensor entities for Shutter Control profiles."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from . import ShutterController, ShutterProfile


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for each configured shutter profile."""

    controller: ShutterController = hass.data[DOMAIN][entry.entry_id]
    entities: list[ShutterProfileSensor] = []

    for profile in controller.profiles:
        entities.append(ShutterProfileSensor(controller, profile, entry.entry_id))

    async_add_entities(entities)


class ShutterProfileSensor(SensorEntity):
    """Expose status datapoints for each configured shutter."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:blinds"

    def __init__(
        self, controller: ShutterController, profile: ShutterProfile, entry_id: str
    ) -> None:
        self._controller = controller
        self._profile = profile
        self._attr_unique_id = f"{entry_id}_{profile.entity_id}_shuttercontrol"
        self._attr_name = (
            f"{profile.name or profile.entity_id} shuttercontrol state"
        )
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {
            ATTR_ENTITY_ID: profile.entity_id,
            "room": profile.room,
            "last_reason": None,
            "last_updated": None,
            "open_position": profile.open_position,
            "close_position": profile.close_position,
            "sunrise_offset": profile.sunrise_offset,
            "sunset_offset": profile.sunset_offset,
            "window_sensors": profile.window_sensors,
        }
        self._unsub: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register for controller callbacks when entity is added."""

        def _handle(profile: ShutterProfile, reason: str, position: int) -> None:
            if profile.entity_id != self._profile.entity_id:
                return
            self._attr_native_value = position
            self._attr_extra_state_attributes.update(
                {
                    "last_reason": reason,
                    "last_updated": datetime.utcnow().isoformat(),
                }
            )
            self.async_write_ha_state()

        self._unsub = self._controller.register_listener(_handle)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks on entity removal."""

        if self._unsub:
            self._unsub()
            self._unsub = None
