"""One transport owner, atomic snapshots and explicit, durable command guards."""
import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ALLOW_WRITES, CONF_INTERVAL, DEFAULT_INTERVAL, DOMAIN, OPERATING_FIELDS
from .protocol import NexusTransport, ProtocolError
from .protocol.catalog import encode_parameter
from .protocol.registers import MODES, SETPOINTS, decode

_LOGGER = logging.getLogger(__name__)


async def read_snapshot(transport):
    """Do not publish a partially refreshed register bank."""
    raw = {}
    for address, count in ((0, 120), (120, 120), (240, 31), (0x8000, 43)):
        result = await transport.read(address, count)
        raw.update(enumerate(result.values, address))
    data = decode(raw)
    if data["mode"] is None or any(data[key + "_setpoint"] is None for key in SETPOINTS):
        raise ProtocolError("Register map is not compatible with the supported M-EVI profile")
    return {"raw": raw, "decoded": data, "received_at": result.received_at}


class NexusCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)))
        self.entry = entry
        self.transport = NexusTransport(entry.data[CONF_HOST], entry.data[CONF_PORT])
        self.command_lock = asyncio.Lock()
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.commands")
        self.write_locked = False
        self.writes = []
        self.service_until = 0.0
        self.last_success = float("-inf")

    async def async_initialize(self):
        saved = await self.store.async_load()
        if saved:
            self.write_locked = bool(saved.get("pending", False))
            self.writes = saved.get("writes", [])

    async def _save(self):
        await self.store.async_save({"pending": self.write_locked, "writes": self.writes})

    @property
    def writes_allowed(self):
        return self.entry.options.get(CONF_ALLOW_WRITES, False)

    @property
    def service_allowed(self):
        data = self.data["decoded"] if self.data else {}
        return (self.writes_allowed and not self.write_locked and self.last_update_success
                and time.monotonic() < self.service_until
                and data.get("enabled") is False and data.get("compressor_running") is False)

    async def _async_update_data(self):
        async with self.command_lock:
            try:
                result = await read_snapshot(self.transport)
            except (ProtocolError, OSError, ValueError) as exc:
                raise UpdateFailed("Cannot read a complete SUNEX M-EVI snapshot") from exc
            self.last_success = time.monotonic()
            return result

    def _require_fresh(self):
        if not self.last_update_success or time.monotonic() - self.last_success > 90:
            raise HomeAssistantError("Fresh device readings are required")

    async def async_service_edit(self, enabled):
        async with self.command_lock:
            self._require_fresh()
            if enabled:
                data = self.data["decoded"]
                if not self.writes_allowed or self.write_locked or data["enabled"] or data["compressor_running"]:
                    raise HomeAssistantError("Enable writes and stop the unit and compressor before service editing")
            self.service_until = time.monotonic() + 600 if enabled else 0
        self.async_update_listeners()

    async def async_acknowledge(self):
        """Operator acknowledgement only, after a successful complete reread."""
        async with self.command_lock:
            try:
                snapshot = await read_snapshot(self.transport)
            except (ProtocolError, OSError, ValueError) as exc:
                raise HomeAssistantError("Cannot verify device state; write lock retained") from exc
            self.last_success = time.monotonic()
            self.write_locked = False
            self.service_until = 0
            await self._save()
            self.async_set_updated_data(snapshot)

    async def async_command(self, kind, key, value):
        async with self.command_lock:
            self._require_fresh()
            if not self.writes_allowed or self.write_locked:
                raise HomeAssistantError("Writes disabled or an uncertain command requires acknowledgement")
            raw = self.data["raw"]
            if kind == "setpoint":
                target = SETPOINTS[key]
                encoded = target.encode(value)
                address = target.address
            elif kind == "parameter":
                if not self.service_allowed:
                    raise HomeAssistantError("Service editing is not enabled")
                address = key
                encoded = encode_parameter(address, value)
            elif kind == "operating":
                if key == "mode":
                    if type(value) is not int or value not in MODES:
                        raise HomeAssistantError("Unsupported operating mode")
                    address, encoded = 4, value
                else:
                    if key not in OPERATING_FIELDS or type(value) is not int or value not in (0, 1):
                        raise HomeAssistantError("Unsupported operating command")
                    address, mask = OPERATING_FIELDS[key]
                    encoded = (raw[address] & ~mask) | (mask if value else 0)
                    if value and key in ("powerful", "silent"):
                        encoded &= ~(32 if key == "powerful" else 16)
            else:
                raise HomeAssistantError("Unsupported command")
            if encoded == raw[address]:
                return
            now = time.time()
            self.writes = [at for at in self.writes if now - at < 86400]
            if len(self.writes) >= 48 or (self.writes and now - self.writes[-1] < 5):
                raise HomeAssistantError("Write budget or minimum write interval reached")
            # Persist before sending: crash/reload cannot silently replay an ambiguous write.
            self.write_locked = True
            self.writes.append(now)
            await self._save()
            try:
                if kind == "setpoint":
                    await self.transport.set_setpoint(key, value, expected=raw[address])
                elif kind == "parameter":
                    await self.transport.change_parameter(address, value, expected=raw[address])
                else:
                    await self.transport.change_operating(key, value, expected=raw[address])
                snapshot = await read_snapshot(self.transport)
            except (ProtocolError, OSError, ValueError) as exc:
                self.service_until = 0
                self.async_set_update_error(UpdateFailed("Command outcome needs manual review"))
                raise HomeAssistantError("Command not confirmed. Inspect the unit; do not repeat blindly") from exc
            finally:
                self.async_update_listeners()
            self.last_success = time.monotonic()
            self.write_locked = False
            await self._save()
            self.async_set_updated_data(snapshot)
