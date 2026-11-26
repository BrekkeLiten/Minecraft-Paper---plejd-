"""Bluetooth mesh session to one powered Plejd node.

macOS CoreBluetooth does not reveal the remote MAC. After connecting, the
node's AccessAddress characteristic supplies the 6 bytes the cipher needs.
Any powered node can relay a dim command to the dimmer pill.
"""

from __future__ import annotations

import asyncio
import logging
import secrets

from bleak import BleakClient, BleakScanner

from .crypto import auth_response, mesh_crypt
from .frames import dim_frame

logger = logging.getLogger(__name__)

SERVICE_UUID = "31ba0001-6085-4726-be45-040c957391b5"
_SUFFIX = "-6085-4726-be45-040c957391b5"
DATA_UUID = f"31ba0004{_SUFFIX}"
ACCESS_UUID = f"31ba0006{_SUFFIX}"
AUTH_UUID = f"31ba0009{_SUFFIX}"
PING_UUID = f"31ba000a{_SUFFIX}"


class MeshLink:
    def __init__(self, key: bytes, ble_address: str = "") -> None:
        self.key = key
        self.ble_address = ble_address.strip()
        self.connected = False
        self._client: BleakClient | None = None
        self._address: bytes | None = None
        self._lock = asyncio.Lock()
        self._ping_task: asyncio.Task[None] | None = None

    async def set_level(self, output_address: int, dim: int) -> None:
        async with self._lock:
            await self._ensure()
            client = self._client
            address = self._address
            if client is None or address is None:
                raise RuntimeError("Plejd link dropped before the write")
            payload = mesh_crypt(self.key, address, dim_frame(output_address, dim))
            await client.write_gatt_char(DATA_UUID, payload, response=True)

    async def close(self) -> None:
        task = self._ping_task
        self._ping_task = None
        current = asyncio.current_task()
        if task is not None and task is not current:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        client = self._client
        self._client = None
        self._address = None
        self.connected = False
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                logger.debug("Disconnect ignored", exc_info=True)

    async def _ensure(self) -> None:
        if self._client is not None and self._client.is_connected and self._address is not None:
            return
        await self._connect()

    async def _connect(self) -> None:
        await self._drop_client()
        device = await self._scan()
        client = BleakClient(device, disconnected_callback=self._on_disconnect)
        await client.connect(timeout=20.0)
        self._client = client
        raw = bytes(await client.read_gatt_char(ACCESS_UUID))
        self._address = _cipher_address(raw)
        await self._authenticate(client)
        await self._ping(client)
        self.connected = True
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info("Plejd link up, cipher address %s", self._address.hex())

    async def _drop_client(self) -> None:
        client = self._client
        self._client = None
        self._address = None
        self.connected = False
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                logger.debug("Drop ignored", exc_info=True)

    def _on_disconnect(self, _client: BleakClient) -> None:
        self.connected = False
        self._address = None

    async def _scan(self):
        found = await BleakScanner.discover(
            timeout=8.0,
            service_uuids=[SERVICE_UUID],
            return_adv=True,
        )
        pairs = list(found.values()) if isinstance(found, dict) else list(found)
        candidates = []
        for device, adv in pairs:
            if self.ble_address and not _same_address(device.address, self.ble_address):
                continue
            rssi = getattr(adv, "rssi", 0)
            candidates.append((device, rssi))
        if not candidates:
            if self.ble_address:
                raise RuntimeError(f"No Plejd advertisement matched {self.ble_address}")
            raise RuntimeError(
                "No Plejd device in range. Stand near a mains-powered node and allow Bluetooth for this terminal."
            )
        candidates.sort(key=lambda item: item[1], reverse=True)
        chosen = candidates[0][0]
        logger.info("Connecting to %s (%s dBm)", chosen.name or "Plejd", candidates[0][1])
        return chosen

    async def _authenticate(self, client: BleakClient) -> None:
        await client.write_gatt_char(AUTH_UUID, bytes([0]), response=True)
        challenge = bytes(await client.read_gatt_char(AUTH_UUID))
        if len(challenge) != len(self.key):
            if len(challenge) > len(self.key):
                logger.info(
                    "Auth challenge is %s bytes; using the first %s",
                    len(challenge),
                    len(self.key),
                )
                challenge = challenge[: len(self.key)]
            else:
                raise RuntimeError(
                    f"Auth challenge is {len(challenge)} bytes and the site key is {len(self.key)}"
                )
        await client.write_gatt_char(AUTH_UUID, auth_response(self.key, challenge), response=True)

    async def _ping(self, client: BleakClient) -> None:
        ping = bytes([secrets.randbelow(256)])
        await client.write_gatt_char(PING_UUID, ping, response=True)
        pong = bytes(await client.read_gatt_char(PING_UUID))
        if not pong or pong[0] != (ping[0] + 1) & 0xFF:
            raise RuntimeError("Plejd ping was not acknowledged; the site key may be wrong")

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(8)
                async with self._lock:
                    client = self._client
                    if client is None or not client.is_connected:
                        return
                    await self._ping(client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Plejd ping failed: %s", exc)
            await self.close()


def _cipher_address(raw: bytes) -> bytes:
    if len(raw) < 6:
        raise RuntimeError(f"Access address was {len(raw)} bytes, expected at least 6")
    return raw[:6]


def _same_address(left: str, right: str) -> bool:
    def norm(value: str) -> str:
        return value.replace(":", "").replace("-", "").lower()

    return norm(left) == norm(right)
