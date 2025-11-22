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

SELECT_COVERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COVERS): selector({
            "entity": {"domain": "cover", "multiple": True}
        })
    }
)


def _base_settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_OPEN_POSITION, default=defaults[CONF_OPEN_POSITION]): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required(CONF_CLOSE_POSITION, default=defaults[CONF_CLOSE_POSITION]): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(
                CONF_SUNRISE_OFFSET, default=defaults[CONF_SUNRISE_OFFSET]
            ): vol.Coerce(int),
            vol.Optional(
                CONF_SUNSET_OFFSET, default=defaults[CONF_SUNSET_OFFSET]
            ): vol.Coerce(int),
            vol.Optional(CONF_PRESENCE_ENTITY, default=defaults[CONF_PRESENCE_ENTITY]): selector(
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
            vol.Optional(CONF_WEATHER_ENTITY, default=defaults[CONF_WEATHER_ENTITY]): selector(
                {"entity": {"domain": "weather"}}
            ),
            vol.Optional(
                CONF_WIND_SPEED_LIMIT, default=defaults[CONF_WIND_SPEED_LIMIT]
            ): vol.Coerce(float),
            vol.Optional(CONF_MANUAL_OVERRIDE, default=defaults[CONF_MANUAL_OVERRIDE]): bool,
        }
    )


def _cover_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): selector({"entity": {"domain": "cover"}}),
            vol.Optional(CONF_NAME): str,
            vol.Optional(
                CONF_OPEN_POSITION, default=defaults[CONF_OPEN_POSITION]
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_CLOSE_POSITION, default=defaults[CONF_CLOSE_POSITION]
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_SUNRISE_OFFSET, default=defaults[CONF_SUNRISE_OFFSET]
            ): vol.Coerce(int),
            vol.Optional(
                CONF_SUNSET_OFFSET, default=defaults[CONF_SUNSET_OFFSET]
            ): vol.Coerce(int),
            vol.Optional(CONF_WINDOW_SENSORS, default=[]): selector(
                {
                    "entity": {
                        "domain": "binary_sensor",
                        "device_class": ["window", "door", "opening"],
                        "multiple": True,
                    }
                }
            ),
        }
    )


class ShutterControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shutter Control."""

    VERSION = 1

    def __init__(self) -> None:
        self._selected_covers: list[str] = []
        self._base_options: dict[str, Any] = {}
        self._cover_options: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """First ask for the shutter/blind entities to manage."""

        errors: dict[str, str] = {}
        if user_input is not None:
            covers = user_input.get(CONF_COVERS, [])
            if not covers:
                errors[CONF_COVERS] = "no_covers"
            else:
                self._selected_covers = covers
                return await self.async_step_base_settings()

        return self.async_show_form(
            step_id="user", data_schema=SELECT_COVERS_SCHEMA, errors=errors
        )

    async def async_step_base_settings(
        self, user_input: dict[str, Any] | None = None
    ):
        """Collect base settings mirroring the ioBroker defaults."""

        defaults = {
            CONF_OPEN_POSITION: DEFAULT_OPEN_POSITION,
            CONF_CLOSE_POSITION: DEFAULT_CLOSE_POSITION,
            CONF_SUNRISE_OFFSET: DEFAULT_SUNRISE_OFFSET,
            CONF_SUNSET_OFFSET: DEFAULT_SUNSET_OFFSET,
            CONF_PRESENCE_ENTITY: None,
            CONF_WEATHER_ENTITY: None,
            CONF_WIND_SPEED_LIMIT: DEFAULT_WIND_SPEED_LIMIT,
            CONF_MANUAL_OVERRIDE: False,
        }
        defaults.update(self._base_options)

        if user_input is None:
            return self.async_show_form(
                step_id="base_settings", data_schema=_base_settings_schema(defaults)
            )

        self._base_options = user_input
        return await self.async_step_cover_settings()

    async def async_step_cover_settings(
        self, user_input: dict[str, Any] | None = None
    ):
        """Gather per-cover tuning like positions and window sensors."""

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

        existing = self._cover_options or [
            {
                ATTR_ENTITY_ID: cover,
                CONF_OPEN_POSITION: cover_defaults[CONF_OPEN_POSITION],
                CONF_CLOSE_POSITION: cover_defaults[CONF_CLOSE_POSITION],
                CONF_SUNRISE_OFFSET: cover_defaults[CONF_SUNRISE_OFFSET],
                CONF_SUNSET_OFFSET: cover_defaults[CONF_SUNSET_OFFSET],
                CONF_WINDOW_SENSORS: [],
            }
            for cover in self._selected_covers
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_COVERS, default=existing): vol.All(
                    vol.Length(min=1), [_cover_schema(cover_defaults)]
                )
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="cover_settings", data_schema=schema)

        self._cover_options = user_input[CONF_COVERS]
        return await self._async_create_entry()

    async def _async_create_entry(self):
        data = {
            **self._base_options,
            CONF_COVERS: self._cover_options,
        }
        return self.async_create_entry(title="Shutter Control", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ShutterControlOptionsFlow(config_entry)


class ShutterControlOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing entry via the same wizard."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._base_options: dict[str, Any] = {}
        self._cover_options: list[dict[str, Any]] = []

    async def async_step_init(self, user_input=None):
        """Start by editing the base settings."""

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

        if user_input is None:
            return self.async_show_form(
                step_id="init", data_schema=_base_settings_schema(base_defaults)
            )

        self._base_options = user_input
        return await self.async_step_cover_settings()

    async def async_step_cover_settings(self, user_input=None):
        """Edit per-cover settings on a follow-up page."""

        cover_defaults = {
            CONF_OPEN_POSITION: self._base_options.get(
                CONF_OPEN_POSITION,
                self.config_entry.options.get(
                    CONF_OPEN_POSITION,
                    self.config_entry.data.get(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                ),
            ),
            CONF_CLOSE_POSITION: self._base_options.get(
                CONF_CLOSE_POSITION,
                self.config_entry.options.get(
                    CONF_CLOSE_POSITION,
                    self.config_entry.data.get(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                ),
            ),
            CONF_SUNRISE_OFFSET: self._base_options.get(
                CONF_SUNRISE_OFFSET,
                self.config_entry.options.get(
                    CONF_SUNRISE_OFFSET,
                    self.config_entry.data.get(CONF_SUNRISE_OFFSET, DEFAULT_SUNRISE_OFFSET),
                ),
            ),
            CONF_SUNSET_OFFSET: self._base_options.get(
                CONF_SUNSET_OFFSET,
                self.config_entry.options.get(
                    CONF_SUNSET_OFFSET,
                    self.config_entry.data.get(CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET),
                ),
            ),
        }

        current_covers = self.config_entry.options.get(
            CONF_COVERS, self.config_entry.data.get(CONF_COVERS, [])
        )

        existing = self._cover_options or current_covers

        schema = vol.Schema(
            {
                vol.Required(CONF_COVERS, default=existing): vol.All(
                    vol.Length(min=1), [_cover_schema(cover_defaults)]
                )
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="cover_settings", data_schema=schema)

        self._cover_options = user_input[CONF_COVERS]
        data = {**self._base_options, CONF_COVERS: self._cover_options}
        return self.async_create_entry(title="Shutter Control", data=data)
