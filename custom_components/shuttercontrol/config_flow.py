"""Config and options flow for Shutter Control."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.util import slugify
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_COLD,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_POSITION_TOLERANCE,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_COVERS,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
    CONF_MANUAL_OVERRIDE_RESET_MODE,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
    CONF_NAME,
    CONF_RESIDENT_SENSOR,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
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
    CONF_WINDOW_SENSORS,
    CONF_WORKDAY_SENSOR,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_TOLERANCE,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_NAME,
    DEFAULT_SHADING_AZIMUTH_END,
    DEFAULT_SHADING_AZIMUTH_START,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    DEFAULT_TEMPERATURE_THRESHOLD,
    DEFAULT_COLD_PROTECTION_THRESHOLD,
    DEFAULT_AUTOMATION_FLAGS,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
    DOMAIN,
)


def _with_automation_defaults(config: dict) -> dict:
    """Ensure automation toggles fall back to default values."""

    return {
        **DEFAULT_AUTOMATION_FLAGS,
        **DEFAULT_MANUAL_OVERRIDE_FLAGS,
        **config,
    }


LOGGER = logging.getLogger(__name__)


def _time_default(value, fallback: str | None = None):
    """Return a time object for selectors, falling back safely."""

    for candidate in (value, fallback):
        if candidate in (None, "", vol.UNDEFINED):
            continue
        parsed = dt_util.parse_time(str(candidate))
        if parsed:
            return parsed
    return vol.UNDEFINED


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
                        selector.EntitySelectorConfig(domain=["binary_sensor"],device_class=["window"], multiple=True)
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
                    vol.Optional(CONF_WORKDAY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                    ),
                    vol.Optional(CONF_RESIDENT_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "switch"])
                    ),
                    vol.Optional(CONF_BRIGHTNESS_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"],device_class=["illuminance"])
                    ),
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
                    vol.Optional(CONF_SHADING_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(
                        CONF_SHADING_FORECAST_TYPE,
                        default=DEFAULT_SHADING_FORECAST_TYPE,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "daily", "label": "Use the daily weather forecast service"},
                                {"value": "hourly", "label": "Use the hourly weather forecast service"},
                                {
                                    "value": "weather_attributes",
                                    "label": "Do not use a weather forecast, but the current weather attributes",
                                },
                            ]
                        )
                    ),
                    vol.Optional(CONF_SHADING_WEATHER_CONDITIONS, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "clear-night",
                                "cloudy",
                                "exceptional",
                                "fog",
                                "hail",
                                "lightning",
                                "lightning-rainy",
                                "partlycloudy",
                                "pouring",
                                "rainy",
                                "snowy",
                                "snowy-rainy",
                                "sunny",
                                "windy",
                                "windy-variant",
                            ],
                            multiple=True,
                        )
                    ),
                    vol.Optional(CONF_MANUAL_OVERRIDE_RESET_MODE, default=self._data.get(CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT)): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": MANUAL_OVERRIDE_RESET_NONE, "label": "No timed reset"},
                                {"value": MANUAL_OVERRIDE_RESET_TIME, "label": "Reset at specific time"},
                                {"value": MANUAL_OVERRIDE_RESET_TIMEOUT, "label": "Reset after timeout (minutes)"},
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_MANUAL_OVERRIDE_RESET_TIME,
                        default=_time_default(
                            self._data.get(
                                CONF_MANUAL_OVERRIDE_RESET_TIME,
                                DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                            ),
                            DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES, default=self._data.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)): vol.Coerce(int),
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_OPEN, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_OPEN, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_OPEN])): bool,
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_CLOSE, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_CLOSE, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_CLOSE])): bool,
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE])): bool,
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_SHADING, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_SHADING, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_SHADING])): bool,
                }
            ),
        )

    async def async_step_finalize(self, user_input=None) -> FlowResult:
        if user_input:
            self._data.update(user_input)
        name = self._data.get(CONF_NAME, DEFAULT_NAME).strip() or DEFAULT_NAME
        data = _with_automation_defaults(self._data)
        return self.async_create_entry(title=name, data=data)

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
        self._config_entry = config_entry
        self._options = self._normalize_options(config_entry)

    def _clean_user_input(self, user_input: dict) -> dict:
        """Drop empty selector values while keeping valid falsy values."""
        return {
            key: value
            for key, value in user_input.items()
            if value is not None and value != "" and value is not vol.UNDEFINED
        }

    def _optional_default(self, key: str):
        """Return a safe default for optional selectors."""

        if key in self._options:
            value = self._options.get(key)
            if value not in (None, ""):
                return value
        return vol.UNDEFINED

    def _sanitize_options(self, options: dict) -> dict:
        """Remove empty selector placeholders from stored options."""

        return {
            key: value
            for key, value in options.items()
            if value not in (None, "", vol.UNDEFINED)
        }

    def _normalize_options(
        self, config_entry: config_entries.ConfigEntry | None, overrides: dict | None = None
    ) -> dict:
        """Merge stored data/options with defaults, overrides, and sanitize them."""


        merged: dict = {}
        if config_entry:
            merged.update(dict(config_entry.data or {}))
            merged.update(dict(config_entry.options or {}))

        merged = _with_automation_defaults(merged)
        if overrides:
            merged.update(overrides)
        sanitized = self._sanitize_options(merged)

        covers = sanitized.get(CONF_COVERS, [])
        if not isinstance(covers, list):
            covers = list(covers) if covers else []
        sanitized[CONF_COVERS] = covers

        windows = sanitized.get(CONF_WINDOW_SENSORS, {})
        if not isinstance(windows, dict):
            windows = {}
        sanitized[CONF_WINDOW_SENSORS] = {
            cover: sensors if isinstance(sensors, list) else []
            for cover, sensors in windows.items()
            if cover
        }

        return sanitized

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            clean_input = self._clean_user_input(user_input)

            name = clean_input.pop(CONF_NAME, self._config_entry.title).strip() or DEFAULT_NAME
            covers = clean_input.get(CONF_COVERS, self._options.get(CONF_COVERS, []))
            mapping: dict[str, list[str]] = {}
            for cover in covers:
                mapping[cover] = clean_input.get(
                    self._cover_key(cover), self._existing_windows_for_cover(cover)
                )
            clean_input[CONF_WINDOW_SENSORS] = mapping
            overrides = {CONF_NAME: name} | clean_input
            try:
                self._options = self._normalize_options(self._config_entry, overrides)
            except Exception:  # pragma: no cover - defensive fallback for HA runtime
                _LOGGER.exception("Failed to normalize shutter control options")
                merged = {
                    **(self._config_entry.data or {}),
                    **(self._config_entry.options or {}),
                    **overrides,
                }
                self._options = self._sanitize_options(
                    _with_automation_defaults(merged)
                )
            self.hass.config_entries.async_update_entry(self._config_entry, title=name)
            return self.async_create_entry(title="", data=self._options)

        auto_brightness = bool(self._options.get(CONF_AUTO_BRIGHTNESS, True))
        auto_sun = bool(self._options.get(CONF_AUTO_SUN, True))
        auto_ventilate = bool(self._options.get(CONF_AUTO_VENTILATE, True))
        auto_cold = bool(self._options.get(CONF_AUTO_COLD, False))
        auto_shading = bool(self._options.get(CONF_AUTO_SHADING, True))

        schema: dict = {
            vol.Optional(CONF_NAME, default=self._options.get(CONF_NAME, self._config_entry.title or DEFAULT_NAME)): str,
            vol.Required(CONF_COVERS, default=self._options.get(CONF_COVERS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["cover"], multiple=True)
            ),
            vol.Optional(
                CONF_POSITION_TOLERANCE,
                default=self._options.get(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE),
            ): vol.Coerce(float),
        }
        if auto_ventilate:
            schema.update(
                {
                    **{
                        vol.Optional(self._cover_key(cover), default=self._existing_windows_for_cover(cover),
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain=["binary_sensor"], multiple=True)
                        )
                            for cover in self._options.get(CONF_COVERS, [])
                    },
                }
            )
        schema.update(
            {
                vol.Optional(
                    CONF_RESIDENT_SENSOR, default=self._optional_default(CONF_RESIDENT_SENSOR)
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "switch"])
                ),
                vol.Optional(
                    CONF_WORKDAY_SENSOR, default=self._optional_default(CONF_WORKDAY_SENSOR)
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                ),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_RESET_MODE,
                    default=self._options.get(CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": MANUAL_OVERRIDE_RESET_NONE, "label": "No timed reset"},
                            {"value": MANUAL_OVERRIDE_RESET_TIME, "label": "Reset at specific time"},
                            {"value": MANUAL_OVERRIDE_RESET_TIMEOUT, "label": "Reset after timeout (minutes)"},
                        ]
                    )
                ),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_RESET_TIME,
                    default=_time_default(
                        self._options.get(
                            CONF_MANUAL_OVERRIDE_RESET_TIME,
                            DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                        ),
                        DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                    ),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_MINUTES,
                    default=self._options.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_OPEN],
                    ),
                ): bool,
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_CLOSE],
                    ),
                ): bool,
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE],
                    ),
                ): bool,
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_SHADING],
                    ),
                ): bool,
            }
        )

        if auto_brightness:
            schema.update(
                {
                    vol.Optional(
                        CONF_BRIGHTNESS_SENSOR,
                        default=self._optional_default(CONF_BRIGHTNESS_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"],device_class=["illuminance"])
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
                    vol.Optional(
                        CONF_SHADING_FORECAST_SENSOR,
                        default=self._optional_default(CONF_SHADING_FORECAST_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(
                        CONF_SHADING_FORECAST_TYPE,
                        default=self._options.get(
                            CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "daily", "label": "Use the daily weather forecast service"},
                                {"value": "hourly", "label": "Use the hourly weather forecast service"},
                                {
                                    "value": "weather_attributes",
                                    "label": "Do not use a weather forecast, but the current weather attributes",
                                },
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_SHADING_WEATHER_CONDITIONS,
                        default=self._options.get(CONF_SHADING_WEATHER_CONDITIONS, []),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "clear-night",
                                "clear",
                                "cloudy",
                                "fog",
                                "hail",
                                "lightning",
                                "lightning-rainy",
                                "partlycloudy",
                                "pouring",
                                "rainy",
                                "snowy",
                                "snowy-rainy",
                                "sunny",
                                "windy",
                                "windy-variant",
                                "exceptional",
                            ],
                            multiple=True,
                        )
                    ),
                }
            )

        if auto_cold:
            schema.update(
                {
                    vol.Optional(
                        CONF_TEMPERATURE_SENSOR_INDOOR,
                        default=self._optional_default(CONF_TEMPERATURE_SENSOR_INDOOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE_SENSOR_OUTDOOR,
                        default=self._optional_default(CONF_TEMPERATURE_SENSOR_OUTDOOR),
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
                        default=self._optional_default(CONF_COLD_PROTECTION_FORECAST_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                }
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))

    def _cover_key(self, cover: str) -> str:
        return f"windows_{slugify(cover)}"

    def _existing_windows_for_cover(self, cover: str) -> list[str]:
        mapping = self._options.get(CONF_WINDOW_SENSORS) or {}
        return mapping.get(cover, [])
