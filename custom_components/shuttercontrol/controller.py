"""Core controller logic derived from the Cover Control Automation blueprint."""
from __future__ import annotations

from datetime import datetime, timedelta, time

from homeassistant import config_entries
from homeassistant.const import STATE_ON
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_BRIGHTNESS_ENTITY,
    CONF_AUTO_COLD,
    CONF_AUTO_COLD_ENTITY,
    CONF_AUTO_DOWN,
    CONF_AUTO_DOWN_ENTITY,
    CONF_AUTO_SHADING,
    CONF_AUTO_SHADING_ENTITY,
    CONF_AUTO_SUN,
    CONF_AUTO_SUN_ENTITY,
    CONF_AUTO_UP,
    CONF_AUTO_UP_ENTITY,
    CONF_AUTO_VENTILATE,
    CONF_AUTO_VENTILATE_ENTITY,
    CONF_AUTO_WIND,
    CONF_AUTO_WIND_ENTITY,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_MANUAL_OVERRIDE_MINUTES,
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
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_OPEN_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_SHADING_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_WIND_LIMIT,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)


def _parse_time(value: str | datetime | None) -> time | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.timetz()
    parsed_datetime = dt_util.parse_datetime(value)
    if parsed_datetime:
        return parsed_datetime.timetz()
    try:
        return dt_util.parse_time(str(value))
    except (TypeError, ValueError):
        return None


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class ControllerManager:
    """Create and coordinate per-cover controllers."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.controllers: dict[str, ShutterController] = {}

    async def async_setup(self) -> None:
        data = {**DEFAULT_AUTOMATION_FLAGS, **self.entry.data, **self.entry.options}
        for cover in data.get(CONF_COVERS, []):
            controller = ShutterController(self.hass, self.entry, cover, data)
            await controller.async_setup()
            self.controllers[cover] = controller

    async def async_unload(self) -> None:
        for controller in self.controllers.values():
            await controller.async_unload()
        self.controllers.clear()

    @callback
    def async_update_options(self) -> None:
        new_data = {**DEFAULT_AUTOMATION_FLAGS, **self.entry.data, **self.entry.options}
        for controller in self.controllers.values():
            controller.update_config(new_data)

    def set_manual_override(self, cover: str, minutes: int) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.set_manual_override(minutes)
        return True

    def activate_shading(self, cover: str, minutes: int | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.activate_shading(minutes)
        return True
    
    def clear_manual_override(self, cover: str) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.clear_manual_override()
        return True


class ShutterController:
    """Translate blueprint-style parameters into runtime cover control."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry, cover: str, config: ConfigType) -> None:
        self.hass = hass
        self.entry = entry
        self.cover = cover
        self.config = config
        self._unsubs: list[CALLBACK_TYPE] = []
        self._manual_until: datetime | None = None
        self._target: float | None = None
        self._reason: str | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        self._auto_entity_map = {
            CONF_AUTO_UP: CONF_AUTO_UP_ENTITY,
            CONF_AUTO_DOWN: CONF_AUTO_DOWN_ENTITY,
            CONF_AUTO_BRIGHTNESS: CONF_AUTO_BRIGHTNESS_ENTITY,
            CONF_AUTO_SUN: CONF_AUTO_SUN_ENTITY,
            CONF_AUTO_VENTILATE: CONF_AUTO_VENTILATE_ENTITY,
            CONF_AUTO_SHADING: CONF_AUTO_SHADING_ENTITY,
            CONF_AUTO_COLD: CONF_AUTO_COLD_ENTITY,
            CONF_AUTO_WIND: CONF_AUTO_WIND_ENTITY,
        }

    async def async_setup(self) -> None:
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_interval, timedelta(minutes=1))
        )
        sensor_entities = [
            self.config.get(CONF_BRIGHTNESS_SENSOR),
            self.config.get(CONF_WORKDAY_SENSOR),
            self.config.get(CONF_WIND_SENSOR),
            self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR),
            self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR),
            self.config.get(CONF_COLD_PROTECTION_FORECAST_SENSOR),
            self.config.get(CONF_RESIDENT_SENSOR),
            self.cover,
        ]
        sensor_entities.extend(self._window_sensors())
        for entity_id in sensor_entities:
            if not entity_id:
                continue
            self._unsubs.append(
                async_track_state_change_event(self.hass, [entity_id], self._handle_state_event)
            )
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    async def async_unload(self) -> None:
        while self._unsubs:
            unsub = self._unsubs.pop()
            unsub()

    @callback
    def update_config(self, new_config: ConfigType) -> None:
        self.config = new_config
        self._manual_until = None
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    @callback
    def _handle_state_event(self, event) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        if event.data.get("entity_id") == self.cover:
            tolerance = float(
                self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
            )
            current = self._current_position()
            if (
                current is not None
                and self._target is not None
                and abs(current - self._target) > tolerance
                and not self._manual_until
            ):
                duration = self.config.get(
                    CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
                )
                self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
                self._reason = "manual_override"
                self._refresh_next_events(dt_util.utcnow())
                self._publish_state()
        self.hass.async_create_task(self._evaluate("state"))

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self.hass.async_create_task(self._evaluate("time"))

    def set_manual_override(self, minutes: int) -> None:
        duration = minutes or self.config.get(
            CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
        )
        self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
        self._reason = "manual_override"
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()
    
    def clear_manual_override(self) -> None:
        self._manual_until = None
        if self._reason in {"manual_override", "manual_shading"}:
            self._reason = None
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def activate_shading(self, minutes: int | None = None) -> None:
        duration = minutes or self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
        self.hass.async_create_task(
            self._set_position(self.config.get(CONF_SHADING_POSITION), "manual_shading")
        )

    def _expire_manual_override(self, now: datetime) -> None:
        if self._manual_until and now >= self._manual_until:
            self._manual_until = None
            if self._reason in {"manual_override", "manual_shading"}:
                self._reason = None

    async def _evaluate(self, trigger: str) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        if self._manual_until and now < self._manual_until:
            self._refresh_next_events(now)
            self._publish_state()
            return

        up_due = self._event_due(self._next_open, now)
        down_due = self._event_due(self._next_close, now)

        brightness = _float_state(self.hass, self.config.get(CONF_BRIGHTNESS_SENSOR))
        sun_state = self.hass.states.get("sun.sun")
        sun_elevation = sun_state and sun_state.attributes.get("elevation")
        sun_azimuth = sun_state and sun_state.attributes.get("azimuth")

        wind_speed = _float_state(self.hass, self.config.get(CONF_WIND_SENSOR))
        wind_limit = float(self.config.get(CONF_WIND_LIMIT, DEFAULT_WIND_LIMIT))
        if self._auto_enabled(CONF_AUTO_WIND) and wind_speed is not None and wind_speed >= wind_limit:
            await self._set_position(
                self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                "wind_protection",
            )
            return

        if self._is_resident_sleeping():
            await self._set_position(
                self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                "resident_asleep",
            )
            return

        if self._auto_enabled(CONF_AUTO_VENTILATE) and self._is_window_open():
            await self._set_position(
                self._position_value(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION),
                "ventilation",
            )
            return

        if self._auto_enabled(CONF_AUTO_COLD) and self._cold_protection_needed(sun_elevation):
            await self._set_position(
                self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                "cold_protection",
            )
            return

        if self._auto_enabled(CONF_AUTO_SHADING):
            shading_active = self._reason in {"shading", "manual_shading"}
            shading_allowed = self._shading_conditions(
                sun_azimuth, sun_elevation, brightness
            )
            if shading_active and not shading_allowed:
                if (
                    self._auto_enabled(CONF_AUTO_DOWN)
                    and self._sun_allows_close(sun_elevation)
                    and self._brightness_allows_close(brightness)
                ):
                    await self._set_position(
                        self._position_value(
                            CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
                        ),
                        "shading_end_close",
                    )
                    return
                if (
                    self._auto_enabled(CONF_AUTO_UP)
                    and self._sun_allows_open(sun_elevation)
                    and self._brightness_allows_open(brightness)
                ):
                    await self._set_position(
                        self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                        "shading_end_open",
                    )
                    return
            if shading_allowed:
                await self._set_position(
                    self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION),
                    "shading",
                )
                return
        
        if self._auto_enabled(CONF_AUTO_SUN) and self._sun_allows_close(sun_elevation):
            if self._brightness_allows_close(brightness):
                await self._set_position(
                    self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    "sun_close",
                )
                return

        if self._auto_enabled(CONF_AUTO_UP) and up_due:
            if self._sun_allows_open(sun_elevation) and self._brightness_allows_open(brightness):
                await self._set_position(
                    self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                    "scheduled_open",
                )
                return
            self._next_open = now + timedelta(minutes=1)
            self._publish_state()
            return

        if self._auto_enabled(CONF_AUTO_DOWN) and down_due:
            if self._sun_allows_close(sun_elevation) and self._brightness_allows_close(brightness):
                await self._set_position(
                    self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    "scheduled_close",
                )
                return
            self._next_close = now + timedelta(minutes=1)
            self._publish_state()
            return

        self._refresh_next_events(now)
        self._publish_state()

    def _sun_allows_open(self, sun_elevation: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        return sun_elevation >= float(self.config.get(CONF_SUN_ELEVATION_OPEN))

    def _sun_allows_close(self, sun_elevation: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        return sun_elevation <= float(self.config.get(CONF_SUN_ELEVATION_CLOSE))

    def _brightness_allows_open(self, brightness: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        return brightness >= float(self.config.get(CONF_BRIGHTNESS_OPEN_ABOVE))

    def _brightness_allows_close(self, brightness: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        return brightness <= float(self.config.get(CONF_BRIGHTNESS_CLOSE_BELOW))

    def _cold_protection_needed(self, sun_elevation: float | None) -> bool:
        if sun_elevation is not None and sun_elevation > 0:
            return False
        threshold = self._cold_threshold()
        if threshold is None:
            return False
        outdoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR))
        if outdoor is not None and outdoor <= threshold:
            return True
        forecast = self._cold_forecast_temperature()
        if forecast is not None and forecast <= threshold:
            return True
        return False

    def _cold_threshold(self) -> float | None:
        value = self.config.get(CONF_COLD_PROTECTION_THRESHOLD)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _cold_forecast_temperature(self) -> float | None:
        entity_id = self.config.get(CONF_COLD_PROTECTION_FORECAST_SENSOR)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        domain = state.entity_id.split(".")[0]
        if domain == "weather":
            forecast = state.attributes.get("forecast")
            if isinstance(forecast, list) and forecast:
                entry = forecast[0] or {}
                for key in ("templow", "temperature"):
                    try:
                        return float(entry.get(key))
                    except (TypeError, ValueError):
                        continue
            try:
                return float(state.attributes.get("temperature"))
            except (TypeError, ValueError):
                return None
        return _float_state(self.hass, entity_id)

    def _shading_conditions(
        self, sun_azimuth: float | None, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        if sun_azimuth is None or sun_elevation is None:
            return False
        if brightness is None:
            return False
        az_start = float(self.config.get(CONF_SUN_AZIMUTH_START))
        az_end = float(self.config.get(CONF_SUN_AZIMUTH_END))
        el_min = float(self.config.get(CONF_SUN_ELEVATION_MIN))
        el_max = float(self.config.get(CONF_SUN_ELEVATION_MAX))
        bright_start = float(self.config.get(CONF_SHADING_BRIGHTNESS_START))
        bright_end = float(self.config.get(CONF_SHADING_BRIGHTNESS_END))
        if not (az_start <= sun_azimuth <= az_end and el_min <= sun_elevation <= el_max):
            return False
        if brightness < bright_start:
            return False
        if self._reason == "shading" and brightness <= bright_end:
            return False
        temp_ok = self._temperature_allows_shading()
        return temp_ok or brightness >= bright_start

    def _temperature_allows_shading(self) -> bool:
        indoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR))
        outdoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR))
        forecast_threshold = self.config.get(CONF_TEMPERATURE_FORECAST_THRESHOLD)
        forecast_hot = False
        if forecast_threshold is not None:
            try:
                forecast_hot = float(forecast_threshold) > 0
            except (TypeError, ValueError):
                forecast_hot = False
        threshold = float(self.config.get(CONF_TEMPERATURE_THRESHOLD))
        if indoor is not None and indoor >= threshold:
            return True
        if outdoor is not None and outdoor >= threshold:
            return True
        return forecast_hot

    def _is_workday(self) -> bool:
        workday_entity = self.config.get(CONF_WORKDAY_SENSOR)
        if not workday_entity:
            return True
        return self.hass.states.is_state(workday_entity, STATE_ON)

    def _is_window_open(self) -> bool:
        window_entities = self._window_sensors()
        if not window_entities:
            return False
        return any(self.hass.states.is_state(entity_id, STATE_ON) for entity_id in window_entities)

    def _is_resident_sleeping(self) -> bool:
        resident_entity = self.config.get(CONF_RESIDENT_SENSOR)
        if not resident_entity:
            return False
        return self.hass.states.is_state(resident_entity, STATE_ON)

    def _time_setting(self, workday: bool, is_up: bool) -> time | None:
        if workday:
            value_key = CONF_TIME_UP_WORKDAY if is_up else CONF_TIME_DOWN_WORKDAY
        else:
            value_key = CONF_TIME_UP_NON_WORKDAY if is_up else CONF_TIME_DOWN_NON_WORKDAY
        return _parse_time(self.config.get(value_key))

    def _event_due(self, target: datetime | None, now: datetime) -> bool:
        if not target:
            return False
        return now >= target

    def _position_value(self, key: str, default: float) -> float | None:
        entity_key = self._position_entity_map.get(key)
        raw_value = self.config.get(key, default)
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return default

    def _auto_enabled(self, config_key: str) -> bool:
        entity_key = self._auto_entity_map.get(config_key)
        if entity_key:
            entity_id = self.config.get(entity_key)
            if entity_id and self.hass.states.get(entity_id) is not None:
                return self.hass.states.is_state(entity_id, STATE_ON)
        return bool(self.config.get(config_key))

    async def _set_position(self, position: float | None, reason: str) -> None:
        if position is None:
            return
        tolerance = float(
            self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
        )
        current = self._current_position()
        if current is not None and abs(current - float(position)) <= tolerance and self._reason == reason:
            return
        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": self.cover, "position": float(position)},
            blocking=False,
        )
        self._target = float(position)
        self._reason = reason
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def _current_position(self) -> float | None:
        state = self.hass.states.get(self.cover)
        if not state:
            return None
        try:
            return float(state.attributes.get("current_position"))
        except (TypeError, ValueError):
            return None

    def _window_sensors(self) -> list[str]:
        mapping = self.config.get(CONF_WINDOW_SENSORS) or {}
        sensors = mapping.get(self.cover, [])
        return sensors or []

    def _refresh_next_events(self, now: datetime) -> None:
        candidates_open: list[datetime] = []
        candidates_close: list[datetime] = []
        if self._auto_enabled(CONF_AUTO_SUN):
            sun_state = self.hass.states.get("sun.sun")
            sun_next_rising = sun_state and sun_state.attributes.get("next_rising")
            sun_next_setting = sun_state and sun_state.attributes.get("next_setting")
            next_rising = self._parse_datetime_attr(sun_next_rising)
            next_setting = self._parse_datetime_attr(sun_next_setting)
            if next_rising:
                candidates_open.append(next_rising)
            if next_setting:
                candidates_close.append(next_setting)
        workday = self._is_workday()
        next_up = self._next_time_for_point(self._time_setting(workday, True), now)
        next_down = self._next_time_for_point(self._time_setting(workday, False), now)
        if self._auto_enabled(CONF_AUTO_UP) and next_up:
            candidates_open.append(next_up)
        if self._auto_enabled(CONF_AUTO_DOWN) and next_down:
            candidates_close.append(next_down)
        self._next_open = min(candidates_open) if candidates_open else None
        self._next_close = min(candidates_close) if candidates_close else None
        
    def _parse_datetime_attr(self, value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        parsed = dt_util.parse_datetime(str(value))
        if parsed:
            return dt_util.as_utc(parsed)
        return None

    def _next_time_for_point(self, scheduled: time | None, now: datetime) -> datetime | None:
        if not scheduled:
            return None
        local_now = dt_util.as_local(now)
        candidate_local = datetime.combine(local_now.date(), scheduled, local_now.tzinfo)
        if candidate_local <= local_now:
            candidate_local = candidate_local + timedelta(days=1)
        return dt_util.as_utc(candidate_local)

    def _publish_state(self) -> None:
        current_position = self._current_position()
        shading_enabled = self._auto_enabled(CONF_AUTO_SHADING)
        shading_active = shading_enabled and self._reason in {"shading", "manual_shading"}
        async_dispatcher_send(
            self.hass,
            SIGNAL_STATE_UPDATED,
            self.entry.entry_id,
            self.cover,
            self._target,
            self._reason,
            self._manual_until,
            self._next_open,
            self._next_close,
            current_position,
            shading_enabled,
            shading_active,
        )
