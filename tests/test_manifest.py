"""The manifest is what Home Assistant reads before any of our code runs."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path("custom_components/apparent_temperature/manifest.json")


def test_manifest_declares_a_loadable_helper() -> None:
    manifest = json.loads(MANIFEST.read_text())

    assert manifest["domain"] == "apparent_temperature"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "helper"
    assert manifest["iot_class"] == "calculated"
    # Declared because sources.py imports homeassistant.components.group.sensor.
    assert manifest["dependencies"] == ["group"]
    # Custom components are rejected by HACS and by HA without a version.
    assert manifest["version"]
