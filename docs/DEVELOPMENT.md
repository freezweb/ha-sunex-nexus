# Development and release gates

## Current state

The public repository includes a shared, read-only protocol transport and nine
synthetic TCP tests. The Home Assistant runtime integration, writable controls
and automated validation workflows are not implemented. The protocol package
has a development-only version; no HA release or compatibility floor is declared.

The manufacturer's transport description has been received privately, but the
referenced register table was absent. Exact register contracts must be obtained,
reviewed and converted into original implementation and synthetic test cases.
Private source documents are not part of this repo.

## Planned layout

```text
custom_components/sunex_nexus/
    __init__.py
    manifest.json
    config_flow.py
    coordinator.py
    diagnostics.py
    translations/
tests/
hacs.json
```

Runtime dependencies must be installable through the integration manifest or
included within the integration directory. The external heating-controller
consumer must use the same tested protocol contracts, not a divergent register
copy. The packaging boundary will be chosen with the runtime implementation.

## Before the first usable release

- [ ] Map documented registers, access rights, limits and firmware applicability.
- [x] Implement serialized read-only Modbus transport and request spacing.
- [x] Verify read-only communication on an NEXUS M18 EVI using RTU-over-TCP.
- [ ] Test signed/unsigned decoding, scaling, bitfields and fault decoding.
- [ ] Implement UI setup, unique identities and duplicate-endpoint protection.
- [ ] Implement entity availability and redacted diagnostics.
- [ ] Implement documented writable controls with validation and readback.
- [ ] Define command ownership for HA and the external controller.
- [ ] Test timeout, reconnection, unload and restart behavior without startup writes.
- [ ] Verify commands and unchanged safety protections on commissioned hardware.
- [ ] Add CI for tests, Home Assistant validation and HACS validation.
- [ ] Provide permitted brand assets and English/German UI strings.
- [ ] Document installation, supported models and known limitations.
- [ ] Review all tracked files for secrets and private source material.
- [ ] Publish a versioned release with a precise hardware-verification statement.

## Shared package boundary

`custom_components/sunex_nexus/protocol/` is HA-independent. The development
package exposes this exact source as `sunex_nexus_protocol` to the external
controller; HA will use a relative import. Do not maintain a second protocol
copy. Installation of the package alone does not start any worker or connect
to a gateway. One process must own the physical bus; in-process endpoint
protection is not a cross-process or hostname-alias lock.

## Hardware evidence scope

The shared transport successfully read two raw registers on an M18 EVI after
an independent read-only address inventory. This proves basic FC03 framing and
response handling on that installation, not temperature interpretation, write
permissions, controller behavior or compatibility with other firmware. No
write/control test has been performed. Raw installation captures remain private.

## HACS default-repository submission

Only request inclusion after a usable release and successful validation against
the then-current HACS requirements. Creating this public repository is not an
HACS submission or acceptance. A custom-repository installation and inclusion
in the default catalog are separate milestones.
