"""Localhost bridge from the Paper plugin to the Plejd mesh."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from aiohttp import web

from .crypto import parse_key
from .frames import light_to_dim
from .mesh import MeshLink

logger = logging.getLogger(__name__)

MIN_WRITE_INTERVAL = 0.4
BRIDGE_KEY: web.AppKey["Bridge"] = web.AppKey("bridge")
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class Bridge:
    def __init__(self, key: bytes, output_address: int, device_name: str, ble_address: str) -> None:
        self.mesh = MeshLink(key, ble_address)
        self.output_address = output_address
        self.device_name = device_name
        self.last_dim: int | None = None
        self.last_error: str | None = None
        self._latest: tuple[int, int] | None = None
        self._lock = asyncio.Lock()
        self._last_write = 0.0

    async def apply(self, light: int) -> int:
        dim = light_to_dim(light)
        self._latest = (light, dim)
        async with self._lock:
            latest = self._latest
            if latest != (light, dim):
                return light_to_dim(latest[0])
            wait = MIN_WRITE_INTERVAL - (time.monotonic() - self._last_write)
            if self._last_write and wait > 0:
                await asyncio.sleep(wait)
                latest = self._latest
                if latest != (light, dim):
                    return light_to_dim(latest[0])
            try:
                await self.mesh.set_level(self.output_address, dim)
            except Exception as exc:
                self.last_error = str(exc)
                await self.mesh.close()
                raise
            self._last_write = time.monotonic()
            self.last_dim = dim
            self.last_error = None
            logger.info("Light %s -> dim %s", light, dim)
            return dim

    async def close(self) -> None:
        await self.mesh.close()


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run: python -m plejd_bridge.setup")
    data = json.loads(path.read_text())
    listen = str(data.get("listen") or "127.0.0.1")
    if listen not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("The bridge only listens on localhost.")
    output = int(data["output_address"])
    if not 0 <= output <= 255:
        raise SystemExit("output_address must be 0..255")
    port = int(data.get("port") or 8765)
    return {
        "key": parse_key(str(data["crypto_key"])),
        "output_address": output,
        "device_name": str(data.get("device_name") or ""),
        "ble_address": str(data.get("ble_address") or ""),
        "listen": listen,
        "port": port,
    }


def build_app(bridge: Bridge) -> web.Application:
    app = web.Application()
    app[BRIDGE_KEY] = bridge

    async def health(request: web.Request) -> web.Response:
        current = request.app[BRIDGE_KEY]
        return web.json_response(
            {
                "connected": current.mesh.connected,
                "device": current.device_name,
                "last_dim": current.last_dim,
                "last_error": current.last_error,
            }
        )

    async def level(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            light = body["light"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return web.json_response({"error": "expected {\"light\": 0..15}"}, status=400)
        try:
            dim = await bridge.apply(light)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.warning("Dim write failed: %s", exc)
            return web.json_response({"error": str(exc)}, status=503)
        return web.json_response({"light": light, "dim": dim})

    app.router.add_get("/health", health)
    app.router.add_post("/level", level)
    return app


async def serve(path: Path = CONFIG_PATH) -> None:
    config = load_config(path)
    bridge = Bridge(
        config["key"],
        config["output_address"],
        config["device_name"],
        config["ble_address"],
    )
    runner = web.AppRunner(build_app(bridge), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, config["listen"], config["port"])
    await site.start()
    label = config["device_name"] or f"output {config['output_address']}"
    logger.info(
        "Plejd bridge listening on http://%s:%s for %s",
        config["listen"],
        config["port"],
        label,
    )
    try:
        await asyncio.Event().wait()
    finally:
        await bridge.close()
        await runner.cleanup()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
