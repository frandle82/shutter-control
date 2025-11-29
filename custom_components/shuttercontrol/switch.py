"""Switch entities to control automation toggles."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_EXPOSE_SWITCH_SETTINGS,
    CONF_CLOSE_POSITION,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
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
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_VENTILATE_POSITION,
    CONF_BRIGHTNESS_SENSOR,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_NAME,
    DEFAULT_AUTOMATION_FLAGS,
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
)

TOGGLE_ICONS: dict[str, str] = {
    CONF_AUTO_UP: "mdi:arrow-up-bold-circle",
    CONF_AUTO_DOWN: "mdi:arrow-down-bold-circle",
    CONF_AUTO_BRIGHTNESS: "mdi:brightness-auto",
    CONF_AUTO_SUN: "mdi:weather-sunny",
    CONF_AUTO_VENTILATE: "mdi:fan-auto",
    CONF_AUTO_SHADING: "mdi:theme-light-dark",
}

SWITCH_SETTINGS: dict[str, set[str]] = {
    CONF_AUTO_UP: {
        CONF_TIME_UP_EARLY_WORKDAY,
        CONF_TIME_UP_LATE_WORKDAY,
        CONF_TIME_DOWN_EARLY_WORKDAY,
        CONF_TIME_DOWN_LATE_WORKDAY,
        CONF_TIME_UP_EARLY_NON_WORKDAY,
        CONF_TIME_UP_LATE_NON_WORKDAY,
        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
        CONF_TIME_DOWN_LATE_NON_WORKDAY,
    },
    CONF_AUTO_DOWN: {
        CONF_TIME_UP_EARLY_WORKDAY,
        CONF_TIME_UP_LATE_WORKDAY,
        CONF_TIME_DOWN_EARLY_WORKDAY,
        CONF_TIME_DOWN_LATE_WORKDAY,
        CONF_TIME_UP_EARLY_NON_WORKDAY,
        CONF_TIME_UP_LATE_NON_WORKDAY,
        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
        CONF_TIME_DOWN_LATE_NON_WORKDAY,
    },
    CONF_AUTO_VENTILATE: {CONF_VENTILATE_POSITION, CONF_POSITION_TOLERANCE},
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
        CONF_SUN_ELEVATION_MIN,
        CONF_SUN_ELEVATION_MAX,
        CONF_OPEN_POSITION,
        CONF_CLOSE_POSITION,
    },
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register automation toggle switches."""

    def _has_sensor(key: str) -> bool:
        options_and_data = {**entry.data, **entry.options}
        if key == CONF_AUTO_BRIGHTNESS:
            return bool(options_and_data.get(CONF_BRIGHTNESS_SENSOR))
        return True

    entities: list[SwitchEntity] = [
        AutomationToggleSwitch(entry, key, translation_key)
        for key, translation_key in AUTOMATION_TOGGLES
        if _has_sensor(key)
    ]

    async_add_entities(entities)


class AutomationToggleSwitch(SwitchEntity):
    """Switch to enable or disable automation features."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, key: str, translation_key: str) -> None:
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_translation_key = translation_key
        self._attr_icon = TOGGLE_ICONS.get(key)
        self._attr_friendly_name = translation_key

    async def async_added_to_hass(self) -> None:
        """Handle entity addition and keep state in sync with options."""

        self.async_on_remove(
            self.entry.add_update_listener(self._handle_entry_update)
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.options.get(
                CONF_NAME,
                self.entry.data.get(CONF_NAME, self.entry.title or DEFAULT_NAME),
            ),
            manufacturer="CCA-derived",
        )

    @property
    def is_on(self) -> bool:
        value = self.entry.options.get(self._key)
        if value is None:
            value = self.entry.data.get(self._key, DEFAULT_AUTOMATION_FLAGS.get(self._key))
        return bool(value)

    @property
    def extra_state_attributes(self):
        if not self.entry.options.get(CONF_EXPOSE_SWITCH_SETTINGS):
            return None
        allowed = SWITCH_SETTINGS.get(self._key)
        if not allowed:
            return None
        config = {**self.entry.data, **self.entry.options}
        return {key: config.get(key) for key in allowed if key in config}

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: True}
        await self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: False}
        await self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def _handle_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Refresh state when config entry is updated."""

        self.async_write_ha_state()
