# Development and release verification

## Architecture

The native integration runs without MQTT or an external heating controller.
Its coordinator owns one serialized RTU-over-TCP client and publishes only
complete snapshots. Entity setup never writes to the device. Polling and whole
command transactions use one coordinator lock. Partial reads are discarded.

The HA-independent protocol lives in `custom_components/sunex_nexus/protocol`.
The external heating controller remains a separate application and may package
this library independently. It is neither started nor modified by this plugin.
Never run both applications as masters of the same physical bus. The in-process
endpoint guard cannot arbitrate another process, hostname alias or RS485 master.

## Command persistence

Home Assistant's standard `.storage` API stores only an uncertainty marker and
write timestamps, not credentials or a new SQL database. The pending marker is
saved before sending. Failure, cancellation or process death leaves writes
locked until an operator acknowledges after a successful fresh read. The
temporary service-edit window is never restored after restart.

## Release gates

- Native config flow, entity platforms, EN/DE translations and local brand icon.
- Protocol tests: actual framed TCP exchanges, fragmentation, timeout, concurrent
  clients, no-op suppression, precondition conflict, signed/scaled data and faults.
- Native HA tests: setup/unload, all entity registration, actual number service,
  read-only default, unavailable/recovery, persistent write lock, acknowledgement,
  service window, stale-data and write-budget guards, sanitized diagnostics.
- HACS action without ignored checks and hassfest must pass before submission.
- Publish a GitHub release, not just a tag, after successful validation.
- Submit an editable PR from a dedicated branch to `hacs/default`.
- Preserve a precise distinction between submission and maintainer acceptance.

## Jenkins validation

The repository includes a dedicated Jenkins pipeline with isolated Python 3.14.5
environments, native HA tests, and the unmodified official hassfest/HACS
validators pinned by source commit in `scripts/ci_validate.py`. No checks are
ignored. Reports record the tested integration commit and validator source
commits. The job checks for changes on `main` every 15 minutes; it does not run
untrusted pull-request branches with credentials and never accesses a heat pump.

The HACS validator reads a protected Jenkins GitHub credential at runtime.
It is never stored in the repository or passed as a command-line argument.
Release assets can contain reviewed validation reports, but not private Jenkins
console logs or customer configuration.

The GitHub workflows are also present. Passing the validators on Jenkins is
technical validation, not a claim that GitHub Actions passed. HACS default-catalog
submission separately requires successful GitHub Actions under its published
policy, or prior agreement from HACS maintainers to accept another CI provider.
Custom-repository installation does not imply default-catalog acceptance.

## Physical evidence and remaining limitations

On one M18 EVI the shared protocol read all documented banks and changed the
heating target by one degree, then restored it. All 271 configuration words
matched baseline afterwards. No new native fault was observed. This proves a
bounded protocol command, not every service field or thermal performance.

The native component is validated in isolated HA tests; production continues
using its existing independent controller. Activating the native component on
that same gateway requires coordinated ownership handover, not parallel polling.
No pool regulator is shipped in this integration. Contradictory or undocumented
registers stay raw/read-only. Manufacturer correspondence remains private.
