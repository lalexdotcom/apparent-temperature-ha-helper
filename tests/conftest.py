"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Load custom_components/ in every test.

    Home Assistant ignores custom components in tests unless this fixture is
    requested, and forgetting it produces an "Integration not found" error that
    looks like a bug in the integration rather than in the test setup.
    """
    yield
