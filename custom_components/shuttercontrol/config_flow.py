"""Config flow for the Shutter Control integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_ROOM,
    CONF_MANUAL_OVERRIDE,
    CONF_OPEN_POSITION,
    CONF_PRESENCE_ENTITY,
    CONF_SUNRISE_OFFSET,
    CONF_SUNSET_OFFSET,
    CONF_WEATHER_ENTITY,
    CONF_WIND_SPEED_LIMIT,
    CONF_WINDOW_SENSORS,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_OPEN_POSITION,
    DEFAULT_SUNRISE_OFFSET,
    DEFAULT_SUNSET_OFFSET,
    DEFAULT_WIND_SPEED_LIMIT,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPEN_POSITION, default=DEFAULT_OPEN_POSITION): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Required(CONF_CLOSE_POSITION, default=DEFAULT_CLOSE_POSITION): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional(CONF_SUNRISE_OFFSET, default=DEFAULT_SUNRISE_OFFSET): vol.Coerce(int),
        vol.Optional(CONF_SUNSET_OFFSET, default=DEFAULT_SUNSET_OFFSET): vol.Coerce(int),
        vol.Optional(CONF_PRESENCE_ENTITY): selector({
            "entity": {
                "domain": [
                    "binary_sensor",
                    "device_tracker",
                    "person",
                    "sensor",
                ]
            }
        }),
        vol.Optional(CONF_WEATHER_ENTITY): selector({"entity": {"domain": "weather"}}),
        vol.Optional(CONF_WIND_SPEED_LIMIT, default=DEFAULT_WIND_SPEED_LIMIT): vol.Coerce(
            float
        ),
        vol.Optional(CONF_MANUAL_OVERRIDE, default=False): bool,
    }
)


class ShutterControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shutter Control."""

    VERSION = 1

    def __init__(self) -> None:
        self._covers: list[dict[str, Any]] = []
        self._base_options: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial configuration step."""

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        self._base_options = user_input
        return await self.async_step_covers()

    async def async_step_covers(self, user_input: dict[str, Any] | None = None):
        """Collect per-cover configuration values."""

        cover_defaults = {
            CONF_OPEN_POSITION: self._base_options.get(
                CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION
            ),
            CONF_CLOSE_POSITION: self._base_options.get(
                CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
            ),
            CONF_SUNRISE_OFFSET: self._base_options.get(
                CONF_SUNRISE_OFFSET, DEFAULT_SUNRISE_OFFSET
            ),
            CONF_SUNSET_OFFSET: self._base_options.get(
                CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET
            ),
        }

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_COVERS, default=[]): vol.All(
                    vol.Length(min=1),
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_ROOM): str,
                                vol.Required(ATTR_ENTITY_ID): selector(
                                    {"entity": {"domain": "cover"}}
                                ),
                                vol.Optional(CONF_NAME): str,
                                vol.Optional(
                                    CONF_OPEN_POSITION,
                                    default=cover_defaults[CONF_OPEN_POSITION],
                                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                                vol.Optional(
                                    CONF_CLOSE_POSITION,
                                    default=cover_defaults[CONF_CLOSE_POSITION],
                                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                                vol.Optional(
                                    CONF_SUNRISE_OFFSET,
                                    default=cover_defaults[CONF_SUNRISE_OFFSET],
                                ): vol.Coerce(int),
                                vol.Optional(
                                    CONF_SUNSET_OFFSET,
                                    default=cover_defaults[CONF_SUNSET_OFFSET],
                                ): vol.Coerce(int),
                                vol.Optional(CONF_WINDOW_SENSORS, default=[]): selector(
                                    {
                                        "entity": {
                                            "domain": "binary_sensor",
                                            "device_class": [
                                                "window",
                                                "door",
                                                "opening",
                                            ],
                                            "multiple": True,
                                        }
                                    }
                                ),
                            }
                        )
                    ],
                )
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="covers", data_schema=options_schema)

        self._covers = user_input.get(CONF_COVERS, [])
        if not self._covers:
            errors = {CONF_COVERS: "no_covers"}
            return self.async_show_form(
                step_id="covers", data_schema=options_schema, errors=errors
            )

        return await self._async_create_entry()

    async def _async_create_entry(self):
        """Register the config entry."""

        data = {
            **self._base_options,
            CONF_COVERS: self._covers,
        }

        return self.async_create_entry(title="Shutter Control", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ShutterControlOptionsFlow(config_entry)


class ShutterControlOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Shutter Control options."""

        current_covers = self.config_entry.options.get(
            CONF_COVERS, self.config_entry.data.get(CONF_COVERS, [])
        )

        for cover in current_covers:
            cover.setdefault(CONF_ROOM, "")
            cover.setdefault(CONF_WINDOW_SENSORS, [])

        base_defaults = {
            CONF_OPEN_POSITION: self.config_entry.options.get(
                CONF_OPEN_POSITION,
                self.config_entry.data.get(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
            ),
            CONF_CLOSE_POSITION: self.config_entry.options.get(
                CONF_CLOSE_POSITION,
                self.config_entry.data.get(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
            ),
            CONF_SUNRISE_OFFSET: self.config_entry.options.get(
                CONF_SUNRISE_OFFSET,
                self.config_entry.data.get(CONF_SUNRISE_OFFSET, DEFAULT_SUNRISE_OFFSET),
            ),
            CONF_SUNSET_OFFSET: self.config_entry.options.get(
                CONF_SUNSET_OFFSET,
                self.config_entry.data.get(CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET),
            ),
            CONF_PRESENCE_ENTITY: self.config_entry.options.get(
                CONF_PRESENCE_ENTITY, self.config_entry.data.get(CONF_PRESENCE_ENTITY)
            ),
            CONF_WEATHER_ENTITY: self.config_entry.options.get(
                CONF_WEATHER_ENTITY, self.config_entry.data.get(CONF_WEATHER_ENTITY)
            ),
            CONF_WIND_SPEED_LIMIT: self.config_entry.options.get(
                CONF_WIND_SPEED_LIMIT,
                self.config_entry.data.get(CONF_WIND_SPEED_LIMIT, DEFAULT_WIND_SPEED_LIMIT),
            ),
            CONF_MANUAL_OVERRIDE: self.config_entry.options.get(
                CONF_MANUAL_OVERRIDE, self.config_entry.data.get(CONF_MANUAL_OVERRIDE, False)
            ),
        }

        schema = vol.Schema(
            {
                vol.Optional(CONF_OPEN_POSITION, default=base_defaults[CONF_OPEN_POSITION]): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
                vol.Optional(CONF_CLOSE_POSITION, default=base_defaults[CONF_CLOSE_POSITION]): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
                vol.Optional(CONF_SUNRISE_OFFSET, default=base_defaults[CONF_SUNRISE_OFFSET]): vol.Coerce(
                    int
                ),
                vol.Optional(CONF_SUNSET_OFFSET, default=base_defaults[CONF_SUNSET_OFFSET]): vol.Coerce(
                    int
                ),
                vol.Optional(
                    CONF_PRESENCE_ENTITY, default=base_defaults[CONF_PRESENCE_ENTITY]
                ): selector(
                    {
                        "entity": {
                            "domain": [
                                "binary_sensor",
                                "device_tracker",
                                "person",
                                "sensor",
                            ]
                        }
                    }
                ),
                vol.Optional(CONF_WEATHER_ENTITY, default=base_defaults[CONF_WEATHER_ENTITY]): selector(
                    {"entity": {"domain": "weather"}}
                ),
                vol.Optional(
                    CONF_WIND_SPEED_LIMIT,
                    default=base_defaults[CONF_WIND_SPEED_LIMIT],
                ): vol.Coerce(float),
                vol.Optional(CONF_MANUAL_OVERRIDE, default=base_defaults[CONF_MANUAL_OVERRIDE]): bool,
                vol.Optional(CONF_COVERS, default=current_covers): vol.All(
                    vol.Length(min=1),
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_ROOM, default=""): str,
                                vol.Required(ATTR_ENTITY_ID): selector(
                                    {"entity": {"domain": "cover"}}
                                ),
                                vol.Optional(CONF_NAME): str,
                                vol.Optional(
                                    CONF_OPEN_POSITION,
                                    default=base_defaults[CONF_OPEN_POSITION],
                                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                                vol.Optional(
                                    CONF_CLOSE_POSITION,
                                    default=base_defaults[CONF_CLOSE_POSITION],
                                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                                vol.Optional(
                                    CONF_SUNRISE_OFFSET,
                                    default=base_defaults[CONF_SUNRISE_OFFSET],
                                ): vol.Coerce(int),
                                vol.Optional(
                                    CONF_SUNSET_OFFSET,
                                    default=base_defaults[CONF_SUNSET_OFFSET],
                                ): vol.Coerce(int),
                                vol.Optional(CONF_WINDOW_SENSORS, default=[]): selector(
                                    {
                                        "entity": {
                                            "domain": "binary_sensor",
                                            "device_class": [
                                                "window",
                                                "door",
                                                "opening",
                                            ],
                                            "multiple": True,
                                        }
                                    }
                                ),
                            }
                        )
                    ],
                ),
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)

        return self.async_create_entry(title="Shutter Control", data=user_input)


