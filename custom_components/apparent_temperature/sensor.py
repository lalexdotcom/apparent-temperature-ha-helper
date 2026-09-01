"""The apparent temperature sensor entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_FORMULA
from .formulas import compute
from .sources import InputResolver

_LOGGER = logging.getLogger(__name__)

ATTR_INDEX_VALUE = "index_value"
ATTR_FORMULA = "formula"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the helper's single sensor."""
    async_add_entities([ApparentTemperatureSensor(hass, entry)])


class ApparentTemperatureSensor(SensorEntity):
    """Perceived temperature derived from three resolved quantities."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise from the config entry's options."""
        self._attr_name = entry.options[CONF_NAME]
        self._attr_unique_id = entry.entry_id
        self._mode: str = entry.options[CONF_FORMULA]
        self._resolver = InputResolver(hass, entry.options)
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Subscribe to every source and compute a first value."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._resolver.tracked_entity_ids, self._handle_change
            )
        )
        self._recalculate()

    @callback
    def _handle_change(self, _event: Event[EventStateChangedData]) -> None:
        """Recompute when any source changes."""
        self._recalculate()
        self.async_write_ha_state()

    @callback
    def _recalculate(self) -> None:
        """Resolve the inputs, apply the formula, publish the attributes."""
        inputs = self._resolver.resolve()
        attributes: dict[str, Any] = {
            "temperature": inputs.temperature.value,
            "temperature_source": inputs.temperature.source,
            "humidity": inputs.humidity.value,
            "humidity_source": inputs.humidity.source,
            "wind_speed": inputs.wind_speed.value,
            "wind_speed_source": inputs.wind_speed.source,
        }

        if inputs.temperature.value is None:
            # Without a temperature there is nothing to derive anything from.
            # The sensor stays unavailable, and Entity only merges
            # extra_state_attributes into the state when available, so there
            # is no point assembling formula/index_value attributes here.
            self._attr_available = False
            self._attr_native_value = None
            return

        try:
            result = compute(
                self._mode,
                inputs.temperature.value,
                inputs.humidity.value,
                inputs.wind_speed.value,
            )
        except Exception:
            # A formula fault must not freeze the sensor on its last good
            # value: go visibly unavailable instead of silently going stale.
            _LOGGER.exception("Failed to compute the apparent temperature")
            self._attr_available = False
            self._attr_native_value = None
            return

        self._attr_available = True
        self._attr_native_value = result.value
        # The state is converted for display by Home Assistant; index_value
        # keeps the number the formula actually produced.
        attributes[ATTR_INDEX_VALUE] = result.value
        attributes[ATTR_FORMULA] = result.formula
        self._attr_extra_state_attributes = attributes
