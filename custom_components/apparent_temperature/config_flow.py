"""Config and options flow for the apparent temperature helper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_ENTITIES, CONF_NAME, CONF_TYPE
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_FORMULA,
    CONF_IGNORE_NON_NUMERIC,
    CONF_WEATHER_ENTITY,
    DEFAULT_STATISTIC,
    DOMAIN,
    FORMULA_MODES,
    FORMULA_THRESHOLDS,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
    STATISTIC_TYPES,
)


def _group_schema(device_class: SensorDeviceClass) -> vol.Schema:
    """Build the three fields every source group shares.

    The entity selector filters on the device class, which is also what makes
    unit conversion possible downstream: a sensor with no device class cannot
    be converted, so hiding it here is the honest behaviour.
    """
    return vol.Schema(
        {
            vol.Optional(CONF_ENTITIES, default=list): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class=device_class, multiple=True
                )
            ),
            vol.Required(CONF_TYPE, default=DEFAULT_STATISTIC): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=STATISTIC_TYPES,
                    translation_key=CONF_TYPE,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_IGNORE_NON_NUMERIC, default=False): selector.BooleanSelector(),
        }
    )


# vol.Optional without a default renders a clearable field: the weather entity
# can be removed after the fact, which a default would prevent.
_COMMON: dict[Any, Any] = {
    vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="weather")
    ),
    vol.Required(CONF_FORMULA, default=FORMULA_THRESHOLDS): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=FORMULA_MODES,
            translation_key=CONF_FORMULA,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Required(SECTION_TEMPERATURE): section(
        _group_schema(SensorDeviceClass.TEMPERATURE), {"collapsed": True}
    ),
    vol.Required(SECTION_HUMIDITY): section(
        _group_schema(SensorDeviceClass.HUMIDITY), {"collapsed": True}
    ),
    vol.Required(SECTION_WIND_SPEED): section(
        _group_schema(SensorDeviceClass.WIND_SPEED), {"collapsed": True}
    ),
}

OPTIONS_SCHEMA = vol.Schema(_COMMON)
CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_NAME): selector.TextSelector(), **_COMMON})

CONFIG_FLOW: dict[str, SchemaFlowFormStep] = {"user": SchemaFlowFormStep(CONFIG_SCHEMA)}
OPTIONS_FLOW: dict[str, SchemaFlowFormStep] = {"init": SchemaFlowFormStep(OPTIONS_SCHEMA)}


class ApparentTemperatureConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle the config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Name the entry after what the user typed."""
        return cast(str, options[CONF_NAME])
