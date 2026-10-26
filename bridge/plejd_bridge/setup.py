"""Ask for the Plejd account once and store the site key plus the chosen dimmer."""

from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

from .cloud import fetch_site, fetch_sites, login, parse_site

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit("Run setup from a terminal so the password can be typed.")
    if CONFIG_PATH.exists():
        answer = input(f"{CONFIG_PATH} already exists. Overwrite it? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            raise SystemExit("Left the existing config in place.")

    email = input("Plejd account email: ").strip()
    password = getpass.getpass("Plejd password (not saved): ")
    try:
        token = login(email, password)
        sites = fetch_sites(token)
        if not sites:
            raise SystemExit("That account has no Plejd sites.")
        site_summary = _choose_site(sites)
        site_id = site_summary.get("siteId")
        if not site_id:
            raise SystemExit("Plejd site list entry has no siteId.")
        site = fetch_site(token, str(site_id))
        _key, outputs = parse_site(site)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    if not outputs:
        raise SystemExit("That site has no devices.")
    _print_outputs(outputs)
    choice = outputs[_choose_index(len(outputs))]
    config = {
        "crypto_key": _key.hex(),
        "output_address": choice.output_address,
        "device_name": choice.name,
        "room": choice.room,
        "listen": "127.0.0.1",
        "port": 8765,
        "ble_address": "",
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
    os.chmod(CONFIG_PATH, 0o600)
    print(f"Wrote {CONFIG_PATH}. The crypto key stays in that file and was not printed.")
    print(f"Selected {choice.room + ' / ' if choice.room else ''}{choice.name} at mesh address {choice.output_address}.")


def _choose_site(sites: list[dict]) -> dict:
    if len(sites) == 1:
        title = sites[0].get("title") or sites[0].get("siteId")
        print(f"Using site {title}.")
        return sites[0]
    print("Sites:")
    for index, site in enumerate(sites):
        print(f"{index:3}  {site.get('title') or 'Untitled'}  ({site.get('siteId')})")
    return sites[_choose_index(len(sites))]


def _print_outputs(outputs: list) -> None:
    print("Devices:")
    for index, output in enumerate(outputs):
        kind = "dimmer" if output.dimmable else "not dimmable"
        room = output.room or "-"
        hardware = f"  {output.hardware}" if output.hardware else ""
        print(f"{index:3}  {room} / {output.name}  address {output.output_address}{hardware}  {kind}")


def _choose_index(count: int) -> int:
    raw = input(f"Device number [0-{count - 1}]: ").strip()
    try:
        index = int(raw)
    except ValueError:
        raise SystemExit("Enter the number beside the dimmer.") from None
    if not 0 <= index < count:
        raise SystemExit("That number is not in the list.")
    return index


if __name__ == "__main__":
    main()
