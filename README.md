# SUNEX NEXUS for Home Assistant

An independent, local-first Home Assistant integration for SUNEX NEXUS heat
pumps, intended for distribution through HACS.

## Development status

**Protocol library and external-controller MQTT deployment are operational on
one M18 installation. A native custom-component/HACS release is not published
yet. This repository has not been submitted to or accepted by HACS.**

The initial implementation targets the NEXUS M18 EVI. Compatibility with other
models and firmware must be verified individually; similar product names are
not evidence of compatible registers.

The manufacturer has supplied the M-EVI register table. That correspondence
and its attachments are not redistributed here. Documented temperatures,
operating flags and fault registers are decoded. Bounded temperature-setpoint
changes use precondition checks, FC06 and readback. One heating-target change
and restoration have been verified on an M18 EVI, including the Home Assistant
MQTT command path through a single-owner heating-controller service. Its full
register dashboard and temporary inlet-target supervisor are separate from
the future native integration. Long-term thermal acceptance remains pending.

## Protocol development

The shared `sunex-nexus-protocol` package is built from the same source directory
that will ship inside the integration. It uses PyModbus for RTU-over-TCP framing,
serializes reads and setpoint transactions, enforces request spacing and checks
responses. It never writes on startup or retries a failed command automatically.
There is no cloud dependency and no automatic connection at import time.

```sh
python -m venv .venv
# Activate the virtual environment for your operating system first.
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests use a synthetic local TCP server, including fragmented packets, concurrent
reads, timeout, cancellation and duplicate transport ownership. They also cover
signed/scaled temperatures, fault flags, target limits, changed preconditions,
write echo/readback, no-op suppression and ambiguous write failures. Synthetic
tests alone do not prove physical heat-pump control.

The catalog covers 271 configuration words and 43 status words. Documented
numeric service parameters have bounded encoding and require both native unit
enable and compressor-running flags to be off. Reserved/ambiguous registers,
factory reset and forced actuators are not writable. Values contradicting the
tested firmware remain read-only; do not treat a plausible raw value as proof
of a register's meaning.

See [Register contracts](docs/REGISTERS.md) for confirmed mappings and unresolved
firmware differences. Heating/cooling setpoints regulate the water **inlet**,
not the outlet; a warmer outlet does not itself mean the target was ignored.

## Planned scope

- Local communication through an RS485-to-Ethernet gateway, without cloud access.
- Home Assistant UI configuration and stable device/entity identifiers.
- Documented temperatures, operating states and fault reporting.
- Documented operating modes and temperature setpoints with validated bounds.
- Explicit write control, serialized requests and command readback.
- Sanitized diagnostics, tests and English/German translations.
- A reusable protocol layer for integration with an external heating controller.

Feature availability will follow the verified register map. Unsupported
measurements or commands will not be invented or represented as working.

## Control ownership and safety

Only one application may own a given gateway connection and issue Modbus
requests. Home Assistant and an external controller must not independently
poll or command the same bus. Their integration must use one transport owner
and an explicitly defined command interface.

The native heat-pump safety functions must remain enabled. Communication loss
must not be treated as a confirmed stop, and stale measurements must not be
reported as current values. No automatic startup or setpoint changes are
permitted merely because an integration is installed or restarted.

## HACS

The root `hacs.json` reserves the integration's display name. Runtime files will
live under `custom_components/sunex_nexus/`. Do not install this development
project as a custom repository: there is no Home Assistant runtime integration yet.

Release gates are tracked in [Development](docs/DEVELOPMENT.md), based on the
official [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
and [publication requirements](https://www.hacs.xyz/docs/publish/start/).

## Contributions

Use GitHub issues for implementation discussions and reproducible bugs. Do not
upload passwords, tokens, private network addresses, customer configuration,
raw diagnostic captures or private manufacturer correspondence. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

Original project code is licensed under the [MIT License](LICENSE). This does
not license manufacturer documents, trademarks or third-party material.
This is an independent project, not an official SUNEX product.
