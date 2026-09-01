"""The apparent temperature sensor entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_FORMULA,
    DOMAIN,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
)
from .formulas import compute
from .sources import InputResolver, ResolvedInputs

_LOGGER = logging.getLogger(__name__)

ATTR_INDEX_VALUE = "index_value"
ATTR_FORMULA = "formula"


ATTR_SOURCE = "source"

# One entity per quantity the formula consumes, in the canonical unit the
# resolver produces. They are registered disabled: most installations only
# want the perceived temperature, and an unwanted entity is harder to get rid
# of than a disabled one is to switch on.
MEASUREMENTS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SECTION_TEMPERATURE,
        translation_key=SECTION_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=SECTION_HUMIDITY,
        translation_key=SECTION_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=SECTION_WIND_SPEED,
        translation_key=SECTION_WIND_SPEED,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
)


class SourceHub:
    """Resolves the three quantities once per source change.

    Every entity of the entry reads the same resolution: without the hub each
    one would run its own three group aggregations on every state change.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._resolver = InputResolver(hass, entry.options)
        self._listeners: list[CALLBACK_TYPE] = []
        self.inputs: ResolvedInputs = self._resolver.resolve()

    @callback
    def async_subscribe(self) -> CALLBACK_TYPE:
        """Track every source; returns the unsubscribe callback."""
        return async_track_state_change_event(
            self._hass, self._resolver.tracked_entity_ids, self._handle_change
        )

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register an entity's update callback and return its remover."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _handle_change(self, _event: Event[EventStateChangedData]) -> None:
        """Re-resolve, then let every entity publish its own view of it."""
        self.inputs = self._resolver.resolve()
        for listener in self._listeners:
            listener()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the apparent temperature sensor and its three inputs."""
    hub = SourceHub(hass, entry)
    entry.async_on_unload(hub.async_subscribe())
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.options[CONF_NAME],
        entry_type=DeviceEntryType.SERVICE,
    )
    async_add_entities(
        [
            ApparentTemperatureSensor(entry, hub, device_info),
            *(
                SourceMeasurementSensor(entry, hub, description, device_info)
                for description in MEASUREMENTS
            ),
        ]
    )


class ApparentTemperatureSensor(SensorEntity):
    """Perceived temperature derived from three resolved quantities."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_should_poll = False
    # The device carries the helper's name, and this entity carries no name of
    # its own, so its displayed name stays the helper's — as it was before the
    # device existed.
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry, hub: SourceHub, device_info: DeviceInfo) -> None:
        """Initialise from the config entry's options."""
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = device_info
        self._mode: str = entry.options[CONF_FORMULA]
        self._hub = hub
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Follow the hub and compute a first value."""
        await super().async_added_to_hass()
        self.async_on_remove(self._hub.async_add_listener(self._handle_change))
        self._recalculate()

    @callback
    def _handle_change(self) -> None:
        """Recompute when any source changes."""
        self._recalculate()
        self.async_write_ha_state()

    @callback
    def _recalculate(self) -> None:
        """Apply the formula to the hub's inputs, publish the attributes."""
        inputs = self._hub.inputs
        attributes: dict[str, Any] = {
            SECTION_TEMPERATURE: inputs.temperature.value,
            SECTION_HUMIDITY: inputs.humidity.value,
            SECTION_WIND_SPEED: inputs.wind_speed.value,
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


class SourceMeasurementSensor(SensorEntity):
    """One resolved input, exactly as the formula received it."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        hub: SourceHub,
        description: SensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the entity for one quantity."""
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info
        self._hub = hub

    async def async_added_to_hass(self) -> None:
        """Follow the hub and publish a first value."""
        await super().async_added_to_hass()
        self.async_on_remove(self._hub.async_add_listener(self._handle_change))
        self._recalculate()

    @callback
    def _handle_change(self) -> None:
        """Republish when any source changes."""
        self._recalculate()
        self.async_write_ha_state()

    @callback
    def _recalculate(self) -> None:
        """Read this entity's quantity out of the hub's last resolution."""
        quantity = self._hub.inputs.quantity(self.entity_description.key)
        self._attr_available = quantity.value is not None
        self._attr_native_value = quantity.value
        # An unavailable state carries no attributes anyway, so there is
        # nothing to say about a source that does not exist.
        self._attr_extra_state_attributes = {ATTR_SOURCE: quantity.source}
