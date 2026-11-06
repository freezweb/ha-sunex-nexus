"""Serialized RTU-over-TCP with bounded, readback-verified setpoint changes."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import time
from typing import ClassVar

from pymodbus import FramerType
from pymodbus.client import AsyncModbusTcpClient
from .registers import SETPOINTS
from .catalog import encode_parameter


class ProtocolError(Exception):
    """An exchange failed or the response did not satisfy the request."""


@dataclass(frozen=True)
class RegisterSnapshot:
    """Raw 16-bit words and their receipt time; never inferred engineering units."""

    address: int
    values: tuple[int, ...]
    received_at: datetime


@dataclass(frozen=True)
class SetpointChange:
    address: int
    previous: int
    requested: int
    changed: bool
    verified_at: datetime


class NexusTransport:
    """One serialized owner per literal gateway endpoint within this process.

    Cross-process exclusivity is a deployment requirement. An external
    controller and Home Assistant must share a transport owner, not instantiate
    independent clients. Hostname aliases must not be used to bypass ownership.
    """

    _owners: ClassVar[dict[tuple[str, int], NexusTransport]] = {}
    REQUEST_GAP = 0.3
    MAX_COUNT = 120
    DEVICE_ID = 1

    def __init__(self, host: str, port: int, *, timeout: float = 4.0):
        if not isinstance(host, str) or not host.strip() or any(c.isspace() for c in host):
            raise ValueError("A gateway hostname is required")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid gateway port")
        if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("Timeout must be positive and at most 60 seconds")
        self._endpoint = (host.rstrip('.').lower(), port)
        self._client = AsyncModbusTcpClient(
            host, port=port, framer=FramerType.RTU, timeout=timeout,
            retries=0, reconnect_delay=0,
        )
        self._lock = asyncio.Lock()
        self._last_finished = float('-inf')
        self._closed = False

    async def _connect_locked(self) -> None:
        if self._closed:
            raise ProtocolError("Transport has been closed")
        owner = self._owners.get(self._endpoint)
        if owner is not None and owner is not self:
            raise ProtocolError("Gateway already owned by another transport")
        self._owners[self._endpoint] = self
        if not self._client.connected and not await self._client.connect():
            raise ProtocolError("Gateway connection failed")

    async def read(self, address: int, count: int = 1) -> RegisterSnapshot:
        """Read FC03, without retries, broadcast, writes or register interpretation."""
        if type(address) is not int or type(count) is not int:
            raise ValueError("Address and count must be integers")
        if not 0 <= address <= 65535 or not 1 <= count <= self.MAX_COUNT or address + count > 65536:
            raise ValueError("Read range exceeds the supported address or count limit")
        async with self._lock:
            return await self._read_locked(address, count)

    async def _exchange_locked(self, function: int, address: int, value: int):
        try:
            await self._connect_locked()
            await asyncio.sleep(max(0.0, self.REQUEST_GAP - (time.monotonic() - self._last_finished)))
            if function == 3:
                response = await self._client.read_holding_registers(address, count=value, device_id=self.DEVICE_ID)
            else:
                response = await self._client.write_register(address, value, device_id=self.DEVICE_ID)
            if response.isError():
                raise ProtocolError(f"Modbus exception {getattr(response, 'exception_code', 'unknown')}")
            if response.function_code != function or response.dev_id != self.DEVICE_ID:
                raise ProtocolError("Unexpected response function or slave")
            words = response.registers
            if any(type(w) is not int or not 0 <= w <= 65535 for w in words):
                raise ProtocolError("Malformed register response")
            if function == 3 and len(words) != value:
                raise ProtocolError("Malformed register count")
            if function == 6 and (response.address != address or words != [value]):
                raise ProtocolError("Write echo does not match the requested setpoint")
            return response
        except asyncio.CancelledError:
            self._client.close()
            raise
        except Exception as exc:
            # A failed write may have executed. Never retry it automatically.
            self._client.close()
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError from exc
            if isinstance(exc, ProtocolError):
                raise
            raise ProtocolError("Modbus exchange failed; command outcome may be unknown") from exc
        finally:
            self._last_finished = time.monotonic()

    async def _read_locked(self, address: int, count: int) -> RegisterSnapshot:
        response = await self._exchange_locked(3, address, count)
        return RegisterSnapshot(address, tuple(response.registers), datetime.now(timezone.utc))

    async def set_setpoint(self, mode: str, temperature: float, *, expected: int) -> SetpointChange:
        """Change one documented target, with optimistic conflict detection.

        No generic register-write API is exposed. Equal values do not write
        EEPROM. The physical display is not locked by this process, so this is
        not a cross-device atomic compare-and-swap operation. A mismatch or
        failed write requires fresh operator review, never automatic replay.
        """
        if mode not in SETPOINTS:
            raise ValueError("Unsupported setpoint")
        target = SETPOINTS[mode]
        value = target.encode(temperature)
        previous = target.encode(expected)
        async with self._lock:
            before = await self._read_locked(target.address, 1)
            if before.values != (previous,):
                raise ProtocolError("Setpoint changed since it was reviewed; no write sent")
            if value == previous:
                return SetpointChange(target.address, previous, value, False, before.received_at)
            await self._exchange_locked(6, target.address, value)
            after = await self._read_locked(target.address, 1)
            if after.values != (value,):
                self._client.close()
                raise ProtocolError("Setpoint readback differs; do not repeat or blindly restore")
            return SetpointChange(target.address, previous, value, True, after.received_at)

    async def close(self) -> None:
        """Wait for any in-flight read and release this process's ownership."""
        async with self._lock:
            self._client.close()
            self._closed = True
            if self._owners.get(self._endpoint) is self:
                del self._owners[self._endpoint]

    async def change_parameter(self, address: int, value: float, *, expected: int) -> SetpointChange:
        """Service parameters only while the native unit and compressor are off."""
        if type(address) is not int or type(expected) is not int or not 0 <= expected <= 65535:
            raise ValueError('Invalid address or expected raw word')
        encoded = encode_parameter(address, value)
        async with self._lock:
            enabled = (await self._read_locked(0, 1)).values[0]
            compressor = (await self._read_locked(0x8004, 1)).values[0]
            if enabled & 1 or compressor & 1:
                raise ProtocolError('Service editing requires unit and compressor off')
            return await self._change_locked(address, encoded, expected)

    async def change_operating(self, key: str, value: int, *, expected: int) -> SetpointChange:
        """Normal controls only; preserve all unrelated bits and protection modes."""
        fields = {'enabled': (0, 1), 'powerful': (1, 16), 'silent': (1, 32),
                  'weather_compensation': (1, 64), 'holiday': (2, 2)}
        if type(value) is not int or type(expected) is not int or not 0 <= expected <= 65535:
            raise ValueError('Invalid command')
        if key == 'mode':
            if value not in range(5):
                raise ValueError('Unknown operating mode')
            address, encoded = 4, value
        else:
            if key not in fields or value not in (0, 1):
                raise ValueError('Unsupported operating field')
            address, mask = fields[key]
            encoded = (expected & ~mask) | (mask if value else 0)
            if value and key in ('powerful', 'silent'):
                encoded &= ~(32 if key == 'powerful' else 16)
        async with self._lock:
            if key == 'mode':
                enabled = (await self._read_locked(0, 1)).values[0]
                running = (await self._read_locked(0x8004, 1)).values[0]
                if enabled & 1 or running & 1:
                    raise ProtocolError('Change operating mode only with unit and compressor off')
            return await self._change_locked(address, encoded, expected)

    async def _change_locked(self, address: int, value: int, expected: int) -> SetpointChange:
        before = await self._read_locked(address, 1)
        if before.values != (expected,):
            raise ProtocolError('Register changed since review; no write sent')
        if value == expected:
            return SetpointChange(address, expected, value, False, before.received_at)
        await self._exchange_locked(6, address, value)
        after = await self._read_locked(address, 1)
        if after.values != (value,):
            self._client.close()
            raise ProtocolError('Register readback differs; no retry or automatic restoration')
        return SetpointChange(address, expected, value, True, after.received_at)

    async def __aenter__(self) -> NexusTransport:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
