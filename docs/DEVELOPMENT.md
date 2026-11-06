# Development and release gates

## Current state

The public repository includes a shared protocol transport, documented register
decoding and bounded setpoint commands. Twenty-three synthetic tests cover both
transport and decoding. The Home Assistant runtime integration, external
controller interface and automated validation workflows remain unimplemented.
The protocol package has a development-only version; no HA release or
compatibility floor is declared.

The manufacturer's M-EVI register table has been reviewed, including visual
inspection of the temperature/setpoint tables. Several diagnostic addresses
conflict with M18 display observations; they are deliberately not assigned
engineering units until clarified. Private source documents remain local.

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
- [x] Test signed/unsigned decoding, scaling, bitfields and fault decoding.
- [ ] Implement UI setup, unique identities and duplicate-endpoint protection.
- [ ] Implement entity availability and redacted diagnostics.
- [x] Implement documented temperature setpoints with validation and readback.
- [ ] Implement remaining documented operating controls with bit preservation.
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

The shared transport successfully read the documented configuration and status
banks on an M18 EVI. A short heating setpoint reduction by one degree followed
by restoration succeeded using FC06 and independent FC03 readback. All 271
configuration words matched the baseline afterwards; no new fault flags were
reported and compressor/pump output indications stayed active. This verifies
the command path, not long-term thermal regulation or every operating mode.
Raw installation captures remain private. No HA or controller deployment is
claimed by this milestone.

## HACS default-repository submission

Only request inclusion after a usable release and successful validation against
the then-current HACS requirements. Creating this public repository is not an
HACS submission or acceptance. A custom-repository installation and inclusion
in the default catalog are separate milestones.
