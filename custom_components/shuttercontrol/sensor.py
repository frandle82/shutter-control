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
from .controller import ControllerManager, IDLE_REASON

REASON_LABELS = {
    "manual_override": "Manuelle Steuerung",
    "manual_shading": "Beschattung aktiv",
    "shading": "Beschattung aktiv",
    "shading_end_close": "Beschattung deaktiv",
    "shading_end_open": "Beschattung deaktiv",
    "sun_close": "Schließung(Sonnenuntergang)",
    "sun_open": "Öffnung(Sonnenaufgang)",
    "scheduled_close": "Schließung(Zeit)",
    "scheduled_open": "Öffnung(Zeit)",
    "ventilation": "Lüftung",
    "wind_protection": "Windschutz",
    "resident_asleep": "Bewohner schläft",
    "cold_protection": "Kälteschutz",
    IDLE_REASON: "Keine Aktion",
}

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
                ShutterReasonSensor(entry, cover),
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
    
    def _normalize_dt(self, value: datetime | str | None) -> datetime | None:
        """Ensure dispatcher values are stored as timezone-aware datetimes."""

        if isinstance(value, datetime):
            return value
        if not value:
            return None
        parsed = dt_util.parse_datetime(str(value))
        if parsed:
            return dt_util.as_utc(parsed)
        return None

    @property
    def extra_state_attributes(self):
        return {
            "reason": self._reason or IDLE_REASON,
            "manual_override_until": self._manual_until.isoformat() if isinstance(self._manual_until, datetime) else self._manual_until,
            "cover_entity": self.cover,
            "next_open": self._next_open.isoformat() if isinstance(self._next_open, datetime) else self._next_open,
            "next_close": self._next_close.isoformat() if isinstance(self._next_close, datetime) else self._next_close,
            "shading_enabled": self._shading_enabled,
            "shading_active": self._shading_active,
            "ventilation": self._ventilation_active,
            "manual_override": bool(
                isinstance(self._manual_until, datetime)
                and self._manual_until
                and dt_util.utcnow() < self._manual_until
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
        manager: ControllerManager = self.hass.data[DOMAIN][self.entry.entry_id]
        snapshot = manager.state_snapshot(self.cover)
        if snapshot:
            (
                self._target,
                self._reason,
                self._manual_until,
                self._next_open,
                self._next_close,
                self._current_position,
                self._shading_enabled,
                self._shading_active,
                self._ventilation_active,
            ) = snapshot
            self._manual_until = self._normalize_dt(self._manual_until)
            self._next_open = self._normalize_dt(self._next_open)
            self._next_close = self._normalize_dt(self._next_close)
            self._reason = self._reason or IDLE_REASON
        else:
            self._reason = IDLE_REASON
            self._shading_enabled = False
            self._shading_active = False
            self._ventilation_active = False

        self.async_write_ha_state()

        # Some Home Assistant instances may still hold an older manager
        # instance that does not expose ``publish_state``. Guard the call so
        # sensors can finish setup instead of failing with ``AttributeError``.
        if hasattr(manager, "publish_state"):
            manager.publish_state(self.cover)

    @callback
    def _cover_label(self) -> str:
        state = self.hass.states.get(self.cover)
        if state and state.name:
            return state.name
        return self.cover.split(".")[-1]

    @callback
    def _handle_state_update(self, *payload: object) -> None:
        # Normalize dispatcher payloads from different versions and pad any
        # missing values to avoid runtime NameError issues during unpacking.
        (
            entry_id,
            cover,
            target,
            reason,
            manual_until,
            next_open,
            next_close,
            current_position,
            shading_enabled,
            shading_active,
            ventilation,
            *_,
        ) = (*payload, None, None, None, None, None, None, None, False, False, False)
        if entry_id != self.entry.entry_id or cover != self.cover:
            return
        self._target = target  # type: ignore[assignment]
        self._reason = (reason or IDLE_REASON)  # type: ignore[arg-type]
        self._manual_until = self._normalize_dt(manual_until)  # type: ignore[arg-type]
        self._next_open = self._normalize_dt(next_open)  # type: ignore[arg-type]
        self._next_close = self._normalize_dt(next_close)  # type: ignore[arg-type]
        self._current_position = current_position  # type: ignore[assignment]
        self._shading_enabled = bool(shading_enabled)
        self._shading_active = bool(shading_active)
        self._ventilation_active = bool(ventilation)
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

class ShutterReasonSensor(ShutterBaseSensor):
    """Expose the last automation reason."""

    _attr_icon = "mdi:information"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "reason", "reason")

    @property
    def native_value(self) -> str | None:
        code = self._reason or IDLE_REASON
        return REASON_LABELS.get(code, code)

class ShutterShadingActiveSensor(ShutterBaseSensor):
    """Expose whether shading mode is active."""

    _attr_icon = "mdi:sunglasses"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "shading", "shading_active")

    @property
    def native_value(self) -> bool:
        return bool(self._shading_active)

    @property
    def available(self) -> bool:
        return True


class ShutterVentilationSensor(ShutterBaseSensor):
    """Expose whether ventilation mode is active."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, entry: ConfigEntry, cover: str) -> None:
        super().__init__(entry, cover, "ventilation", "ventilation")

    @property
    def native_value(self) -> bool:
        return bool(self._ventilation_active)
