"""One-time Plejd cloud login used to fetch the site key and device list.

The account password is only sent to cloud.plejd.com and is not written to disk.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .crypto import parse_key

APP_ID = "zHtVqXt8k4yFyk2QGmgp48D9xZr2G94xWYnF4dak"
BASE_URL = "https://cloud.plejd.com"


@dataclass(frozen=True)
class Output:
    name: str
    room: str
    output_address: int
    ble_address: str
    hardware: str
    dimmable: bool


def login(username: str, password: str) -> str:
    payload = _post("/parse/login", None, {"username": username, "password": password})
    token = payload.get("sessionToken")
    if not token:
        raise RuntimeError("Plejd login did not return a session")
    return str(token)


def fetch_sites(token: str) -> list[dict]:
    payload = _post("/parse/functions/getSiteList", token, {})
    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Plejd did not return a site list")
    return result


def fetch_site(token: str, site_id: str) -> dict:
    payload = _post(
        "/parse/functions/getSiteById",
        token,
        {},
        {"siteId": site_id},
    )
    result = payload.get("result")
    if isinstance(result, list):
        if not result:
            raise RuntimeError("Plejd returned an empty site")
        result = result[0]
    if not isinstance(result, dict):
        raise RuntimeError("Plejd did not return site details")
    return result


def parse_site(site: dict) -> tuple[bytes, list[Output]]:
    mesh = site.get("plejdMesh") or {}
    key = parse_key(str(mesh.get("cryptoKey") or ""))
    rooms = {
        room.get("roomId"): str(room.get("title") or "")
        for room in site.get("rooms") or []
        if isinstance(room, dict)
    }
    hardware = {
        str(item.get("deviceId")): str(item.get("hardwareId") or "")
        for item in site.get("plejdDevices") or []
        if isinstance(item, dict) and item.get("deviceId")
    }
    settings_by_device: dict[str, list[dict]] = {}
    for setting in site.get("outputSettings") or []:
        if not isinstance(setting, dict):
            continue
        device_id = setting.get("deviceParseId")
        if device_id:
            settings_by_device.setdefault(str(device_id), []).append(setting)

    outputs: list[Output] = []
    for device in site.get("devices") or []:
        if not isinstance(device, dict):
            continue
        ble = str(device.get("deviceId") or "")
        name = str(device.get("title") or "Unnamed")
        room = rooms.get(device.get("roomId"), "")
        hw = hardware.get(ble, "")
        settings = settings_by_device.get(str(device.get("objectId")), [])
        output_map = (site.get("outputAddress") or {}).get(ble) or {}
        if not isinstance(output_map, dict):
            output_map = {}
        if settings:
            for setting in settings:
                address = output_map.get(str(setting.get("output")))
                if address is None:
                    address = (site.get("deviceAddress") or {}).get(ble)
                if address is None:
                    continue
                outputs.append(
                    Output(
                        name=name,
                        room=room,
                        output_address=_address(address),
                        ble_address=ble,
                        hardware=hw,
                        dimmable=setting.get("dimCurve") != "nonDimmable",
                    )
                )
            continue
        address = (site.get("deviceAddress") or {}).get(ble)
        if address is None:
            continue
        outputs.append(
            Output(
                name=name,
                room=room,
                output_address=_address(address),
                ble_address=ble,
                hardware=hw,
                dimmable=True,
            )
        )
    outputs.sort(key=lambda item: (item.room.lower(), item.name.lower(), item.output_address))
    return key, outputs


def _address(value: object) -> int:
    address = int(value)  # type: ignore[arg-type]
    if not 0 <= address <= 255:
        raise ValueError(f"mesh address {address} is outside 0..255")
    return address


def _post(path: str, token: str | None, body: dict, query: dict | None = None) -> dict:
    url = BASE_URL + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "X-Parse-Application-Id": APP_ID,
        "Content-Type": "application/json",
    }
    if token:
        headers["X-Parse-Session-Token"] = token
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Plejd cloud returned HTTP {exc.code} for {path}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Plejd cloud: {exc.reason}") from None
    if not isinstance(payload, dict):
        raise RuntimeError(f"Plejd cloud returned an unexpected body for {path}")
    return payload
