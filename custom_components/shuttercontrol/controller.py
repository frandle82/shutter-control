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
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
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
    CONF_TIME_DOWN_EARLY,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_LATE,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_UP_EARLY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_LATE,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_VENTILATE_POSITION,
    CONF_WIND_LIMIT,
    CONF_WIND_SENSOR,
    CONF_WINDOW_SENSORS,
    CONF_WORKDAY_SENSOR,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_TOLERANCE,
    DEFAULT_WIND_LIMIT,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return dt_util.parse_time(value)
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
        data = {**self.entry.data, **self.entry.options}
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
        new_data = {**self.entry.data, **self.entry.options}
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
            self.config.get(CONF_RESIDENT_SENSOR),
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

    @callback
    def _handle_state_event(self, event) -> None:
        self.hass.async_create_task(self._evaluate("state"))

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self.hass.async_create_task(self._evaluate("time"))

    def set_manual_override(self, minutes: int) -> None:
        duration = minutes or self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
        self._reason = "manual_override"
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def activate_shading(self, minutes: int | None = None) -> None:
        duration = minutes or self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
        self.hass.async_create_task(
            self._set_position(self.config.get(CONF_SHADING_POSITION), "manual_shading")
        )

    async def _evaluate(self, trigger: str) -> None:
        now = dt_util.utcnow()
        if self._manual_until and now < self._manual_until:
            self._refresh_next_events(now)
            self._publish_state()
            return

        workday = self._is_workday()
        up_window = self._time_window(
            _parse_time(self.config.get(CONF_TIME_UP_EARLY if workday else CONF_TIME_UP_EARLY_NON_WORKDAY)),
            _parse_time(self.config.get(CONF_TIME_UP_LATE if workday else CONF_TIME_UP_LATE_NON_WORKDAY)),
            now,
        )
        down_window = self._time_window(
            _parse_time(self.config.get(CONF_TIME_DOWN_EARLY if workday else CONF_TIME_DOWN_EARLY_NON_WORKDAY)),
            _parse_time(self.config.get(CONF_TIME_DOWN_LATE if workday else CONF_TIME_DOWN_LATE_NON_WORKDAY)),
            now,
        )

        brightness = _float_state(self.hass, self.config.get(CONF_BRIGHTNESS_SENSOR))
        sun_state = self.hass.states.get("sun.sun")
        sun_elevation = sun_state and sun_state.attributes.get("elevation")
        sun_azimuth = sun_state and sun_state.attributes.get("azimuth")

        wind_speed = _float_state(self.hass, self.config.get(CONF_WIND_SENSOR)) or 0.0
        wind_limit = float(self.config.get(CONF_WIND_LIMIT, DEFAULT_WIND_LIMIT))
        if wind_speed >= wind_limit:
            await self._set_position(self.config.get(CONF_OPEN_POSITION), "wind_protection")
            return

        if self._is_resident_sleeping():
            await self._set_position(self.config.get(CONF_CLOSE_POSITION), "resident_asleep")
            return

        if self.config.get(CONF_AUTO_VENTILATE) and self._is_window_open():
            await self._set_position(self.config.get(CONF_VENTILATE_POSITION), "ventilation")
            return

        if self.config.get(CONF_AUTO_SHADING) and self._shading_conditions(
            sun_azimuth, sun_elevation, brightness
        ):
            await self._set_position(self.config.get(CONF_SHADING_POSITION), "shading")
            return

        if self.config.get(CONF_AUTO_UP) and up_window:
            if self._sun_allows_open(sun_elevation) and self._brightness_allows_open(brightness):
                await self._set_position(self.config.get(CONF_OPEN_POSITION), "scheduled_open")
                return

        if self.config.get(CONF_AUTO_DOWN) and down_window:
            if self._sun_allows_close(sun_elevation) and self._brightness_allows_close(brightness):
                await self._set_position(self.config.get(CONF_CLOSE_POSITION), "scheduled_close")
                return
        self._refresh_next_events(now)
        self._publish_state()

    def _sun_allows_open(self, sun_elevation: float | None) -> bool:
        if not self.config.get(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        return sun_elevation >= float(self.config.get(CONF_SUN_ELEVATION_OPEN))

    def _sun_allows_close(self, sun_elevation: float | None) -> bool:
        if not self.config.get(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        return sun_elevation <= float(self.config.get(CONF_SUN_ELEVATION_CLOSE))

    def _brightness_allows_open(self, brightness: float | None) -> bool:
        if not self.config.get(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        return brightness >= float(self.config.get(CONF_BRIGHTNESS_OPEN_ABOVE))

    def _brightness_allows_close(self, brightness: float | None) -> bool:
        if not self.config.get(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        return brightness <= float(self.config.get(CONF_BRIGHTNESS_CLOSE_BELOW))

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

    def _time_window(self, start: time | None, end: time | None, now: datetime) -> bool:
        if not start or not end:
            return True
        local_now = dt_util.as_local(now).time()
        if start <= end:
            return start <= local_now <= end
        return local_now >= start or local_now <= end

    async def _set_position(self, position: float | None, reason: str) -> None:
        if position is None:
            return
        tolerance = float(self.config.get(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE))
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
        self._next_open = self._next_time_for_window(
            _parse_time(
                self.config.get(
                    CONF_TIME_UP_EARLY if self._is_workday() else CONF_TIME_UP_EARLY_NON_WORKDAY
                )
            ),
            now,
        )
        self._next_close = self._next_time_for_window(
            _parse_time(
                self.config.get(
                    CONF_TIME_DOWN_EARLY if self._is_workday() else CONF_TIME_DOWN_EARLY_NON_WORKDAY
                )
            ),
            now,
        )

    def _next_time_for_window(self, start: time | None, now: datetime) -> datetime | None:
        if not start:
            return None
        local_now = dt_util.as_local(now)
        candidate_local = datetime.combine(local_now.date(), start, local_now.tzinfo)
        if candidate_local <= local_now:
            candidate_local = candidate_local + timedelta(days=1)
        return dt_util.as_utc(candidate_local)

    def _publish_state(self) -> None:
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
        )
