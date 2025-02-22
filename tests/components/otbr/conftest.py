"""Test fixtures for the Home Assistant SkyConnect integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import otbr

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {"url": "http://core-silabs-multiprotocol:8081"}


@pytest.fixture(name="thread_config_entry")
async def thread_config_entry_fixture(hass):
    """Mock Thread config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=otbr.DOMAIN,
        options={},
        title="Thread",
    )
    config_entry.add_to_hass(hass)
    with patch("python_otbr_api.OTBR.get_active_dataset_tlvs"):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
