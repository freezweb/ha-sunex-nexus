"""Bounded targets and opt-in, unit-off service parameter edits."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from .entity import NexusEntity
from .protocol.catalog import CATALOG
from .protocol.registers import SETPOINTS, signed


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NexusTarget(entry.runtime_data, key, target) for key, target in SETPOINTS.items()]
                       + [NexusParameter(entry.runtime_data, row) for row in CATALOG if row["access"] == "service"])


class NexusTarget(NexusEntity, NumberEntity):
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, key, target):
        super().__init__(coordinator, key + "_setpoint")
        self.target_mode = key
        self._attr_native_min_value = target.minimum
        self._attr_native_max_value = target.maximum

    @property
    def native_value(self):
        return self.coordinator.data["decoded"][self.key]

    async def async_set_native_value(self, value):
        await self.coordinator.async_command("setpoint", self.target_mode, value)


class NexusParameter(NexusEntity, NumberEntity):
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, row):
        super().__init__(coordinator, f"parameter_{row['hex'].lower()}")
        self._attr_translation_key = None
        self._attr_name = f"{row['hex']} {row['name']} (service raw)"
        self.address = row["address"]
        self._attr_native_min_value, self._attr_native_max_value = row["bounds"]

    @property
    def native_value(self):
        value = self.coordinator.data["raw"].get(self.address)
        if value is not None and self.native_min_value < 0:
            value = signed(value)
        return value

    async def async_set_native_value(self, value):
        await self.coordinator.async_command("parameter", self.address, value)
