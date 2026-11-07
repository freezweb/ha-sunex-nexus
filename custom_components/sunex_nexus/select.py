"""All five documented modes, changeable only while stopped."""
from homeassistant.components.select import SelectEntity

from .entity import NexusEntity
from .protocol.registers import MODES


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NexusMode(entry.runtime_data, "mode")])


class NexusMode(NexusEntity, SelectEntity):
    _attr_options = list(MODES.values())

    @property
    def current_option(self):
        return self.coordinator.data["decoded"]["mode"]

    async def async_select_option(self, option):
        value = next(key for key, name in MODES.items() if name == option)
        await self.coordinator.async_command("operating", "mode", value)
