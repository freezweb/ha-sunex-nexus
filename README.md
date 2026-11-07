# SUNEX NEXUS for Home Assistant

Independent, local Home Assistant integration for SUNEX NEXUS M-EVI heat pumps.
No cloud, MQTT broker or external heating controller is required. This is a
community project, not an official SUNEX product.

## Features

- UI setup for an Ethernet/RS485 gateway using transparent Modbus RTU over TCP.
- Temperatures, compressor frequency, fan speed, operating flags and fault codes.
- Heating, cooling and hot-water targets; all five documented operating modes.
- Unit enable, powerful/silent operation, weather compensation and holiday mode.
- All 314 documented configuration/status words as optional raw diagnostics.
- Documented bounded service parameters, optional and disabled in the entity
  registry by default. Enable individual entities only when needed.
- English/German UI, diagnostics without network addresses, stable entity IDs.
- Writes disabled by default. Serialized writes with readback, no automatic
  retries, durable uncertainty lock, five-second spacing and 48 writes per 24 h.

## Requirements and supported hardware

- Home Assistant **2026.10.4 or newer**.
- SUNEX NEXUS **M18 EVI**, using the manufacturer M-EVI register map.
- A transparent RTU-over-TCP Ethernet/RS485 gateway: **9600 baud, 8N1, slave 1**.
  Configure its serial settings beforehand; this integration does not change
  gateway configuration. Set the configured TCP port in the integration.
- Exclusive Modbus-master ownership of the gateway **and physical bus**.

Only the M18 EVI has hardware evidence. Other models, gateway protocols and
firmware variants are not claimed compatible. This is not Modbus TCP with an
MBAP header. Similar connector labels do not prove an electrical pinout.

## Installation

Until HACS default-catalog inclusion is accepted:

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/freezweb/ha-sunex-nexus`, category **Integration**.
3. Download **SUNEX NEXUS**, then restart Home Assistant.
4. Open **Settings > Devices & services > Add integration > SUNEX NEXUS**.
5. Enter the gateway hostname/IP and TCP port. Confirm exclusive bus ownership
   and the supported register profile. Setup only reads, never switches or writes.

Manual alternative: place `custom_components/sunex_nexus` in your Home Assistant
configuration's `custom_components` directory and restart, then follow step 4.

This project must not be confused with the separate heating-controller project.
That controller can use the shared protocol library without Home Assistant.
**Do not enable this integration against a gateway already owned by that or
another Modbus master**, including a second gateway on the same RS485 pair.
There is no cross-process lock or automatic arbitration. Coordinate an explicit
handover first. An IP/hostname alias is not a separate device.

## Operation and safety

After confirming wiring, hydraulic commissioning and control ownership, enable
**Allow writes** in the integration options if control is required. The default
is read-only. Neither setup, reload nor reconnect sends startup commands.

Heating/cooling targets control **water inlet temperature**, not outlet or pool
temperature. Heating accepts whole degrees from **15 to 50 C**, cooling 7 to 30 C,
hot water 28 to 60 C. There is no pool-floor or whole-house regulator in this
integration. Those functions remain separate from the device interface.

Service editing requires the unit **and compressor off**, writes enabled and
the **Service editing (10 minutes)** switch. Operating-mode changes also require
unit and compressor off. The native safety functions remain in control.
Reserved/ambiguous words, factory reset and forced actuators are not writable.
Service values are documented **raw integers**, not guessed engineering units.
Fault codes are exposed on the fault-count sensor's `codes` attribute.

A failed command may have executed. Further writes are locked, including across
HA reload/restart. Inspect actual device state, then use **Acknowledge command
after inspection**. It performs a fresh complete read and releases the lock;
it never repeats the previous command or restores a guessed value.

Communication failure makes measurements unavailable. It does **not** prove the
heat pump stopped and does not override its local protections. Never use this
integration as an independent safety device or bypass flow/temperature limits.
Local thermostat/display changes take priority through pre-write conflict checks;
these checks are not a physical cross-master atomic lock.

## Verification and limitations

The shared protocol read the documented register banks on one commissioned
M18 EVI. A one-degree heating-target change and restoration were verified by
independent register reads; other configuration words were unchanged. That
evidence predates the native HA component and does not prove every mode or
service parameter on every firmware.

Native HA setup, entity services, unload, errors and command locks are tested in
an isolated HA runtime. Protocol tests exercise actual RTU frames against a
synthetic TCP server, including fragmented responses. Automated tests are not
physical commissioning or long-term thermal acceptance. No second client is
started against an actively controlled installation for release testing.

Raw/contradictory firmware fields remain raw. In particular `0x00B0`/`0x00B1`
are not writable. See [register contracts](docs/REGISTERS.md) and
[development/release evidence](docs/DEVELOPMENT.md).

## Development

Use Python 3.14 and Linux for native Home Assistant tests:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest-homeassistant-custom-component==0.13.375
pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1
```

`custom_components/sunex_nexus/protocol/` is also packaged as
`sunex-nexus-protocol` for independent consumers; it contains no HA dependency.
The native integration imports the same source, not a separate register copy.
The original integration icon and translations are generated by
`python scripts/build_metadata.py`; the icon is not a manufacturer trademark.

Please file issues with firmware/model details and sanitized diagnostics. Never
upload credentials, customer configuration, private correspondence or raw network
captures. The manufacturer-supplied PDF is intentionally not redistributed.

## HACS status

Custom-repository installation, submitting a default-catalog pull request, and
HACS acceptance are separate milestones. Release validation uses both hassfest
and the HACS action without ignored checks. Inclusion in the default catalog
requires review by HACS maintainers; publishing a release is not acceptance.
