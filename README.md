# SUNEX NEXUS for Home Assistant

An independent, local-first Home Assistant integration for SUNEX NEXUS heat
pumps, intended for distribution through HACS.

## Development status

**Repository bootstrap only. No working integration or installable release is
published yet. This repository has not been submitted to or accepted by HACS.**

The initial implementation targets the NEXUS M18 EVI. Compatibility with other
models and firmware must be verified individually; similar product names are
not evidence of compatible registers.

The manufacturer has supplied interface documentation for implementation.
That correspondence and its attachments are not redistributed here. Live
communication, register decoding, command readback and recovery still require
verification before a release can be recommended.

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
bootstrap as a custom repository: there is no runtime implementation yet.

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
