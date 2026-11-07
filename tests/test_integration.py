"""Exercise actual Home Assistant lifecycle, platforms and command guards."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sunex_nexus.const import DOMAIN, CONF_ALLOW_WRITES
from custom_components.sunex_nexus.protocol import ProtocolError
from custom_components.sunex_nexus.protocol.registers import decode


def snapshot():
    raw = dict.fromkeys([*range(271), *range(0x8000, 0x802B)], 0)
    raw.update({4: 1, 0x8F: 45, 0x90: 12, 0x91: 35, 0x800E: 312, 0x8012: 83})
    return {"raw": raw, "decoded": decode(raw), "received_at": datetime.now(timezone.utc)}


@pytest.fixture
def transport():
    with patch("custom_components.sunex_nexus.coordinator.NexusTransport") as factory:
        client = factory.return_value
        client.close = AsyncMock()
        client.set_setpoint = AsyncMock()
        client.change_operating = AsyncMock()
        client.change_parameter = AsyncMock()
        yield client


@pytest.fixture
def reading():
    with patch("custom_components.sunex_nexus.coordinator.read_snapshot", new_callable=AsyncMock) as read:
        read.return_value = snapshot()
        yield read


async def setup(hass, *, writes=False):
    entry = MockConfigEntry(domain=DOMAIN, title="SUNEX NEXUS", unique_id="gateway.test:10003",
                            data={CONF_HOST: "gateway.test", CONF_PORT: 10003},
                            options={CONF_ALLOW_WRITES: writes})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass, entry, platform, key):
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


async def test_lifecycle_all_entities_no_startup_write(hass, transport, reading):
    entry = await setup(hass)
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entries) > 570
    assert hass.states.get(entity_id(hass, entry, "sensor", "water_inlet_temperature")).state == "31.2"
    assert hass.states.get(entity_id(hass, entry, "number", "heating_setpoint")).state == "35"
    raw = next(e for e in entries if e.unique_id.endswith("raw_800e"))
    assert raw.disabled_by is not None
    transport.set_setpoint.assert_not_called()
    transport.change_operating.assert_not_called()
    transport.change_parameter.assert_not_called()
    assert await hass.config_entries.async_unload(entry.entry_id)
    transport.close.assert_awaited_once()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_write_off_by_default(hass, transport, reading):
    entry = await setup(hass)
    with pytest.raises(HomeAssistantError, match="Writes disabled"):
        await entry.runtime_data.async_command("setpoint", "heating", 38)
    transport.set_setpoint.assert_not_called()


async def test_setpoint_via_real_entity_service(hass, transport, reading):
    entry = await setup(hass, writes=True)
    new = snapshot()
    new["raw"][145] = 38
    new["decoded"] = decode(new["raw"])
    reading.return_value = new
    await hass.services.async_call("number", "set_value", {
        "entity_id": entity_id(hass, entry, "number", "heating_setpoint"), "value": 38}, blocking=True)
    transport.set_setpoint.assert_awaited_once_with("heating", 38.0, expected=35)
    assert not entry.runtime_data.write_locked
    assert hass.states.get(entity_id(hass, entry, "number", "heating_setpoint")).state == "38"


async def test_failed_write_locks_reload_and_acknowledges_without_replay(hass, transport, reading):
    entry = await setup(hass, writes=True)
    transport.set_setpoint.side_effect = ProtocolError("Unknown write outcome")
    with pytest.raises(HomeAssistantError, match="not confirmed"):
        await entry.runtime_data.async_command("setpoint", "heating", 38)
    assert entry.runtime_data.write_locked
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.write_locked
    with pytest.raises(HomeAssistantError):
        await entry.runtime_data.async_command("setpoint", "heating", 38)
    await entry.runtime_data.async_acknowledge()
    assert not entry.runtime_data.write_locked
    transport.set_setpoint.assert_awaited_once()


async def test_poll_failure_entities_unavailable_then_recover(hass, transport, reading):
    entry = await setup(hass)
    coordinator = entry.runtime_data
    reading.side_effect = ProtocolError("No response")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert hass.states.get(entity_id(hass, entry, "sensor", "water_inlet_temperature")).state == "unavailable"
    reading.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_initial_failure_closes_transport(hass, transport, reading):
    reading.side_effect = ProtocolError("Offline")
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "gateway.test", CONF_PORT: 10003})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    transport.close.assert_awaited_once()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_service_window_and_guard(hass, transport, reading):
    entry = await setup(hass, writes=True)
    coordinator = entry.runtime_data
    from custom_components.sunex_nexus.protocol.catalog import CATALOG
    row = next(r for r in CATALOG if r["access"] == "service")
    with pytest.raises(HomeAssistantError, match="Service editing"):
        await coordinator.async_command("parameter", row["address"], row["bounds"][0])
    await coordinator.async_service_edit(True)
    assert coordinator.service_allowed
    coordinator.data["decoded"]["compressor_running"] = True
    assert not coordinator.service_allowed
    with pytest.raises(HomeAssistantError):
        await coordinator.async_service_edit(True)
    transport.change_parameter.assert_not_called()


async def test_stale_readings_and_budget_reject(hass, transport, reading):
    entry = await setup(hass, writes=True)
    c = entry.runtime_data
    c.last_success -= 100
    with pytest.raises(HomeAssistantError, match="Fresh"):
        await c.async_command("setpoint", "heating", 38)
    await c.async_refresh()
    import time
    c.writes = [time.time()] * 48
    with pytest.raises(HomeAssistantError, match="budget"):
        await c.async_command("setpoint", "heating", 38)
    transport.set_setpoint.assert_not_called()


async def test_diagnostics_redacts_endpoint(hass, transport, reading):
    from custom_components.sunex_nexus.diagnostics import async_get_config_entry_diagnostics
    entry = await setup(hass)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert "gateway.test" not in str(result)
    assert entry.entry_id not in str(result)


async def test_flow_exclusive_required_without_network(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    with patch("custom_components.sunex_nexus.config_flow.NexusTransport") as factory:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            CONF_HOST: "gateway.test", CONF_PORT: 10003, "exclusive_gateway": False})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "exclusive_required"}
        factory.assert_not_called()


async def test_flow_success_and_duplicate(hass):
    data = {CONF_HOST: "gateway.test", CONF_PORT: 10003, "exclusive_gateway": True}
    with patch("custom_components.sunex_nexus.config_flow.NexusTransport") as factory, \
         patch("custom_components.sunex_nexus.config_flow.read_snapshot", new_callable=AsyncMock), \
         patch("custom_components.sunex_nexus.async_setup_entry", return_value=True):
        factory.return_value.close = AsyncMock()
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=data)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        factory.return_value.close.assert_awaited_once()
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=data)
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_offline(hass):
    with patch("custom_components.sunex_nexus.config_flow.NexusTransport") as factory, \
         patch("custom_components.sunex_nexus.config_flow.read_snapshot", side_effect=ProtocolError("Offline")):
        factory.return_value.close = AsyncMock()
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data={
            CONF_HOST: "gateway.test", CONF_PORT: 10003, "exclusive_gateway": True})
        assert result["errors"] == {"base": "cannot_connect"}
        factory.return_value.close.assert_awaited_once()


async def test_noop_does_not_use_write_budget(hass, transport, reading):
    entry = await setup(hass, writes=True)
    await entry.runtime_data.async_command("setpoint", "heating", 35)
    assert entry.runtime_data.writes == []
    transport.set_setpoint.assert_not_called()


async def test_storage_failure_prevents_transmission(hass, transport, reading):
    entry = await setup(hass, writes=True)
    with patch.object(entry.runtime_data.store, "async_save", side_effect=OSError("Disk unavailable")):
        with pytest.raises(OSError):
            await entry.runtime_data.async_command("setpoint", "heating", 38)
    assert entry.runtime_data.write_locked
    transport.set_setpoint.assert_not_called()


async def test_failed_acknowledgement_retains_lock(hass, transport, reading):
    entry = await setup(hass, writes=True)
    entry.runtime_data.write_locked = True
    reading.side_effect = ProtocolError("Offline")
    with pytest.raises(HomeAssistantError, match="lock retained"):
        await entry.runtime_data.async_acknowledge()
    assert entry.runtime_data.write_locked


async def test_service_window_expires(hass, transport, reading):
    entry = await setup(hass, writes=True)
    await entry.runtime_data.async_service_edit(True)
    assert entry.runtime_data.service_allowed
    entry.runtime_data.service_until -= 601
    assert not entry.runtime_data.service_allowed


async def test_operating_services_use_shared_transaction(hass, transport, reading):
    entry = await setup(hass, writes=True)
    await hass.services.async_call("switch", "turn_on", {
        "entity_id": entity_id(hass, entry, "switch", "silent")}, blocking=True)
    transport.change_operating.assert_awaited_once_with("silent", 1, expected=0)


async def test_options_reload_does_not_write(hass, transport, reading):
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "allow_writes": True, "poll_interval": 45})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.writes_allowed
    assert entry.runtime_data.update_interval.total_seconds() == 45
    transport.set_setpoint.assert_not_called()
    transport.change_operating.assert_not_called()


async def test_complete_bank_read_and_profile_rejection():
    from custom_components.sunex_nexus.coordinator import read_snapshot
    from custom_components.sunex_nexus.protocol import RegisterSnapshot
    raw = snapshot()["raw"]
    async def read(address, count):
        return RegisterSnapshot(address, tuple(raw[a] for a in range(address, address + count)),
                                datetime.now(timezone.utc))
    client = AsyncMock()
    client.read.side_effect = read
    result = await read_snapshot(client)
    assert len(result["raw"]) == 314
    assert result["decoded"]["water_inlet_temperature"] == 31.2
    raw[4] = 99
    with pytest.raises(ProtocolError, match="not compatible"):
        await read_snapshot(client)
