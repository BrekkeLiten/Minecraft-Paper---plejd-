# Plejd Light for Minecraft (Paper)

Makes a real Plejd dimmer follow the light level around your Minecraft character. Walk into a cave and the lamp in your room dims; step into daylight and it brightens.

It has two parts that run on the same Mac:

- **Plugin** (`plugin/`, Java): a Paper 26.3 plugin that reads the light level at your character's eyes and sends it to the bridge.
- **Bridge** (`bridge/`, Python): a small local service that writes that level to a Plejd dimmer over Bluetooth.

This is a Paper plugin, not a Fabric or Forge mod. It is not affiliated with or supported by Plejd, and it relies on Plejd's unofficial cloud API and Bluetooth protocol, which may change.

## Requirements

- A Mac with Bluetooth, within range of a mains-powered Plejd device
- A Plejd account with at least one dimmer
- Python 3.10 or newer
- A Paper 26.3 server running on the same Mac
- Java 25 to build the plugin (Gradle downloads it if it is missing)

## 1. Set up the bridge

```bash
cd bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m plejd_bridge.setup
python -m plejd_bridge
```

Setup asks for your Plejd account once, lists the site's devices and writes `bridge/config.json`. That file holds the site's crypto key, so it is git-ignored and created with mode `0600`. Your password is sent only to `cloud.plejd.com` and is not stored.

Leave the bridge terminal open while you play. macOS will ask for Bluetooth permission for the Python process; allow it.

The bridge connects to the nearest mains-powered Plejd node, or to `ble_address` from the config (a MAC address on Linux, a CoreBluetooth UUID on macOS). That node does not have to be the dimmer itself: the mesh relays the command to the device you picked in setup.

`GET http://127.0.0.1:8765/health` reports whether the link is up. The bridge refuses to listen on anything but localhost.

## 2. Build and install the plugin

```bash
cd plugin
./gradlew build
```

Copy `plugin/build/libs/plejd-light-1.0.0.jar` into the server's `plugins/` folder and start the server. The server must run on the same Mac as the bridge so it can reach `127.0.0.1:8765`.

## Configuration

`plugins/PlejdLight/config.yml` on the server:

| Setting | Default | Meaning |
|---|---|---|
| `player` | empty | Minecraft name to follow. Empty follows the only player online; with several online and no name, the lamp is left alone. |
| `bridge-url` | `http://127.0.0.1:8765` | Where the bridge listens. |
| `poll-ticks` | `10` | How often the light is sampled, in server ticks (20 ticks = 1 second). |
| `invert` | `false` | `true` makes a dark game give a bright lamp. |
| `offline` | `keep` | `keep` leaves the lamp alone when the followed player leaves; `off` turns it off. |

Light level 0 turns the dimmer off and level 15 is full brightness. Each step in between sends `light × 17` (0–255).

## Commands

All need the `plejd.use` permission (operators have it by default).

| Command | What it does |
|---|---|
| `/plejd status` | Shows whether the bridge is connected. |
| `/plejd set <0-15>` | Holds the lamp at that level. |
| `/plejd follow` | Goes back to following the game's light. |

## Tests

```bash
cd bridge && python -m unittest discover -s tests   # light mapping, login response, dim frame, encryption
cd plugin && ./gradlew test                         # light mapping
```

The tests need no Plejd hardware or Minecraft server. Whether the lamp actually moves can only be checked on the Mac, with the bridge running and Bluetooth allowed.

## License

[MIT](LICENSE)
