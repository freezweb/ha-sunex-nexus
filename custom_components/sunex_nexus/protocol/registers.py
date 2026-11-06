"""Verified M-EVI operating registers; no guessed firmware-specific aliases.

The privately supplied M-EVI table and manufacturer clarification distinguish
the inlet-controlled heating target from the measured outlet temperature.
Reserved registers and conflicting diagnostic fields intentionally stay raw.
"""
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping


def word(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError("Expected an unsigned 16-bit register")
    return value


def signed(value: int) -> int:
    value = word(value)
    return value - 65536 if value & 0x8000 else value


@dataclass(frozen=True)
class Measurement:
    key: str
    address: int
    scale: float = 1
    signed: bool = False
    unit: str | None = None
    fault: tuple[int, int] | None = None

    def decode(self, registers: Mapping[int, int]) -> int | float | None:
        if self.address not in registers:
            return None
        if self.fault is not None:
            address, bit = self.fault
            # Missing fault flags must not make a sensor look valid.
            if address not in registers or word(registers[address]) & (1 << bit):
                return None
        raw = signed(registers[self.address]) if self.signed else word(registers[self.address])
        return round(raw * self.scale, 6)


MEASUREMENTS = (
    Measurement("water_inlet_temperature", 0x800E, .1, True, "C", (0x800A, 0)),
    Measurement("water_outlet_temperature", 0x8012, .5, True, "C", (0x8007, 4)),
    Measurement("tank_temperature", 0x800F, .5, True, "C", (0x8007, 0)),
    Measurement("ambient_temperature", 0x8011, .5, True, "C", (0x8007, 1)),
    Measurement("return_gas_temperature", 0x8015, .5, True, "C", (0x800A, 6)),
    Measurement("outdoor_coil_temperature", 0x8016, .5, True, "C", (0x8007, 2)),
    Measurement("cooling_coil_temperature", 0x801A, .5, True, "C", (0x800B, 3)),
    Measurement("discharge_gas_temperature", 0x801B, 1, True, "C", (0x8009, 6)),
    Measurement("main_expansion_valve", 0x801C),
    Measurement("auxiliary_expansion_valve", 0x801D),
    Measurement("compressor_frequency", 0x801E, unit="Hz"),
    Measurement("dc_bus_voltage", 0x8021, unit="V"),
    Measurement("target_frequency", 0x8024, unit="Hz"),
    Measurement("fan_1_speed", 0x8026, unit="rpm"),
    # Units of the DC pump register are not stated in the supplied table.
    Measurement("dc_pump_speed_raw", 0x802A),
)

FAULTS = MappingProxyType({
    (0x8007, 0): "Er14_tank_sensor", (0x8007, 1): "Er21_ambient_sensor",
    (0x8007, 2): "Er16_outdoor_coil_sensor", (0x8007, 4): "Er27_outlet_sensor",
    (0x8007, 5): "Er05_high_pressure", (0x8007, 6): "Er06_low_pressure",
    (0x8008, 0): "Er03_water_flow", (0x8008, 2): "Er32_heating_water_overtemperature",
    (0x8009, 6): "Er18_discharge_sensor", (0x800A, 0): "Er15_inlet_sensor",
    (0x800A, 1): "Er12_discharge_overtemperature", (0x800A, 5): "Er23_cooling_outlet_undertemperature",
    (0x800A, 6): "Er29_return_gas_sensor", (0x800B, 0): "Er69_low_pressure_protection",
    (0x800B, 2): "Er33_coil_overtemperature", (0x800B, 3): "Er42_cooling_coil_sensor",
    (0x800B, 7): "Er67_low_pressure_sensor", (0x800C, 4): "secondary_antifreeze",
    (0x800C, 5): "primary_antifreeze", (0x800D, 4): "Er10_inverter_communication",
    (0x800D, 5): "Er66_fan_2", (0x800D, 6): "Er64_fan_1",
})

FAULT_REGISTERS = (*range(0x8007, 0x800E), 0x801F, 0x8020)


def fault_codes(registers: Mapping[int, int]) -> tuple[str, ...] | None:
    """Return None for incomplete evidence; preserve unknown/reserved bits.

    Inverter octets stay raw because the document's 0xff wording is ambiguous.
    Nonzero unknown flags are never silently reported as healthy.
    """
    if any(address not in registers for address in FAULT_REGISTERS):
        return None
    result = []
    for address in FAULT_REGISTERS:
        raw = word(registers[address])
        if address in (0x801F, 0x8020):
            if raw:
                result.append(f"inverter_raw_{address:04x}_{raw:04x}")
            continue
        for bit in range(16):
            if raw & (1 << bit):
                result.append(FAULTS.get((address, bit), f"unknown_{address:04x}_bit_{bit}"))
    return tuple(result)


@dataclass(frozen=True)
class Setpoint:
    key: str
    address: int
    minimum: int
    maximum: int

    def encode(self, value: float) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Setpoint must be a finite temperature")
        if value != int(value) or not self.minimum <= value <= self.maximum:
            raise ValueError(f"Setpoint requires whole degrees between {self.minimum} and {self.maximum}")
        return int(value)


SETPOINTS = MappingProxyType({
    "heating": Setpoint("heating", 0x0091, 15, 50),
    "cooling": Setpoint("cooling", 0x0090, 7, 30),
    "hot_water": Setpoint("hot_water", 0x008F, 28, 60),
})

MODES = MappingProxyType({0: "hot_water", 1: "heating", 2: "cooling",
                          3: "hot_water_heating", 4: "hot_water_cooling"})


def decode(registers: Mapping[int, int]) -> dict:
    """Decode only confirmed fields, without changing device state."""
    result = {item.key: item.decode(registers) for item in MEASUREMENTS}
    result["faults"] = fault_codes(registers)
    result["mode"] = MODES.get(registers.get(4))
    for name, target in SETPOINTS.items():
        raw = registers.get(target.address)
        result[name + "_setpoint"] = raw if raw is not None and target.minimum <= raw <= target.maximum else None
    for name, address, bit, inverted in (
        ("enabled", 0, 0, False), ("defrost", 0x8003, 7, False),
        ("compressor_running", 0x8004, 0, False), ("fan_running", 0x8004, 5, False),
        ("pump_running", 0x8006, 0, False), ("flow_switch_closed", 0x8002, 2, True),
        ("evu_contact_closed", 0x8002, 5, True), ("sg_contact_closed", 0x8002, 6, True),
    ):
        result[name] = None if address not in registers else bool(word(registers[address]) & (1 << bit)) != inverted
    return result
