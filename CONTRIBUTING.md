# Contributing

This integration is in development. No real heat-pump support is claimed until
it is verified against the relevant model and firmware.

- Keep protocol decoding independent of Home Assistant APIs where practical.
- Use a maintained Modbus library for framing and transport, not ad hoc packets.
- Treat register address, type, scaling, signedness, access rights and limits
  as explicit contracts with tests.
- Validate an entire command before writing. Do not retry ambiguous writes
  blindly; read back the affected state first where supported.
- Use synthetic test fixtures. Never publish credentials, customer-specific
  configuration, raw private captures or manufacturer emails/attachments.
- Document unavailable and stale data accurately. Zero is not a substitute
  for a failed measurement.
- Keep one serialized transport owner per physical bus and prevent conflicting
  control ownership between Home Assistant and external controllers.
- Preserve native protections and do not start equipment during setup/tests.

Before a release, run the Home Assistant/HACS validators and automated tests,
then record the scope of hardware verification without identifying the site.
