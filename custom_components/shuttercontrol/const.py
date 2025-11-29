"""Constants for Shutter Control integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "shuttercontrol"
CONF_NAME = "name"
DEFAULT_NAME = "Cover Control"
PLATFORMS: list[Platform] = [
        Platform.SENSOR,
        Platform.NUMBER,
        Platform.TIME,
        Platform.SWITCH
    ]

CONF_COVERS = "covers"
CONF_OPEN_POSITION = "open_position"
CONF_CLOSE_POSITION = "close_position"
CONF_VENTILATE_POSITION = "ventilate_position"
CONF_SHADING_POSITION = "shading_position"
CONF_POSITION_TOLERANCE = "position_tolerance"
CONF_TIME_UP_WORKDAY = "time_up_workday"
CONF_TIME_UP_NON_WORKDAY = "time_up_non_workday"
CONF_TIME_DOWN_WORKDAY = "time_down_workday"
CONF_TIME_DOWN_NON_WORKDAY = "time_down_non_workday"

CONF_WORKDAY_SENSOR = "workday_sensor"
CONF_BRIGHTNESS_SENSOR = "brightness_sensor"
CONF_BRIGHTNESS_OPEN_ABOVE = "brightness_open_above"
CONF_BRIGHTNESS_CLOSE_BELOW = "brightness_close_below"

CONF_SUN_ELEVATION_OPEN = "sun_elevation_open"
CONF_SUN_ELEVATION_CLOSE = "sun_elevation_close"
CONF_SUN_AZIMUTH_START = "shading_azimuth_start"
CONF_SUN_AZIMUTH_END = "shading_azimuth_end"
CONF_SUN_ELEVATION_MIN = "shading_elevation_min"
CONF_SUN_ELEVATION_MAX = "shading_elevation_max"
CONF_SHADING_BRIGHTNESS_START = "shading_brightness_start"
CONF_SHADING_BRIGHTNESS_END = "shading_brightness_end"
DEFAULT_SHADING_FORECAST_TYPE = "weather_attributes"
CONF_SHADING_FORECAST_SENSOR = "shading_forecast_sensor"
CONF_SHADING_FORECAST_TYPE = "shading_forecast_type"
CONF_SHADING_WEATHER_CONDITIONS = "shading_weather_conditions"

CONF_TEMPERATURE_SENSOR_INDOOR = "temperature_sensor_indoor"
CONF_TEMPERATURE_SENSOR_OUTDOOR = "temperature_sensor_outdoor"
CONF_TEMPERATURE_THRESHOLD = "temperature_threshold"
CONF_TEMPERATURE_FORECAST_THRESHOLD = "temperature_forecast_threshold"

CONF_RESIDENT_SENSOR = "resident_sensor"
CONF_WINDOW_SENSORS = "window_sensors"

CONF_AUTO_UP = "auto_up_enabled"
CONF_AUTO_UP_ENTITY = "auto_up_entity"
CONF_AUTO_DOWN = "auto_down_enabled"
CONF_AUTO_DOWN_ENTITY = "auto_down_entity"
CONF_AUTO_BRIGHTNESS = "auto_brightness_enabled"
CONF_AUTO_BRIGHTNESS_ENTITY = "auto_brightness_entity"
CONF_AUTO_SUN = "auto_sun_enabled"
CONF_AUTO_SUN_ENTITY = "auto_sun_entity"
CONF_AUTO_VENTILATE = "auto_ventilate_enabled"
CONF_AUTO_VENTILATE_ENTITY = "auto_ventilate_entity"
CONF_AUTO_SHADING = "auto_shading_enabled"
CONF_AUTO_SHADING_ENTITY = "auto_shading_entity"
CONF_AUTO_COLD = "auto_cold_protection_enabled"
CONF_AUTO_COLD_ENTITY = "auto_cold_entity"

DEFAULT_AUTOMATION_FLAGS: dict[str, bool] = {
    CONF_AUTO_UP: True,
    CONF_AUTO_DOWN: True,
    CONF_AUTO_BRIGHTNESS: True,
    CONF_AUTO_SUN: True,
    CONF_AUTO_VENTILATE: True,
    CONF_AUTO_SHADING: True,
    CONF_AUTO_COLD: False,
}

CONF_COLD_PROTECTION_THRESHOLD = "cold_protection_temperature"
CONF_COLD_PROTECTION_FORECAST_SENSOR = "cold_protection_forecast_sensor"

CONF_MANUAL_OVERRIDE_MINUTES = "manual_override_minutes"
CONF_MANUAL_OVERRIDE_BLOCK_OPEN = "manual_override_block_open"
CONF_MANUAL_OVERRIDE_BLOCK_CLOSE = "manual_override_block_close"
CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE = "manual_override_block_ventilate"
CONF_MANUAL_OVERRIDE_BLOCK_SHADING = "manual_override_block_shading"
CONF_MANUAL_OVERRIDE_RESET_MODE = "manual_override_reset_mode"
CONF_MANUAL_OVERRIDE_RESET_TIME = "manual_override_reset_time"
CONF_FULL_OPEN_POSITION = "full_open_position"

MANUAL_OVERRIDE_RESET_NONE = "none"
MANUAL_OVERRIDE_RESET_TIME = "time"
MANUAL_OVERRIDE_RESET_TIMEOUT = "timeout"

SIGNAL_STATE_UPDATED = "shuttercontrol_state_updated"

DEFAULT_OPEN_POSITION = 100
DEFAULT_CLOSE_POSITION = 0
DEFAULT_VENTILATE_POSITION = 50
DEFAULT_SHADING_POSITION = 30
DEFAULT_TOLERANCE = 3

DEFAULT_BRIGHTNESS_OPEN = 500
DEFAULT_BRIGHTNESS_CLOSE = 100
DEFAULT_SUN_ELEVATION_OPEN = -2.0
DEFAULT_SUN_ELEVATION_CLOSE = -4.0
DEFAULT_SHADING_AZIMUTH_START = 90
DEFAULT_SHADING_AZIMUTH_END = 270
DEFAULT_SHADING_ELEVATION_MIN = 10
DEFAULT_SHADING_ELEVATION_MAX = 70
DEFAULT_SHADING_BRIGHTNESS_START = 20000
DEFAULT_SHADING_BRIGHTNESS_END = 15000
DEFAULT_TEMPERATURE_THRESHOLD = 26.0
DEFAULT_TEMPERATURE_FORECAST_THRESHOLD = 27.0
DEFAULT_COLD_PROTECTION_THRESHOLD = 5.0
DEFAULT_MANUAL_OVERRIDE_MINUTES = 90
DEFAULT_MANUAL_OVERRIDE_RESET_TIME = "00:00:00"
DEFAULT_MANUAL_OVERRIDE_FLAGS: dict[str, bool] = {
    CONF_MANUAL_OVERRIDE_BLOCK_OPEN: True,
    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE: True,
    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE: True,
    CONF_MANUAL_OVERRIDE_BLOCK_SHADING: True,
}

DEFAULT_TIME_UP_WORKDAY = "06:00:00"
DEFAULT_TIME_UP_NON_WORKDAY = "07:30:00"
DEFAULT_TIME_DOWN_WORKDAY = "18:00:00"
DEFAULT_TIME_DOWN_NON_WORKDAY = "18:30:00"
