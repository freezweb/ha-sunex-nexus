"""Support data without hostnames, network endpoints or entry identifiers."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "profile": "M-EVI",
        "last_update_success": coordinator.last_update_success,
        "write_locked": coordinator.write_locked,
        "writes_allowed": coordinator.writes_allowed,
        "writes_in_window": len(coordinator.writes),
        "data": coordinator.data,
    }
