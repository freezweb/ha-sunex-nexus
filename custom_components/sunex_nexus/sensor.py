"""Decoded measurements and the entire documented raw register inventory."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature

from .entity import NexusEntity
from .protocol.catalog import CATALOG
from .protocol.registers import MEASUREMENTS


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([NexusMeasurement(coordinator, item) for item in MEASUREMENTS]
                       + [NexusRaw(coordinator, row) for row in CATALOG]
                       + [NexusFaults(coordinator)])


class NexusMeasurement(NexusEntity, SensorEntity):
    def __init__(self, coordinator, item):
        super().__init__(coordinator, item.key)
        if item.unit:
            self._attr_native_unit_of_measurement = item.unit
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if item.unit == "C":
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif item.unit == "V":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif item.unit == "Hz":
            self._attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def native_value(self):
        return self.coordinator.data["decoded"].get(self.key)


class NexusRaw(NexusEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, row):
        super().__init__(coordinator, f"raw_{row['hex'].lower()}")
        self._attr_translation_key = None
        self._attr_name = f"{row['hex']} {row['name']} (raw)"
        self.address = row["address"]

    @property
    def native_value(self):
        return self.coordinator.data["raw"].get(self.address)


class NexusFaults(NexusEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "faults")

    @property
    def native_value(self):
        faults = self.coordinator.data["decoded"]["faults"]
        return len(faults) if faults is not None else None

    @property
    def extra_state_attributes(self):
        return {"codes": self.coordinator.data["decoded"]["faults"]}
