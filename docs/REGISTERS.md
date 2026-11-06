# M-EVI register contracts

Addresses are zero-based. The development transport uses slave 1, RTU framing
over transparent TCP, 9600/8N1 on the gateway, at most 120 words per request and
300 ms between completed exchanges. Firmware/model applicability must be checked
before connecting another installation.

## Operating setpoints

| Purpose | Address | Whole-degree bounds | Controlled sensor |
| --- | --- | --- | --- |
| Heating | `0x0091` | 15-50 C | Water inlet / return (T3) |
| Cooling | `0x0090` | 7-30 C | Water inlet / return (T3) |
| Hot water | `0x008F` | 28-60 C | Tank (T2) |

`set_setpoint(mode, temperature, expected=previous)` checks the current value,
skips equal values, sends one FC06 and reads the same register again. It never
rounds fractional values or retries writes. A failed response does not prove
that the command was rejected: inspect the device before further changes.
The precondition check is not atomic against a person using the native display.

The manufacturer warns that parameter writes update nonvolatile memory. Do not
write on every polling cycle or implement a fast PID loop that continuously
rewrites targets. There is no generic public register-write API, manual actuator
override, factory reset or forced-defrost command in this implementation.

## Measurements

| Measurement | Address | Factor |
| --- | --- | --- |
| Water inlet | `0x800E` | 0.1 |
| Tank | `0x800F` | 0.5 |
| Ambient | `0x8011` | 0.5 |
| Water outlet | `0x8012` | 0.5 |
| Return gas | `0x8015` | 0.5 |
| Outdoor coil | `0x8016` | 0.5 |
| Cooling coil | `0x801A` | 0.5 |
| Discharge gas | `0x801B` | 1 |

Temperature decoding uses signed 16-bit words, consistent with the observed
negative temperatures. A dedicated sensor-fault flag makes the corresponding
measurement unavailable. Missing words are not substituted with zero. The
meaning of additional sentinel values is still awaiting manufacturer guidance.
The decoder is stateless: consumers must enforce timestamp freshness and
communication availability, and must not present cached values as current.

Confirmed telemetry also includes expansion-valve raw positions, compressor
frequency, DC bus voltage, target frequency and fan 1 speed. Pump speed remains
explicitly raw because its unit is not specified. Valve values are not doubled
using rules that apply to *configuration* registers instead of telemetry.

Output indications, input contact polarity, defrost and documented faults are
decoded separately. Output flags do not independently prove mechanical flow or
actuator operation. Unknown fault bits remain visible; inverter error octets
remain raw until the document's ambiguous `0xff` wording is clarified.

## Unresolved firmware differences

- The table reserves `0x8022` and `0x8023`; observations suggest heatsink
  temperature and compressor current respectively.
- The table places compressor current at `0x8025`, which does not match the
  observed current on the tested M18. Neither interpretation is exposed as a
  confirmed current sensor.
- `0x8027` is reserved in the table but appears to track fan 2. It stays raw.
- Reserved economizer temperatures are not exposed as valid measurements.
- No inferred power, COP or heat output is calculated without independently
  verified electrical and water-flow measurements.

## Acceptance scope

Documented reading and a bounded heating-setpoint change/restoration were tested
on one M18 EVI. Cooling and DHW writes have synthetic coverage only. Mode changes,
power commands, firmware compatibility, Home Assistant runtime and closed-loop
thermal control require separate acceptance. Communication loss leaves the
native controller using its last settings; it is not a verified stop mechanism.
