"""Synthetic protocol tests: no connection to a real installation."""
import asyncio
import struct
import time
import unittest

from pymodbus.framer.rtu import FramerRTU
from pymodbus.pdu import DecodePDU
from pymodbus.pdu.register_message import ReadHoldingRegistersResponse, WriteSingleRegisterResponse
from sunex_nexus_protocol import NexusTransport, ProtocolError


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.finished = []
        self.streams = []
        self.handlers = set()
        self.response_mode = 'normal'
        self.clients = []
        self.bank = {}
        self.writes = []
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        for client in self.clients:
            await asyncio.wait_for(client.close(), 2)
        self.server.close()
        for writer in self.streams:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (TimeoutError, ConnectionError):
                writer.transport.abort()
        for task in self.handlers:
            task.cancel()
        await asyncio.gather(*self.handlers, return_exceptions=True)
        await asyncio.wait_for(self.server.wait_closed(), 2)

    def client(self, **kwargs):
        client = NexusTransport('127.0.0.1', self.port, **kwargs)
        self.clients.append(client)
        return client

    async def handle(self, reader, writer):
        self.handlers.add(asyncio.current_task())
        self.streams.append(writer)
        try:
            while True:
                frame = await reader.readexactly(8)
                self.assertTrue(FramerRTU.check_CRC(frame[:-2], int.from_bytes(frame[-2:], 'big')))
                self.assertEqual(frame[0], 1)
                self.assertIn(frame[1], (3, 6))
                address, count = struct.unpack('>HH', frame[2:6])
                self.requests.append((address, count, time.monotonic()))
                if self.response_mode == 'silent':
                    continue
                if frame[1] == 6:
                    self.writes.append((address, count))
                    self.bank[address] = count
                    if self.response_mode == 'silent_write':
                        continue
                    if self.response_mode == 'wrong_readback':
                        self.bank[address] += 1
                    echo = count + 1 if self.response_mode == 'wrong_echo' else count
                    reply = WriteSingleRegisterResponse(address=address, registers=[echo], dev_id=1)
                else:
                    if self.response_mode == 'short':
                        count -= 1
                    reply = ReadHoldingRegistersResponse(registers=[self.bank.get(address + i, (address + i) % 65536) for i in range(count)], dev_id=1)
                payload = FramerRTU(DecodePDU(False)).buildFrame(reply)
                # Deliberate packet fragmentation exercises real RTU-over-TCP parsing.
                writer.write(payload[:3])
                await writer.drain()
                await asyncio.sleep(0.01)
                writer.write(payload[3:])
                await writer.drain()
                self.finished.append(time.monotonic())
        except (asyncio.IncompleteReadError, ConnectionError):
            return

    async def test_real_frames_and_end_of_address_space(self):
        result = await self.client().read(65534, 2)
        self.assertEqual(result.values, (65534, 65535))
        self.assertIsNotNone(result.received_at.tzinfo)

    async def test_parallel_reads_are_serialized_and_paced(self):
        client = self.client()
        results = await asyncio.gather(client.read(8), client.read(9), client.read(10))
        self.assertEqual([x.values for x in results], [(8,), (9,), (10,)])
        for index in range(1, len(self.requests)):
            self.assertGreater(self.requests[index][2] - self.finished[index - 1], 0.2)

    async def test_invalid_ranges_send_nothing(self):
        client = self.client()
        for address, count in [(-1, 1), (65536, 1), (65535, 2), (0, 121), (0, 0), (True, 1), (0, 1.5)]:
            with self.assertRaises(ValueError):
                await client.read(address, count)
        self.assertEqual(self.requests, [])

    async def test_maximum_count(self):
        result = await self.client().read(20, 120)
        self.assertEqual(len(result.values), 120)

    async def test_duplicate_endpoint_blocked_until_close(self):
        first, second = self.client(), self.client()
        await first.read(8)
        with self.assertRaises(ProtocolError):
            await second.read(9)
        self.assertEqual(len(self.requests), 1)
        await first.close()
        await second.read(9)

    async def test_timeout_does_not_retry(self):
        self.response_mode = 'silent'
        with self.assertRaises(ProtocolError):
            await self.client(timeout=0.1).read(8)
        self.assertEqual(len(self.requests), 1)

    async def test_short_response_rejected(self):
        self.response_mode = 'short'
        with self.assertRaises(ProtocolError):
            await self.client().read(8, 2)

    async def test_close_prevents_reuse(self):
        client = self.client()
        await client.close()
        with self.assertRaises(ProtocolError):
            await client.read(8)
        self.assertEqual(self.requests, [])

    async def test_cancellation_drops_connection(self):
        self.response_mode = 'silent'
        client = self.client()
        task = asyncio.create_task(client.read(8))
        async with asyncio.timeout(2):
            while not self.requests:
                await asyncio.sleep(0.001)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.response_mode = 'normal'
        self.assertEqual((await client.read(9)).values, (9,))

    async def test_setpoint_write_readback_and_noop(self):
        self.bank[0x91] = 35
        client = self.client()
        result = await client.set_setpoint('heating', 36, expected=35)
        self.assertTrue(result.changed)
        self.assertEqual((result.previous, result.requested), (35, 36))
        noop = await client.set_setpoint('heating', 36, expected=36)
        self.assertFalse(noop.changed)
        self.assertEqual(self.writes, [(0x91, 36)])
        for index in range(1, len(self.requests)):
            self.assertGreater(self.requests[index][2] - self.finished[index - 1], .2)

    async def test_external_setpoint_change_prevents_write(self):
        self.bank[0x91] = 35
        with self.assertRaisesRegex(ProtocolError, 'changed since'):
            await self.client().set_setpoint('heating', 36, expected=34)
        self.assertEqual(self.writes, [])

    async def test_invalid_setpoint_sends_nothing(self):
        client = self.client()
        for mode, value in [('heating', 51), ('heating', 36.5), ('heating', True),
                            ('heating', float('nan')), ('hot_water', 20), ('reset', 1)]:
            with self.assertRaises(ValueError):
                await client.set_setpoint(mode, value, expected=35)
        self.assertEqual(self.requests, [])

    async def test_lost_write_response_not_retried(self):
        self.bank[0x91] = 35
        self.response_mode = 'silent_write'
        with self.assertRaises(ProtocolError):
            await self.client(timeout=.1).set_setpoint('heating', 36, expected=35)
        self.assertEqual(self.writes, [(0x91, 36)])
        self.assertEqual(self.bank[0x91], 36)

    async def test_wrong_write_echo_rejected(self):
        self.bank[0x91] = 35
        self.response_mode = 'wrong_echo'
        with self.assertRaises(ProtocolError):
            await self.client().set_setpoint('heating', 36, expected=35)
        self.assertEqual(self.writes, [(0x91, 36)])

    async def test_wrong_write_readback_not_retried(self):
        self.bank[0x91] = 35
        self.response_mode = 'wrong_readback'
        with self.assertRaisesRegex(ProtocolError, 'readback differs'):
            await self.client().set_setpoint('heating', 36, expected=35)
        self.assertEqual(self.writes, [(0x91, 36)])


if __name__ == '__main__':
    unittest.main()
