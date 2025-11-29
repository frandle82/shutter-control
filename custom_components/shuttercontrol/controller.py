"""Core controller logic derived from the Cover Control Automation blueprint."""
from __future__ import annotations

import asyncio
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
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
    CONF_MANUAL_OVERRIDE_RESET_MODE,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
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
    CONF_WINDOW_SENSORS,
    CONF_WORKDAY_SENSOR,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_TIME_DOWN_NON_WORKDAY,
    DEFAULT_TIME_DOWN_WORKDAY,
    DEFAULT_TIME_UP_NON_WORKDAY,
    DEFAULT_TIME_UP_WORKDAY,
    DEFAULT_OPEN_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_SHADING_POSITION,
    DEFAULT_CLOSE_POSITION,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
)

IDLE_REASON = "idle"

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
        data = {
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **self.entry.data,
            **self.entry.options,
        }
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
        new_data = {
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **self.entry.data,
            **self.entry.options,
        }
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

    async def recalibrate_cover(self, cover: str, full_open: float | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        await controller.recalibrate(full_open)
        return True

    def state_snapshot(
        self, cover: str
        ) -> tuple[
            float | None,
            str | None,
            datetime | None,
            bool,
            datetime | None,
            datetime | None,
            float | None,
            bool,
            bool,
            bool,
        ] | None:
            controller = self.controllers.get(cover)
            if not controller:
                return (
                    None,
                    IDLE_REASON,
                    None,
                    None,
                    False,
                    None,
                    None,
                    False,
                    False,
                    False,
                )
            return controller.state_snapshot()

class ShutterController:
    """Translate blueprint-style parameters into runtime cover control."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry, cover: str, config: ConfigType) -> None:
        self.hass = hass
        self.entry = entry
        self.cover = cover
        self.config = config
        self._unsubs: list[CALLBACK_TYPE] = []
        self._manual_until: datetime | None = None
        self._manual_active: bool = False
        self._manual_scope_all: bool = False
        self._target: float | None = None
        self._reason: str | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        # Position helpers were removed, but keep the mapping available so
        # legacy config entries that still reference helper entities do not
        # cause attribute errors during lookups.
        self._position_entity_map: dict[str, str] = {}
        self._auto_entity_map = {
            CONF_AUTO_UP: CONF_AUTO_UP_ENTITY,
            CONF_AUTO_DOWN: CONF_AUTO_DOWN_ENTITY,
            CONF_AUTO_BRIGHTNESS: CONF_AUTO_BRIGHTNESS_ENTITY,
            CONF_AUTO_SUN: CONF_AUTO_SUN_ENTITY,
            CONF_AUTO_VENTILATE: CONF_AUTO_VENTILATE_ENTITY,
            CONF_AUTO_SHADING: CONF_AUTO_SHADING_ENTITY,
            CONF_AUTO_COLD: CONF_AUTO_COLD_ENTITY,
        }

    async def async_setup(self) -> None:
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_interval, timedelta(minutes=1))
        )
        sensor_entities = [
            self.config.get(CONF_BRIGHTNESS_SENSOR),
            self.config.get(CONF_WORKDAY_SENSOR),
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
        self._manual_active = False
        self._manual_scope_all = False
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self.hass.async_create_task(self._evaluate("config"))
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
                and self._manual_detection_enabled()
            ):
                self._activate_manual_override(reason="manual_override")
        self.hass.async_create_task(self._evaluate("state"))

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self.hass.async_create_task(self._evaluate("time"))

    def _manual_detection_enabled(self) -> bool:
        if self._manual_active:
            return False
        return any(
            bool(self.config.get(flag, DEFAULT_MANUAL_OVERRIDE_FLAGS.get(flag, False)))
            for flag in (
                CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
            )
        )

    def _activate_manual_override(
        self, minutes: int | None = None, scope_all: bool = False, reason: str | None = None
    ) -> None:
        now = dt_util.utcnow()
        self._manual_active = True
        self._manual_scope_all = self._manual_scope_all or scope_all
        self._manual_until = self._manual_reset_at(now, minutes)
        if reason:
            self._reason = reason
        elif self._manual_scope_all:
            self._reason = "manual_override"
        self._refresh_next_events(now)
        self._publish_state()

    def _manual_reset_at(self, now: datetime, minutes: int | None = None) -> datetime | None:
        if minutes is not None:
            return now + timedelta(minutes=minutes)
        mode = self.config.get(CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT)
        if mode == MANUAL_OVERRIDE_RESET_NONE:
            return None
        if mode == MANUAL_OVERRIDE_RESET_TIME:
            reset_time = _parse_time(self.config.get(CONF_MANUAL_OVERRIDE_RESET_TIME)) or _parse_time(
                DEFAULT_MANUAL_OVERRIDE_RESET_TIME
            )
            return self._next_time_for_point(reset_time, now)
        duration = self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        try:
            minutes_value = int(duration)
        except (TypeError, ValueError):
            minutes_value = DEFAULT_MANUAL_OVERRIDE_MINUTES
        return now + timedelta(minutes=minutes_value)

    def _manual_blocks_action(self, action: str) -> bool:
        if not self._manual_active:
            return False
        if self._manual_scope_all:
            return True
        flag_map = {
            "open": CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
            "close": CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
            "ventilation": CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
            "shading": CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
        }
        flag = flag_map.get(action)
        if not flag:
            return False
        return bool(self.config.get(flag, DEFAULT_MANUAL_OVERRIDE_FLAGS.get(flag, False)))

    def set_manual_override(self, minutes: int) -> None:
        duration = minutes or self.config.get(
            CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
        )
        self._activate_manual_override(
            minutes=duration, scope_all=True, reason="manual_override"
        )
    
    def clear_manual_override(self) -> None:
        self._manual_until = None
        self._manual_active = False
        self._manual_scope_all = False
        if self._reason in {"manual_override", "manual_shading"}:
            self._reason = None
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def publish_state(self) -> None:
        """Expose the current state via dispatcher for newly added entities."""
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def state_snapshot(
        self,
    ) -> tuple[
        float | None,
        str | None,
        datetime | None,
        bool,
        datetime | None,
        datetime | None,
        float | None,
        bool,
        bool,
        bool,
    ]:
        """Provide the current state values without dispatching updates."""

        self._refresh_next_events(dt_util.utcnow())
        current_position = self._current_position()
        shading_enabled = self._auto_enabled(CONF_AUTO_SHADING)
        shading_active = self._shading_is_active(current_position, shading_enabled)
        ventilation_active = self._ventilation_is_active(current_position)
        return (
            self._target,
            self._reason or IDLE_REASON,
            self._manual_until,
            self._manual_active,
            self._next_open,
            self._next_close,
            current_position,
            shading_enabled,
            shading_active,
            ventilation_active,
        )

    def activate_shading(self, minutes: int | None = None) -> None:
        duration = minutes or self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
        self.hass.async_create_task(
            self._set_position(self.config.get(CONF_SHADING_POSITION), "manual_shading")
        )

    async def recalibrate(self, full_open: float | None) -> None:
        tolerance = float(self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE))
        target_open = self._normalize_position(full_open, DEFAULT_OPEN_POSITION)
        current_position = self._current_position()

        manual_state = (
            self._manual_until,
            self._manual_active,
            self._manual_scope_all,
            self._reason,
        )

        self._activate_manual_override(
            minutes=self.config.get(
                CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
            ),
            scope_all=True,
            reason="manual_override",
        )

        try:
            await self._command_position(target_open)
            await self._wait_for_position(target_open, tolerance)

            if current_position is not None:
                await self._command_position(current_position)
                await self._wait_for_position(current_position, tolerance)
        finally:
            (
                self._manual_until,
                self._manual_active,
                self._manual_scope_all,
                self._reason,
            ) = manual_state
            self._refresh_next_events(dt_util.utcnow())
            self._publish_state()

    def _expire_manual_override(self, now: datetime) -> None:
        if self._manual_until and now >= self._manual_until:
            self._manual_until = None
            self._manual_active = False
            self._manual_scope_all = False
            if self._reason in {"manual_override", "manual_shading"}:
                self._reason = None

    async def _evaluate(self, trigger: str) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        if self._manual_active and self._manual_scope_all:
            self._refresh_next_events(now)
            self._publish_state()
            return

        up_due = self._event_due(self._next_open, now)
        down_due = self._event_due(self._next_close, now)

        brightness = _float_state(self.hass, self.config.get(CONF_BRIGHTNESS_SENSOR))
        sun_state = self.hass.states.get("sun.sun")
        sun_elevation = sun_state and sun_state.attributes.get("elevation")
        sun_azimuth = sun_state and sun_state.attributes.get("azimuth")

        if self._is_resident_sleeping():
            await self._set_position(
                self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                "resident_asleep",
            )
            return

        if self._auto_enabled(CONF_AUTO_VENTILATE) and self._is_window_open():
            if not self._manual_blocks_action("ventilation"):
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

        if self._auto_enabled(CONF_AUTO_SHADING) and not self._manual_blocks_action("shading"):
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
                    if not self._manual_blocks_action("close"):
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
                    if not self._manual_blocks_action("open"):
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
                if not self._manual_blocks_action("close"):
                    await self._set_position(
                        self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                        "sun_close",
                    )
                    return

        time_window_open = self._within_open_close_window(now)
        sun_open_enabled = self._auto_enabled(CONF_AUTO_SUN)
        sun_allows_open = sun_open_enabled and self._sun_allows_open(sun_elevation)

        if self._auto_enabled(CONF_AUTO_UP) and (up_due or time_window_open or sun_allows_open):
            brightness_allows_open = self._brightness_allows_open(brightness)
            if brightness_allows_open and (sun_allows_open or not sun_open_enabled):
                if not self._manual_blocks_action("open"):
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
                if not self._manual_blocks_action("close"):
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
            fallback = DEFAULT_TIME_UP_WORKDAY if is_up else DEFAULT_TIME_DOWN_WORKDAY
        else:
            value_key = CONF_TIME_UP_NON_WORKDAY if is_up else CONF_TIME_DOWN_NON_WORKDAY
            fallback = (
                DEFAULT_TIME_UP_NON_WORKDAY if is_up else DEFAULT_TIME_DOWN_NON_WORKDAY
            )

        parsed = _parse_time(self.config.get(value_key))
        if parsed:
            return parsed
        return _parse_time(fallback)

    def _within_open_close_window(self, now: datetime) -> bool:
        workday = self._is_workday()
        open_time = self._time_setting(workday, True)
        close_time = self._time_setting(workday, False)
        if not open_time or not close_time:
            return False

        local_now = dt_util.as_local(now)

        def _window_for(date_value) -> tuple[datetime, datetime]:
            start = datetime.combine(date_value, open_time, local_now.tzinfo)
            end = datetime.combine(date_value, close_time, local_now.tzinfo)
            if end <= start:
                end = end + timedelta(days=1)
            return start, end

        for offset in (0, -1):
            start, end = _window_for(local_now.date() + timedelta(days=offset))
            if start <= local_now < end:
                return True
        return False


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

    def _normalize_position(self, value: float | int | None, default: float) -> float:
        try:
            position = float(value)
        except (TypeError, ValueError):
            position = default
        return max(0.0, min(100.0, position))

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

        sun_enabled = self._auto_enabled(CONF_AUTO_SUN)
        if sun_enabled:
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
        if not sun_enabled:
            if self._auto_enabled(CONF_AUTO_UP) and next_up:
                candidates_open.append(next_up)
            if self._auto_enabled(CONF_AUTO_DOWN) and next_down:
                candidates_close.append(next_down)
        self._next_open = min(candidates_open) if candidates_open else None
        self._next_close = min(candidates_close) if candidates_close else None

        # Ensure timestamp sensors have a concrete value even if dispatcher
        # events have not yet run or if an automation toggle briefly disabled
        # schedule collection.
        if not sun_enabled and self._next_open is None:
            fallback_open = self._next_time_for_point(self._time_setting(workday, True), now)
            if fallback_open:
                self._next_open = fallback_open
        if not sun_enabled and self._next_close is None:
            fallback_close = self._next_time_for_point(self._time_setting(workday, False), now)
            if fallback_close:
                self._next_close = fallback_close
        
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
        shading_active = self._shading_is_active(current_position, shading_enabled)
        ventilation_active = self._ventilation_is_active(current_position)
        async_dispatcher_send(
            self.hass,
            SIGNAL_STATE_UPDATED,
            self.entry.entry_id,
            self.cover,
            self._target,
            self._reason or IDLE_REASON,
            self._manual_until,
            self._manual_active,
            self._next_open,
            self._next_close,
            current_position,
            shading_enabled,
            shading_active,
            ventilation_active,
        )

    def _position_matches(self, target: float | None, current: float | None) -> bool:
        if target is None or current is None:
            return False
        tolerance = float(self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE))
        return abs(current - float(target)) <= tolerance

    def _shading_is_active(self, current_position: float | None, shading_enabled: bool) -> bool:
        if not shading_enabled:
            return False
        if self._reason not in {"shading", "manual_shading"}:
            return False
        shading_target = self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION)
        return self._position_matches(shading_target, current_position)

    def _ventilation_is_active(self, current_position: float | None) -> bool:
        if self._reason != "ventilation":
            return False
        vent_target = self._position_value(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION)
        return self._position_matches(vent_target, current_position)

    async def _command_position(self, position: float) -> None:
        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": self.cover, "position": float(position)},
            blocking=True,
        )

    async def _wait_for_position(
        self, target: float, tolerance: float, timeout: int = 60
    ) -> None:
        end = dt_util.utcnow() + timedelta(seconds=timeout)
        while dt_util.utcnow() < end:
            current = self._current_position()
            if current is not None and abs(current - target) <= tolerance:
                return
            await asyncio.sleep(1)
