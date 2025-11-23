"""Create helper entities used to configure automation parameters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components import input_boolean, input_datetime, input_number
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

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
    CONF_CLOSE_POSITION,
    CONF_CLOSE_POSITION_ENTITY,
    CONF_OPEN_POSITION,
    CONF_OPEN_POSITION_ENTITY,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ENTITY,
    CONF_TIME_DOWN_NON_WORKDAY,
    CONF_TIME_DOWN_NON_WORKDAY_ENTITY,
    CONF_TIME_DOWN_WORKDAY,
    CONF_TIME_DOWN_WORKDAY_ENTITY,
    CONF_TIME_UP_NON_WORKDAY,
    CONF_TIME_UP_NON_WORKDAY_ENTITY,
    CONF_TIME_UP_WORKDAY,
    CONF_TIME_UP_WORKDAY_ENTITY,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATE_POSITION_ENTITY,
)


@dataclass
class _NumberSpec:
    key: str
    entity_key: str
    default: float
    min_value: float
    max_value: float
    step: float
    unit: str | None = None


@dataclass
class _BooleanSpec:
    key: str
    entity_key: str
    default: bool


@dataclass
class _TimeSpec:
    key: str
    entity_key: str
    default: str


NUMBER_SPECS: tuple[_NumberSpec, ...] = (
    _NumberSpec(CONF_OPEN_POSITION, CONF_OPEN_POSITION_ENTITY, 100, 0, 100, 1, PERCENTAGE),
    _NumberSpec(CONF_CLOSE_POSITION, CONF_CLOSE_POSITION_ENTITY, 0, 0, 100, 1, PERCENTAGE),
    _NumberSpec(CONF_VENTILATE_POSITION, CONF_VENTILATE_POSITION_ENTITY, 50, 0, 100, 1, PERCENTAGE),
    _NumberSpec(CONF_SHADING_POSITION, CONF_SHADING_POSITION_ENTITY, 30, 0, 100, 1, PERCENTAGE),
)


BOOLEAN_SPECS: tuple[_BooleanSpec, ...] = (
    _BooleanSpec(CONF_AUTO_UP, CONF_AUTO_UP_ENTITY, True),
    _BooleanSpec(CONF_AUTO_DOWN, CONF_AUTO_DOWN_ENTITY, True),
    _BooleanSpec(CONF_AUTO_BRIGHTNESS, CONF_AUTO_BRIGHTNESS_ENTITY, True),
    _BooleanSpec(CONF_AUTO_SUN, CONF_AUTO_SUN_ENTITY, True),
    _BooleanSpec(CONF_AUTO_VENTILATE, CONF_AUTO_VENTILATE_ENTITY, True),
    _BooleanSpec(CONF_AUTO_COLD, CONF_AUTO_COLD_ENTITY, False),
    _BooleanSpec(CONF_AUTO_SHADING, CONF_AUTO_SHADING_ENTITY, True),
    _BooleanSpec(CONF_AUTO_WIND, CONF_AUTO_WIND_ENTITY, True),
)


TIME_SPECS: tuple[_TimeSpec, ...] = (
    _TimeSpec(CONF_TIME_UP_WORKDAY, CONF_TIME_UP_WORKDAY_ENTITY, "06:00:00"),
    _TimeSpec(CONF_TIME_UP_NON_WORKDAY, CONF_TIME_UP_NON_WORKDAY_ENTITY, "07:30:00"),
    _TimeSpec(CONF_TIME_DOWN_WORKDAY, CONF_TIME_DOWN_WORKDAY_ENTITY, "18:00:00"),
    _TimeSpec(CONF_TIME_DOWN_NON_WORKDAY, CONF_TIME_DOWN_NON_WORKDAY_ENTITY, "18:30:00"),
)


async def _create_if_missing(
    hass: HomeAssistant, entity_id: str | None, factory: Callable[[], Any]
) -> str:
    if entity_id:
        return entity_id
    created = await factory()
    return created["entity_id"] if isinstance(created, dict) else created


async def ensure_config_entities(hass: HomeAssistant, entry_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Create helper entities for configurable parameters if they are missing."""

    updated: dict[str, Any] = {}

    for spec in NUMBER_SPECS:
        current_entity = data.get(spec.entity_key)
        initial_value = data.get(spec.key, spec.default)

        async def _make_number(name=spec.entity_key, initial=initial_value, spec_obj=spec):
            return await input_number.async_create_input_number(
                hass,
                f"Shutter {name}",
                initial=initial,
                minimum=spec_obj.min_value,
                maximum=spec_obj.max_value,
                step=spec_obj.step,
                unit_of_measurement=spec_obj.unit,
                icon=None,
                mode=input_number.MODE_SLIDER,
                unique_id=f"{entry_id}-{name}",
            )

        updated[spec.entity_key] = await _create_if_missing(hass, current_entity, _make_number)

    for spec in BOOLEAN_SPECS:
        current_entity = data.get(spec.entity_key)
        initial_value = data.get(spec.key, spec.default)

        async def _make_boolean(name=spec.entity_key, initial=initial_value, spec_obj=spec):
            return await input_boolean.async_create_input_boolean(
                hass,
                f"Shutter {name}",
                initial=bool(initial),
                icon=None,
                unique_id=f"{entry_id}-{name}",
            )

        updated[spec.entity_key] = await _create_if_missing(hass, current_entity, _make_boolean)

    for spec in TIME_SPECS:
        current_entity = data.get(spec.entity_key)
        initial_value = data.get(spec.key, spec.default)

        async def _make_time(name=spec.entity_key, initial=initial_value):
            return await input_datetime.async_create_input_datetime(
                hass,
                f"Shutter {name}",
                has_date=False,
                has_time=True,
                initial=initial,
                icon=None,
                unique_id=f"{entry_id}-{name}",
            )

        updated[spec.entity_key] = await _create_if_missing(hass, current_entity, _make_time)

    return updated
