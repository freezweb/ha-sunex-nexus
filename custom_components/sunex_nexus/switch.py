"""Explicit normal commands; no switch action on setup or reload."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .const import OPERATING_FIELDS
from .entity import NexusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NexusSwitch(entry.runtime_data, key) for key in OPERATING_FIELDS]
                       + [NexusServiceEdit(entry.runtime_data, "service_edit")])


class NexusSwitch(NexusEntity, SwitchEntity):
    @property
    def is_on(self):
        address, mask = OPERATING_FIELDS[self.key]
        return bool(self.coordinator.data["raw"][address] & mask)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_command("operating", self.key, 1)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_command("operating", self.key, 0)


class NexusServiceEdit(NexusSwitch):
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return self.coordinator.service_allowed

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_service_edit(True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_service_edit(False)
