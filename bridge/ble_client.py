"""BLE client for the claude-desktop-buddy ESP32 device.

Connects to the device's Nordic UART Service (NUS), sends newline-delimited
JSON heartbeats / prompts, and receives the device's responses (button
decisions, acks). The device firmware is unchanged — it speaks the same
protocol regardless of whether the peer is Claude Desktop or this bridge.

NUS UUIDs (standard Nordic UART Service):
    Service : 6e400001-b5a3-f393-e0a9-e50e24dcca9e
    RX (write, host -> device) : 6e400002-b5a3-f393-e0a9-e50e24dcca9e
    TX (notify, device -> host): 6e400003-b5a3-f393-e0a9-e50e24dcca9e
"""

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

log = logging.getLogger("ble")

NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # write to device
NUS_TX_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # notify from device

# BLE characteristic writes are MTU-limited; chunk below the negotiated size.
_WRITE_CHUNK = 180


class BuddyBleClient:
    """Maintains a connection to one buddy device and pumps JSON lines."""

    def __init__(
        self,
        name_prefix: str = "Claude",
        address: Optional[str] = None,
        on_message: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.name_prefix = name_prefix
        self.address = address
        self.on_message = on_message
        self._client: Optional[BleakClient] = None
        self._rx_buf = bytearray()
        self._connected = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def _find_device(self, timeout: float = 10.0) -> Optional[BLEDevice]:
        log.info("Scanning for buddy device (prefix=%r addr=%s)...",
                 self.name_prefix, self.address)
        devices = await BleakScanner.discover(timeout=timeout)
        for d in devices:
            if self.address and d.address.lower() == self.address.lower():
                return d
            if d.name and d.name.startswith(self.name_prefix):
                log.info("Found %s (%s)", d.name, d.address)
                return d
        return None

    def _handle_notify(self, _char, data: bytearray) -> None:
        # Device sends newline-delimited JSON. Accumulate and split on \n.
        self._rx_buf.extend(data)
        while b"\n" in self._rx_buf:
            line, _, rest = self._rx_buf.partition(b"\n")
            self._rx_buf = bytearray(rest)
            text = line.decode("utf-8", "replace").strip()
            if not text or not text.startswith("{"):
                continue
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                log.warning("Bad JSON from device: %s", text)
                continue
            log.debug("RX <- device: %s", msg)
            if self.on_message:
                asyncio.create_task(self.on_message(msg))

    async def connect(self, retry: bool = True) -> None:
        while True:
            dev = await self._find_device()
            if dev is None:
                log.warning("Device not found.")
                if not retry:
                    raise RuntimeError("buddy device not found")
                await asyncio.sleep(3)
                continue
            try:
                self._client = BleakClient(dev)
                await self._client.connect()
                await self._client.start_notify(NUS_TX_CHAR, self._handle_notify)
                self._connected.set()
                log.info("Connected to %s", dev.address)
                return
            except Exception as e:  # noqa: BLE001 - surface and retry
                log.error("Connect failed: %s", e)
                self._client = None
                if not retry:
                    raise
                await asyncio.sleep(3)

    async def send_json(self, obj: dict) -> None:
        """Send one JSON object as a newline-terminated line to the device."""
        if not self.connected:
            log.debug("send_json skipped (not connected): %s", obj)
            return
        payload = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        for i in range(0, len(payload), _WRITE_CHUNK):
            chunk = payload[i:i + _WRITE_CHUNK]
            await self._client.write_gatt_char(NUS_RX_CHAR, chunk, response=False)
        log.debug("TX -> device: %s", obj)

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            finally:
                self._client = None
                self._connected.clear()
