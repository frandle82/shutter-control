"""Config and options flow for Shutter Control."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_COLD,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_AUTO_WIND,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_NAME,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_RESIDENT_SENSOR,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_POSITION,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_TEMPERATURE_THRESHOLD,
    CONF_TIME_DOWN_NON_WORKDAY,
    CONF_TIME_DOWN_WORKDAY,
    CONF_TIME_UP_NON_WORKDAY,
    CONF_TIME_UP_WORKDAY,
    CONF_VENTILATE_POSITION,
    CONF_WIND_LIMIT,
    CONF_WIND_SENSOR,
    CONF_WINDOW_SENSORS,
    CONF_WORKDAY_SENSOR,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_NAME,
    DEFAULT_OPEN_POSITION,
    DEFAULT_SHADING_AZIMUTH_END,
    DEFAULT_SHADING_AZIMUTH_START,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN,
    DEFAULT_SHADING_POSITION,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    DEFAULT_TEMPERATURE_THRESHOLD,
    DEFAULT_COLD_PROTECTION_THRESHOLD,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_WIND_LIMIT,
    DEFAULT_TIME_DOWN_NON_WORKDAY,
    DEFAULT_TIME_DOWN_WORKDAY,
    DEFAULT_TIME_UP_NON_WORKDAY,
    DEFAULT_TIME_UP_WORKDAY,
    DOMAIN,
)
from .const import DEFAULT_CLOSE_POSITION  # separate import for line length


class ShutterControlFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_windows()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                }
            ),
        )

    async def async_step_windows(self, user_input=None) -> FlowResult:
        covers: list[str] = self._data.get(CONF_COVERS, [])
        if user_input is not None:
            mapping: dict[str, list[str]] = {}
            for cover in covers:
                key = self._cover_key(cover)
                mapping[cover] = user_input.get(key, [])
            self._data[CONF_WINDOW_SENSORS] = mapping
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="windows",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        self._cover_key(cover),
                        default=self._existing_windows_for_cover(cover),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor"], multiple=True)
                    )
                    for cover in covers
                }
            ),
        )

    async def async_step_schedule(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_shading()

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPEN_POSITION, default=DEFAULT_OPEN_POSITION): int,
                    vol.Required(CONF_CLOSE_POSITION, default=DEFAULT_CLOSE_POSITION): int,
                    vol.Required(CONF_VENTILATE_POSITION, default=DEFAULT_VENTILATE_POSITION): int,
                    vol.Required(CONF_SHADING_POSITION, default=DEFAULT_SHADING_POSITION): int,
                    vol.Required(CONF_POSITION_TOLERANCE, default=DEFAULT_TOLERANCE): int,
                    vol.Required(CONF_TIME_UP_WORKDAY, default=DEFAULT_TIME_UP_WORKDAY): selector.TimeSelector(),
                    vol.Required(CONF_TIME_DOWN_WORKDAY, default=DEFAULT_TIME_DOWN_WORKDAY): selector.TimeSelector(),
                    vol.Required(CONF_TIME_DOWN_NON_WORKDAY, default=DEFAULT_TIME_DOWN_NON_WORKDAY): selector.TimeSelector(),
                    ol.Required(CONF_TIME_UP_NON_WORKDAY, default=DEFAULT_TIME_UP_NON_WORKDAY): selector.TimeSelector(),
                    vol.Optional(CONF_WORKDAY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                    ),
                    vol.Optional(CONF_RESIDENT_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "switch"])
                    ),
                }
            ),
        )

    async def async_step_shading(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_finalize()

        return self.async_show_form(
            step_id="shading",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BRIGHTNESS_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(CONF_BRIGHTNESS_OPEN_ABOVE, default=DEFAULT_BRIGHTNESS_OPEN): vol.Coerce(float),
                    vol.Optional(CONF_BRIGHTNESS_CLOSE_BELOW, default=DEFAULT_BRIGHTNESS_CLOSE): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_OPEN, default=DEFAULT_SUN_ELEVATION_OPEN): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_CLOSE, default=DEFAULT_SUN_ELEVATION_CLOSE): vol.Coerce(float),
                    vol.Optional(CONF_SUN_AZIMUTH_START, default=DEFAULT_SHADING_AZIMUTH_START): vol.Coerce(float),
                    vol.Optional(CONF_SUN_AZIMUTH_END, default=DEFAULT_SHADING_AZIMUTH_END): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_MIN, default=DEFAULT_SHADING_ELEVATION_MIN): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_MAX, default=DEFAULT_SHADING_ELEVATION_MAX): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_BRIGHTNESS_START, default=DEFAULT_SHADING_BRIGHTNESS_START): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_BRIGHTNESS_END, default=DEFAULT_SHADING_BRIGHTNESS_END): vol.Coerce(float),
                    vol.Optional(CONF_TEMPERATURE_SENSOR_INDOOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(CONF_TEMPERATURE_SENSOR_OUTDOOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE_THRESHOLD, default=DEFAULT_TEMPERATURE_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_TEMPERATURE_FORECAST_THRESHOLD, default=DEFAULT_TEMPERATURE_FORECAST_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_COLD_PROTECTION_THRESHOLD, default=DEFAULT_COLD_PROTECTION_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(CONF_COLD_PROTECTION_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(CONF_WIND_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(CONF_WIND_LIMIT, default=DEFAULT_WIND_LIMIT): vol.Coerce(float),
                    vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES, default=DEFAULT_MANUAL_OVERRIDE_MINUTES): vol.Coerce(int),
                    vol.Required(CONF_AUTO_UP, default=True): bool,
                    vol.Required(CONF_AUTO_DOWN, default=True): bool,
                    vol.Required(CONF_AUTO_BRIGHTNESS, default=True): bool,
                    vol.Required(CONF_AUTO_SUN, default=True): bool,
                    vol.Required(CONF_AUTO_VENTILATE, default=True): bool,
                    vol.Required(CONF_AUTO_COLD, default=False): bool,
                    vol.Required(CONF_AUTO_SHADING, default=True): bool,
                    vol.Required(CONF_AUTO_WIND, default=True): bool,
                }
            ),
        )

    async def async_step_finalize(self, user_input=None) -> FlowResult:
        if user_input:
            self._data.update(user_input)
        name = self._data.get(CONF_NAME, DEFAULT_NAME).strip() or DEFAULT_NAME
        return self.async_create_entry(title=name, data=self._data)

    def _cover_key(self, cover: str) -> str:
        state = self.hass.states.get(cover)
        friendly_name = state.name if state else cover.split(".")[-1]
        return f"Fenster-/Türkontakt für {friendly_name}"

    def _existing_windows_for_cover(self, cover: str) -> list[str]:
        mapping = self._data.get(CONF_WINDOW_SENSORS) or {}
        return mapping.get(cover, [])

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return ShutterOptionsFlow(config_entry)


class ShutterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._options = dict(config_entry.data | config_entry.options)

    def _time_default(self, key: str, legacy: tuple[str, ...], fallback: str) -> str:
        if key in self._options:
            return self._options.get(key, fallback)
        for legacy_key in legacy:
            if legacy_key in self._options:
                return self._options.get(legacy_key, fallback)
        return fallback

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            name = user_input.pop(CONF_NAME, self.config_entry.title).strip() or DEFAULT_NAME
            mapping: dict[str, list[str]] = {}
            for cover in self._options.get(CONF_COVERS, []):
                mapping[cover] = user_input.get(self._cover_key(cover), self._existing_windows_for_cover(cover))
            user_input[CONF_WINDOW_SENSORS] = mapping
            self._options.update({CONF_NAME: name} | user_input)
            await self.hass.config_entries.async_update_entry(self.config_entry, title=name)
            return self.async_create_entry(title="", data=self._options)

        auto_brightness = bool(self._options.get(CONF_AUTO_BRIGHTNESS, True))
        auto_sun = bool(self._options.get(CONF_AUTO_SUN, True))
        auto_ventilate = bool(self._options.get(CONF_AUTO_VENTILATE, True))
        auto_cold = bool(self._options.get(CONF_AUTO_COLD, False))
        auto_shading = bool(self._options.get(CONF_AUTO_SHADING, True))
        auto_wind = bool(self._options.get(CONF_AUTO_WIND, True))

        schema: dict = {
            vol.Optional(CONF_NAME, default=self._options.get(CONF_NAME, self.config_entry.title or DEFAULT_NAME)): str,
            vol.Required(CONF_COVERS, default=self._options.get(CONF_COVERS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["cover"], multiple=True)
            ),
            vol.Required(CONF_OPEN_POSITION, default=self._options.get(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)): int,
            vol.Required(CONF_CLOSE_POSITION, default=self._options.get(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)): int,
            vol.Required(
                CONF_VENTILATE_POSITION, default=self._options.get(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION)
            ): int,
            vol.Required(CONF_SHADING_POSITION, default=self._options.get(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION)): int,
            vol.Required(
                CONF_POSITION_TOLERANCE,
                default=self._options.get(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE),
            ): int,
            vol.Optional(CONF_WIND_SENSOR, default=self._options.get(CONF_WIND_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"])
            ),
            vol.Optional(
                CONF_WIND_LIMIT,
                default=self._options.get(CONF_WIND_LIMIT, DEFAULT_WIND_LIMIT),
            ): vol.Coerce(float),
            vol.Optional(CONF_RESIDENT_SENSOR, default=self._options.get(CONF_RESIDENT_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "switch"])
            ),
            vol.Optional(
                CONF_TIME_UP_WORKDAY,
                default=self._options.get(CONF_TIME_UP_WORKDAY, DEFAULT_TIME_UP_WORKDAY),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_UP_NON_WORKDAY,
                default=self._options.get(CONF_TIME_UP_NON_WORKDAY, DEFAULT_TIME_UP_NON_WORKDAY),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_DOWN_WORKDAY,
                default=self._options.get(CONF_TIME_DOWN_WORKDAY, DEFAULT_TIME_DOWN_WORKDAY),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_DOWN_NON_WORKDAY,
                default=self._options.get(CONF_TIME_DOWN_NON_WORKDAY, DEFAULT_TIME_DOWN_NON_WORKDAY),
            ): selector.TimeSelector(),
            vol.Optional(CONF_WORKDAY_SENSOR, default=self._options.get(CONF_WORKDAY_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
            ),
            vol.Required(CONF_AUTO_UP, default=self._options.get(CONF_AUTO_UP, True)): bool,
            vol.Required(CONF_AUTO_DOWN, default=self._options.get(CONF_AUTO_DOWN, True)): bool,
            vol.Required(CONF_AUTO_BRIGHTNESS, default=self._options.get(CONF_AUTO_BRIGHTNESS, True)): bool,
            vol.Required(CONF_AUTO_SUN, default=self._options.get(CONF_AUTO_SUN, True)): bool,
            vol.Required(CONF_AUTO_VENTILATE, default=self._options.get(CONF_AUTO_VENTILATE, True)): bool,
            vol.Required(CONF_AUTO_COLD, default=self._options.get(CONF_AUTO_COLD, False)): bool,
            vol.Required(CONF_AUTO_SHADING, default=self._options.get(CONF_AUTO_SHADING, True)): bool,
            vol.Required(CONF_AUTO_WIND, default=auto_wind): bool,
            vol.Optional(
                CONF_MANUAL_OVERRIDE_MINUTES,
                default=self._options.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES),
            ): vol.Coerce(int),
        }

        if auto_brightness:
            schema.update(
                {
                    vol.Optional(CONF_BRIGHTNESS_SENSOR, default=self._options.get(CONF_BRIGHTNESS_SENSOR)): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(
                        CONF_BRIGHTNESS_OPEN_ABOVE,
                        default=self._options.get(CONF_BRIGHTNESS_OPEN_ABOVE, DEFAULT_BRIGHTNESS_OPEN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_BRIGHTNESS_CLOSE_BELOW,
                        default=self._options.get(CONF_BRIGHTNESS_CLOSE_BELOW, DEFAULT_BRIGHTNESS_CLOSE),
                    ): vol.Coerce(float),
                }
            )

        if auto_sun:
            schema.update(
                {
                    vol.Optional(
                        CONF_SUN_ELEVATION_OPEN,
                        default=self._options.get(CONF_SUN_ELEVATION_OPEN, DEFAULT_SUN_ELEVATION_OPEN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_ELEVATION_CLOSE,
                        default=self._options.get(CONF_SUN_ELEVATION_CLOSE, DEFAULT_SUN_ELEVATION_CLOSE),
                    ): vol.Coerce(float),
                }
            )

        if auto_shading:
            schema.update(
                {
                    vol.Optional(
                        CONF_SUN_AZIMUTH_START,
                        default=self._options.get(CONF_SUN_AZIMUTH_START, DEFAULT_SHADING_AZIMUTH_START),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_AZIMUTH_END,
                        default=self._options.get(CONF_SUN_AZIMUTH_END, DEFAULT_SHADING_AZIMUTH_END),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_ELEVATION_MIN,
                        default=self._options.get(CONF_SUN_ELEVATION_MIN, DEFAULT_SHADING_ELEVATION_MIN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_ELEVATION_MAX,
                        default=self._options.get(CONF_SUN_ELEVATION_MAX, DEFAULT_SHADING_ELEVATION_MAX),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_BRIGHTNESS_START,
                        default=self._options.get(CONF_SHADING_BRIGHTNESS_START, DEFAULT_SHADING_BRIGHTNESS_START),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_BRIGHTNESS_END,
                        default=self._options.get(CONF_SHADING_BRIGHTNESS_END, DEFAULT_SHADING_BRIGHTNESS_END),
                    ): vol.Coerce(float),
                }
            )

        if auto_cold:
            schema.update(
                {
                    vol.Optional(
                        CONF_TEMPERATURE_SENSOR_INDOOR,
                        default=self._options.get(CONF_TEMPERATURE_SENSOR_INDOOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE_SENSOR_OUTDOOR,
                        default=self._options.get(CONF_TEMPERATURE_SENSOR_OUTDOOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE_THRESHOLD,
                        default=self._options.get(CONF_TEMPERATURE_THRESHOLD, DEFAULT_TEMPERATURE_THRESHOLD),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_TEMPERATURE_FORECAST_THRESHOLD,
                        default=self._options.get(CONF_TEMPERATURE_FORECAST_THRESHOLD, DEFAULT_TEMPERATURE_FORECAST_THRESHOLD),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_COLD_PROTECTION_THRESHOLD,
                        default=self._options.get(CONF_COLD_PROTECTION_THRESHOLD, DEFAULT_COLD_PROTECTION_THRESHOLD),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_COLD_PROTECTION_FORECAST_SENSOR,
                        default=self._options.get(CONF_COLD_PROTECTION_FORECAST_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                }
            )

        if auto_ventilate:
            schema.update(
                {
                    **{
                        vol.Optional(
                            self._cover_key(cover),
                            default=self._existing_windows_for_cover(cover),
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain=["binary_sensor"], multiple=True)
                        )
                        for cover in self._options.get(CONF_COVERS, [])
                    },
                }
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))

    def _cover_key(self, cover: str) -> str:
        return f"windows_{slugify(cover)}"

    def _existing_windows_for_cover(self, cover: str) -> list[str]:
        mapping = self._options.get(CONF_WINDOW_SENSORS) or {}
        return mapping.get(cover, [])
