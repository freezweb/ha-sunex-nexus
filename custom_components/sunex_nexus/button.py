"""Manual acknowledgement of ambiguous commands, never a replay."""
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import NexusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NexusAcknowledge(entry.runtime_data, "acknowledge_write_lock")])


class NexusAcknowledge(NexusEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self):
        await self.coordinator.async_acknowledge()
