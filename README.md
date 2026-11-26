"""Run the Paper 26.3 server and this bridge on the same Mac. The plugin reads the light at your eyes and the bridge writes that level to a Plejd dimmer over Bluetooth.

## Bridge

```bash
cd bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m plejd_bridge.setup
python -m plejd_bridge
```

Setup asks for the Plejd account once, lists the site's devices, and writes `config.json` next to this folder. That file holds the site crypto key. It is gitignored, mode `0600`, and the password is not stored. Leave the bridge terminal open while you play.

macOS will ask for Bluetooth permission for the Python process. Allow it. The bridge connects to the nearest mains-powered Plejd node (or `ble_address` in the config, a MAC on Linux or a CoreBluetooth UUID on macOS). The dimmer pill does not have to be the node you connect to; the mesh relays the command. The device you pick in setup is the one that changes brightness.

`GET http://127.0.0.1:8765/health` reports whether the link is up. The bridge refuses to listen on anything but localhost.

## Plugin

The server must be Paper 26.3, running on this Mac so it can reach the bridge at `127.0.0.1`.

```bash
cd plugin
./gradlew build
```

Copy `plugin/build/libs/plejd-light-1.0.0.jar` into the server's `plugins/` folder and start the server. Java 25 is required to compile; Gradle downloads it.

`plugins/PlejdLight/config.yml`:

- `player` — Minecraft name to follow. Empty uses the only person online. With several people online and no name, the lamp is left alone.
- `invert` — flip the mapping.
- `offline` — `keep` leaves the lamp where it is when that player leaves. `off` sends level 0.

Join the server. Eye light 0 turns the dimmer off. Light 15 sends dim 255. Each step in between is `light * 17`.

```
/plejd status
/plejd set 15
/plejd set 0
/plejd follow
```

`/plejd set` holds a level until `/plejd follow`.

## What this machine cannot check

A cloud build has no Plejd radio and no Minecraft server. Unit tests cover the light map, the login response, and the dim frame. The lamp itself moves only on the Mac, with the bridge running and Bluetooth allowed.

## License

[MIT](LICENSE). Not affiliated with or supported by Plejd.
