"""Expose controller state as sensor entities."""
from __future__ import annotations

from datetime import datetime

from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import CONF_AUTO_SHADING, CONF_NAME, DEFAULT_NAME, DOMAIN, SIGNAL_STATE_UPDATED
from .controller import ControllerManager

def _instance_name(entry: ConfigEntry) -> str:
    return entry.options.get(CONF_NAME, entry.data.get(CONF_NAME, entry.title or DEFAULT_NAME))

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for cover, controller in manager.controllers.items():
        entities.extend(
            [
                ShutterNextOpenSensor(entry, cover),
                ShutterNextCloseSensor(entry, cover),
                ShutterVentilationSensor(entry, cover),
            ]
        )
        if controller.config.get(CONF_AUTO_SHADING):
            entities.append(ShutterShadingActiveSensor(entry, cover))
    async_add_entities(entities)


class ShutterBaseSensor(SensorEntity):
    """Common helpers for per-cover sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, cover: str, suffix: str, translation_key: str) -> None:
        self.entry = entry
        self.cover = cover
        self._reason: str | None = None
        self._manual_until: datetime | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        self._shading_enabled: bool = False
        self._shading_active: bool = False
        self._ventilation_active: bool = False
        slug = slugify(cover.split(".")[-1])
        self._attr_unique_id = f"{entry.entry_id}-{slug}-{suffix}"
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {"cover": slug}

    @property
    def extra_state_attributes(self):
        return {
            "reason": self._reason,
            "manual_override_until": self._manual_until.isoformat() if self._manual_until else None,
            "cover_entity": self.cover,
            "next_open": self._next_open.isoformat() if self._next_open else None,
            "next_close": self._next_close.isoformat() if self._next_close else None,
            "shading_enabled": self._shading_enabled,
            "shading_active": self._shading_active,
            "ventilation": self._ventilation_active,
            "manual_override": bool(
                self._manual_until and dt_util.utcnow() < self._manual_until
            ),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=_instance_name(self.entry),
            manufacturer="CCA-derived",
        )

    async def async_added_to_hass(self) -> None:
        self._attr_translation_placeholders = {"cover": self._cover_label()}
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATE_UPDATED,
                self._handle_state_update,
            )
        )

    @callback
    def _cover_label(self) -> str:
        state = self.hass.states.get(self.cover)
        if state and state.name:
            return state.name
        return self.cover.split(".")[-1]

    @callback
    def _handle_state_update(
        self,
        entry_id: str,
        cover: str,
        reason: str | None,
        manual_until: datetime | None,
        next_open: datetime | None,
        next_close: datetime | None,
        shading_enabled: bool,
        shading_active: bool,
        ventilation: bool,
    ) -> None:
        if entry_id != self.entry.entry_id or cover != self.cover:
            return
        self._reason = reason
        self._manual_until = manual_until
        self._next_open = next_open
        self._next_close = next_close
        self._shading_enabled = shading_enabled
        self._shading_active = shading_active
        self._ventilation_active = ventilation
        self.async_write_ha_state()


class ShutterNextOpenSensor(ShutterBaseSensor):
    """Expose the next planned opening time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-time-eight"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "next-open", "next_open")

    @property
    def native_value(self) -> datetime | None:
        return self._next_open


class ShutterNextCloseSensor(ShutterBaseSensor):
    """Expose the next planned closing time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-time-five"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "next-close", "next_close")

    @property
    def native_value(self) -> datetime | None:
        return self._next_close


class ShutterShadingActiveSensor(ShutterBaseSensor):
    """Expose whether shading mode is active."""

    _attr_icon = "mdi:sunglasses"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "shading", "shading_active")

    @property
    def native_value(self) -> bool:
        return self._shading_active

    @property
    def available(self) -> bool:
        return self._shading_enabled


class ShutterVentilationSensor(ShutterBaseSensor):
    """Expose whether ventilation mode is active."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "ventilation", "ventilation")

    @property
    def native_value(self) -> bool:
        return self._ventilation_active
