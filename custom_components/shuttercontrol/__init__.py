"""Home Assistant integration for automated shutter control."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_sunrise, async_track_sunset
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_REASON,
    ATTR_TARGET,
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
    DOMAIN,
    SERVICE_MOVE_COVERS,
    SERVICE_RECALCULATE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ShutterProfile:
    """Configuration for a single cover entity."""

    entity_id: str
    name: str | None
    open_position: int
    close_position: int
    sunrise_offset: int
    sunset_offset: int
    room: str | None
    window_sensors: list[str]


class ShutterController:
    """Handle automation logic for configured shutters."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        profiles: list[ShutterProfile],
        presence_entity: str | None,
        weather_entity: str | None,
        wind_speed_limit: float | None,
        manual_override: bool,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.profiles = profiles
        self.presence_entity = presence_entity
        self.weather_entity = weather_entity
        self.wind_speed_limit = wind_speed_limit
        self.manual_override = manual_override
        self._sun_callbacks: list[Callable[[], None]] = []

    async def async_start(self) -> None:
        """Initialize listeners for sunrise and sunset."""

        await self.async_stop()
        for profile in self.profiles:
            sunrise_offset = timedelta(minutes=profile.sunrise_offset)
            sunset_offset = timedelta(minutes=profile.sunset_offset)

            self._sun_callbacks.append(
                async_track_sunrise(
                    self.hass,
                    lambda _now, p=profile: self._async_handle_sunrise(p),
                    offset=sunrise_offset,
                )
            )
            self._sun_callbacks.append(
                async_track_sunset(
                    self.hass,
                    lambda _now, p=profile: self._async_handle_sunset(p),
                    offset=sunset_offset,
                )
            )

        _LOGGER.debug("Registered %s sun callbacks", len(self._sun_callbacks))

    async def async_stop(self) -> None:
        """Remove all scheduled callbacks."""

        while self._sun_callbacks:
            cancel = self._sun_callbacks.pop()
            cancel()

    async def async_recalculate(self) -> None:
        """Re-schedule callbacks after configuration changes."""

        await self.async_start()

    async def async_move_covers(self, target: str) -> None:
        """Move all covers to the requested state immediately."""

        for profile in self.profiles:
            if target == "open":
                await self._async_move_cover(profile, profile.open_position, "manual")
            elif target == "close":
                await self._async_move_cover(profile, profile.close_position, "manual")

    async def _async_handle_sunrise(self, profile: ShutterProfile) -> None:
        await self._async_move_cover(profile, profile.open_position, "sunrise")

    async def _async_handle_sunset(self, profile: ShutterProfile) -> None:
        await self._async_move_cover(profile, profile.close_position, "sunset")

    async def _async_move_cover(
        self, profile: ShutterProfile, position: int, reason: str
    ) -> None:
        if self.manual_override:
            _LOGGER.debug(
                "Manual override enabled; skipping automation for %s", profile.entity_id
            )
            return

        if self.presence_entity:
            state = self.hass.states.get(self.presence_entity)
            if state and state.state in {"home", "on", "true", "playing"}:
                _LOGGER.debug(
                    "Presence detected via %s; keeping %s untouched",
                    self.presence_entity,
                    profile.entity_id,
                )
                return

        if self.weather_entity and self.wind_speed_limit is not None:
            weather_state = self.hass.states.get(self.weather_entity)
            if weather_state:
                wind_speed = weather_state.attributes.get("wind_speed")
                if wind_speed is not None and wind_speed >= self.wind_speed_limit:
                    _LOGGER.warning(
                        "Wind speed %.1f exceeds limit %.1f; opening %s to safe position",
                        wind_speed,
                        self.wind_speed_limit,
                        profile.entity_id,
                    )
                    position = 50

        if profile.window_sensors and position < profile.open_position:
            open_states = {"on", "open", "opening", "true", "1"}
            for sensor in profile.window_sensors:
                sensor_state = self.hass.states.get(sensor)
                if sensor_state and sensor_state.state in open_states:
                    _LOGGER.warning(
                        "Window sensor %s reports open; skipping close for %s in room %s",
                        sensor,
                        profile.entity_id,
                        profile.room,
                    )
                    return

        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {ATTR_ENTITY_ID: profile.entity_id, "position": position},
            blocking=False,
        )
        _LOGGER.info(
            "Moved %s to %s%% because of %s", profile.entity_id, position, reason
        )


@callback
def _build_profiles(entry: ConfigEntry) -> list[ShutterProfile]:
    covers: list[dict[str, Any]] = entry.options.get(
        CONF_COVERS, entry.data.get(CONF_COVERS, [])
    )
    profiles: list[ShutterProfile] = []
    for cover in covers:
        profiles.append(
            ShutterProfile(
                entity_id=cover[ATTR_ENTITY_ID],
                name=cover.get(CONF_NAME),
                open_position=cover.get(CONF_OPEN_POSITION),
                close_position=cover.get(CONF_CLOSE_POSITION),
                sunrise_offset=cover.get(CONF_SUNRISE_OFFSET),
                sunset_offset=cover.get(CONF_SUNSET_OFFSET),
                room=cover.get(CONF_ROOM),
                window_sensors=cover.get(CONF_WINDOW_SENSORS, []),
            )
        )
    return profiles


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration namespace."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shutter Control from a config entry."""

    profiles = _build_profiles(entry)
    controller = ShutterController(
        hass=hass,
        entry=entry,
        profiles=profiles,
        presence_entity=entry.options.get(
            CONF_PRESENCE_ENTITY, entry.data.get(CONF_PRESENCE_ENTITY)
        ),
        weather_entity=entry.options.get(
            CONF_WEATHER_ENTITY, entry.data.get(CONF_WEATHER_ENTITY)
        ),
        wind_speed_limit=entry.options.get(
            CONF_WIND_SPEED_LIMIT, entry.data.get(CONF_WIND_SPEED_LIMIT)
        ),
        manual_override=entry.options.get(
            CONF_MANUAL_OVERRIDE, entry.data.get(CONF_MANUAL_OVERRIDE, False)
        ),
    )

    await controller.async_start()
    hass.data[DOMAIN][entry.entry_id] = controller

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECALCULATE,
        lambda call: hass.async_create_task(controller.async_recalculate()),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MOVE_COVERS,
        lambda call: hass.async_create_task(
            controller.async_move_covers(call.data.get(ATTR_TARGET, "open"))
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Shutter Control."""

    controller: ShutterController | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if controller:
        await controller.async_stop()

    return True
