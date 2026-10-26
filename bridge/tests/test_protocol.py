import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from plejd_bridge.cloud import parse_site
from plejd_bridge.crypto import auth_response, mesh_crypt, parse_key
from plejd_bridge.frames import dim_frame, light_to_dim
from plejd_bridge.server import Bridge, build_app, load_config


DIMS = [0, 17, 34, 51, 68, 85, 102, 119, 136, 153, 170, 187, 204, 221, 238, 255]


class ScaleTests(unittest.TestCase):
    def test_each_minecraft_level_is_a_distinct_dim_byte(self):
        self.assertEqual([light_to_dim(light) for light in range(16)], DIMS)
        for light, dim in enumerate(DIMS):
            self.assertEqual(dim, round(light / 15 * 255))

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            light_to_dim(-1)
        with self.assertRaises(ValueError):
            light_to_dim(16)
        with self.assertRaises(ValueError):
            light_to_dim(True)  # type: ignore[arg-type]


class FrameTests(unittest.TestCase):
    def test_published_dim_layout(self):
        self.assertEqual(dim_frame(0x5A, 0x78), bytes.fromhex("5a01100098017878"))
        self.assertEqual(dim_frame(0x5A, 255), bytes.fromhex("5a0110009801ffff"))

    def test_darkness_is_the_off_command(self):
        self.assertEqual(dim_frame(0x5A, 0), bytes.fromhex("5a0110009700"))


class CryptoTests(unittest.TestCase):
    def test_keystream_matches_the_published_recipe(self):
        key = bytes(range(16))
        address = bytes(range(6))
        seed = address + address + address[:4]
        encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
        stream = encryptor.update(seed) + encryptor.finalize()
        data = bytes(range(8))
        expected = bytes(byte ^ stream[index % 16] for index, byte in enumerate(data))
        self.assertEqual(mesh_crypt(key, address, data), expected)

    def test_crypt_round_trip_and_pinned_vector(self):
        key = bytes(range(16))
        address = bytes.fromhex("aabbccddeeff")
        frame = dim_frame(7, 119)
        blob = mesh_crypt(key, address, frame)
        self.assertEqual(mesh_crypt(key, address, blob), frame)
        self.assertNotEqual(blob, frame)
        # Pinned output of the published keystream for this frame, so a drift in
        # dim_frame or mesh_crypt fails even if both stay inverses of each other.
        self.assertEqual(blob.hex(), "acce43215f04054d")

    def test_auth_folds_sha256(self):
        key = bytes(range(16))
        challenge = bytes(range(16, 32))
        mixed = bytes(left ^ right for left, right in zip(key, challenge, strict=True))
        digest = hashlib.sha256(mixed).digest()
        expected = bytes(left ^ right for left, right in zip(digest[:16], digest[16:], strict=True))
        self.assertEqual(auth_response(key, challenge), expected)
        self.assertEqual(len(auth_response(key, challenge)), 16)

    def test_auth_accepts_a_32_byte_key(self):
        key = bytes(range(32))
        challenge = bytes(range(32, 64))
        mixed = (int.from_bytes(key, "big") ^ int.from_bytes(challenge, "big")).to_bytes(32, "big")
        digest = hashlib.sha256(mixed).digest()
        expected = bytes(left ^ right for left, right in zip(digest[:16], digest[16:], strict=True))
        self.assertEqual(auth_response(key, challenge), expected)

    def test_parse_key_strips_dashes(self):
        self.assertEqual(
            parse_key("00112233-4455-6677-8899-aabbccddeeff"),
            bytes.fromhex("00112233445566778899aabbccddeeff"),
        )


class CloudTests(unittest.TestCase):
    def test_parse_site_prefers_output_address(self):
        site = {
            "plejdMesh": {"cryptoKey": "00112233-4455-6677-8899-AABBCCDDEEFF"},
            "devices": [
                {"deviceId": "AABBCCDDEEFF", "title": "Pill", "objectId": "obj1", "roomId": "r1"},
                {"deviceId": "112233445566", "title": "Relay", "objectId": "obj2", "roomId": "r1"},
            ],
            "deviceAddress": {"AABBCCDDEEFF": 3, "112233445566": 4},
            "outputSettings": [
                {"deviceParseId": "obj1", "output": 0, "dimCurve": "linear"},
                {"deviceParseId": "obj2", "output": 0, "dimCurve": "nonDimmable"},
            ],
            "outputAddress": {"AABBCCDDEEFF": {"0": 7}, "112233445566": {"0": 9}},
            "plejdDevices": [
                {"deviceId": "AABBCCDDEEFF", "hardwareId": "DIM-01"},
                {"deviceId": "112233445566", "hardwareId": "REL-01"},
            ],
            "rooms": [{"roomId": "r1", "title": "Kitchen"}],
        }
        key, outputs = parse_site(site)
        self.assertEqual(key.hex(), "00112233445566778899aabbccddeeff")
        by_name = {item.name: item for item in outputs}
        self.assertEqual(by_name["Pill"].output_address, 7)
        self.assertTrue(by_name["Pill"].dimmable)
        self.assertEqual(by_name["Pill"].hardware, "DIM-01")
        self.assertEqual(by_name["Pill"].room, "Kitchen")
        self.assertEqual(by_name["Relay"].output_address, 9)
        self.assertFalse(by_name["Relay"].dimmable)


class ConfigTests(unittest.TestCase):
    def test_refuses_a_public_bind(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "crypto_key": "00112233445566778899aabbccddeeff",
                        "output_address": 1,
                        "listen": "0.0.0.0",
                    }
                )
            )
            with self.assertRaises(SystemExit):
                load_config(path)


class FakeMesh:
    def __init__(self) -> None:
        self.connected = False
        self.levels: list[tuple[int, int]] = []

    async def set_level(self, output: int, dim: int) -> None:
        self.connected = True
        self.levels.append((output, dim))

    async def close(self) -> None:
        self.connected = False


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from aiohttp.test_utils import TestClient, TestServer

        self.bridge = Bridge(bytes(range(16)), 7, "Pill", "")
        self.fake = FakeMesh()
        self.bridge.mesh = self.fake  # type: ignore[assignment]
        self.client = TestClient(TestServer(build_app(self.bridge)))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_level_maps_and_forwards(self) -> None:
        response = await self.client.post("/level", json={"light": 15})
        self.assertEqual(response.status, 200)
        body = await response.json()
        self.assertEqual(body, {"light": 15, "dim": 255})
        self.assertEqual(self.fake.levels, [(7, 255)])

    async def test_health(self) -> None:
        response = await self.client.get("/health")
        self.assertEqual(response.status, 200)
        body = await response.json()
        self.assertEqual(body["device"], "Pill")
        self.assertFalse(body["connected"])
