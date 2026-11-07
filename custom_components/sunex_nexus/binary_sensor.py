"""Documented operating flags and persistent command uncertainty."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import EntityCategory

from .const import BINARY_KEYS
from .entity import NexusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NexusBinary(entry.runtime_data, key) for key in BINARY_KEYS]
                       + [NexusWriteLock(entry.runtime_data, "write_lock")])


class NexusBinary(NexusEntity, BinarySensorEntity):
    @property
    def is_on(self):
        return self.coordinator.data["decoded"].get(self.key)


class NexusWriteLock(NexusBinary):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.write_locked
