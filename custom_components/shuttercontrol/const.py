"""Constants for the Shutter Control integration."""

from __future__ import annotations

DOMAIN = "shuttercontrol"
CONF_COVERS = "covers"
CONF_SUNRISE_OFFSET = "sunrise_offset"
CONF_SUNSET_OFFSET = "sunset_offset"
CONF_OPEN_POSITION = "open_position"
CONF_CLOSE_POSITION = "close_position"
CONF_NAME = "name"
CONF_PRESENCE_ENTITY = "presence_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_WIND_SPEED_LIMIT = "wind_speed_limit"
CONF_MANUAL_OVERRIDE = "manual_override"
CONF_WINDOW_SENSORS = "window_sensors"
DEFAULT_OPEN_POSITION = 100
DEFAULT_CLOSE_POSITION = 0
DEFAULT_SUNRISE_OFFSET = -15
DEFAULT_SUNSET_OFFSET = 15
DEFAULT_WIND_SPEED_LIMIT = 50.0
SERVICE_RECALCULATE = "recalculate_targets"
SERVICE_MOVE_COVERS = "move_covers"
ATTR_TARGET = "target"
ATTR_REASON = "reason"

SUPPORTED_PLATFORMS: list[str] = ["sensor"]
