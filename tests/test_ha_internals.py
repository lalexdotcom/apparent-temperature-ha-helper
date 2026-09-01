"""Pins the Home Assistant internals this integration depends on.

sources.py builds SensorGroup by hand. Home Assistant makes no API promise for
homeassistant.components.*, so this file exists to fail loudly on the next core
refactor instead of letting the helper drift silently in production.
"""

from __future__ import annotations

import inspect

import pytest
from homeassistant.components.group.sensor import SensorGroup
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant


def test_constructor_signature_is_unchanged() -> None:
    parameters = list(inspect.signature(SensorGroup.__init__).parameters)

    assert parameters == [
        "self",
        "hass",
        "unique_id",
        "name",
        "entity_ids",
        "ignore_non_numeric",
        "sensor_type",
        "unit_of_measurement",
        "state_class",
        "device_class",
    ]


async def test_configured_unit_wins_over_member_units(hass: HomeAssistant) -> None:
    """A configured unit must short-circuit unit negotiation.

    This is what lets members be converted before aggregation. If core ever
    stops honouring it, the helper's means become wrong for non-linear units.
    """
    hass.states.async_set(
        "sensor.a",
        68.0,
        {
            "device_class": "temperature",
            "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
        },
    )

    group = SensorGroup(
        hass,
        None,
        "pin",
        ["sensor.a"],
        False,
        "mean",
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.TEMPERATURE,
    )
    group.async_update_group_state()

    assert group.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert group.native_value == pytest.approx(20.0)
    assert group.available is True


async def test_update_works_without_being_added_to_hass(
    hass: HomeAssistant,
) -> None:
    """The group is never added to hass, so entity_id stays None.

    Core logs a warning naming self.entity_id on a bad member; that must not
    raise. It also must not open a repair issue, which is why the constructor
    receives an explicit device class, state class and unit.
    """
    hass.states.async_set(
        "sensor.broken",
        "not a number",
        {
            "device_class": "temperature",
            "unit_of_measurement": UnitOfTemperature.CELSIUS,
        },
    )

    group = SensorGroup(
        hass,
        None,
        "pin",
        ["sensor.broken"],
        False,
        "mean",
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.TEMPERATURE,
    )
    group.async_update_group_state()

    assert group.native_value is None
