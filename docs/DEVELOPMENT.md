# Development and release gates

## Current state

The public repository and project metadata exist. The runtime integration,
its protocol library and automated validation workflows are not implemented.
No version or compatibility floor has been declared without testing.

The manufacturer's interface description has been received privately. Exact
register contracts must be reviewed and converted into original implementation
and synthetic test cases. Private source documents are not part of this repo.

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
- [ ] Implement serialized Modbus transport and documented request spacing.
- [ ] Verify read-only communication on real supported hardware.
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

## HACS default-repository submission

Only request inclusion after a usable release and successful validation against
the then-current HACS requirements. Creating this public repository is not an
HACS submission or acceptance. A custom-repository installation and inclusion
in the default catalog are separate milestones.
