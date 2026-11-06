"""Serialized RTU-over-TCP reads using the manufacturer transport limits.

This is not a register map or a controller. There is deliberately no write API
until writable register contracts are available and verified.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import time
from typing import ClassVar

from pymodbus import FramerType
from pymodbus.client import AsyncModbusTcpClient


class ProtocolError(Exception):
    """A read failed or the response did not satisfy the request."""


@dataclass(frozen=True)
class RegisterSnapshot:
    """Raw 16-bit words and their receipt time; never inferred engineering units."""

    address: int
    values: tuple[int, ...]
    received_at: datetime


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
            try:
                await self._connect_locked()
                await asyncio.sleep(max(0.0, self.REQUEST_GAP - (time.monotonic() - self._last_finished)))
                response = await self._client.read_holding_registers(
                    address, count=count, device_id=self.DEVICE_ID,
                )
                if response.isError():
                    raise ProtocolError(f"Modbus exception {getattr(response, 'exception_code', 'unknown')}")
                if response.function_code != 3 or response.dev_id != self.DEVICE_ID:
                    raise ProtocolError("Unexpected response function or slave")
                words = response.registers
                if len(words) != count or any(type(w) is not int or not 0 <= w <= 65535 for w in words):
                    raise ProtocolError("Malformed register response")
                return RegisterSnapshot(address, tuple(words), datetime.now(timezone.utc))
            except asyncio.CancelledError:
                self._client.close()
                raise
            except Exception as exc:
                # Drop the stream so a late response cannot satisfy a later read.
                self._client.close()
                # PyModbus wraps task cancellation in ModbusIOException.
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError from exc
                if isinstance(exc, ProtocolError):
                    raise
                raise ProtocolError("Modbus read failed") from exc
            finally:
                self._last_finished = time.monotonic()

    async def close(self) -> None:
        """Wait for any in-flight read and release this process's ownership."""
        async with self._lock:
            self._client.close()
            self._closed = True
            if self._owners.get(self._endpoint) is self:
                del self._owners[self._endpoint]

    async def __aenter__(self) -> NexusTransport:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
