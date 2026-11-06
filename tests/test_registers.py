"""Synthetic register fixtures; no private installation captures."""
import unittest
from sunex_nexus_protocol.registers import decode, signed, SETPOINTS, MEASUREMENTS, fault_codes


class RegisterTests(unittest.TestCase):
    def bank(self):
        return {**dict.fromkeys(range(0x8000, 0x802B), 0), 0: 0x40, 4: 1,
                0x8F: 45, 0x90: 12, 0x91: 35}

    def test_temperature_scales_signed_and_sensors(self):
        bank = self.bank()
        bank.update({0x800E: 312, 0x8012: 83, 0x8011: 0xFFF5,
                     0x8015: 0xFFFA, 0x801B: 81})
        data = decode(bank)
        self.assertEqual(data['water_inlet_temperature'], 31.2)
        self.assertEqual(data['water_outlet_temperature'], 41.5)
        self.assertEqual(data['ambient_temperature'], -5.5)
        self.assertEqual(data['return_gas_temperature'], -3)
        self.assertEqual(data['discharge_gas_temperature'], 81)

    def test_no_invented_values_for_missing_data(self):
        self.assertTrue(all(value is None for value in decode({}).values()))
        self.assertIsNone(fault_codes({0x8007: 0}))

    def test_faulty_sensor_unavailable_others_preserved(self):
        bank = self.bank()
        bank.update({0x800E: 300, 0x8012: 80, 0x800A: 1})
        data = decode(bank)
        self.assertIsNone(data['water_inlet_temperature'])
        self.assertEqual(data['water_outlet_temperature'], 40)
        self.assertEqual(data['faults'], ('Er15_inlet_sensor',))

    def test_unknown_fault_bits_are_not_healthy(self):
        bank = self.bank()
        bank.update({0x8008: 1, 0x8009: 0x8000, 0x801F: 0xFF})
        faults = fault_codes(bank)
        self.assertIn('Er03_water_flow', faults)
        self.assertIn('unknown_8009_bit_15', faults)
        self.assertIn('inverter_raw_801f_00ff', faults)

    def test_contact_polarity_and_output_flags(self):
        bank = self.bank()
        bank.update({0: 65, 0x8002: 4, 0x8003: 128, 0x8004: 33, 0x8006: 1})
        data = decode(bank)
        self.assertTrue(data['enabled'])
        self.assertTrue(data['compressor_running'])
        self.assertTrue(data['fan_running'])
        self.assertTrue(data['pump_running'])
        self.assertTrue(data['defrost'])
        self.assertFalse(data['flow_switch_closed'])
        self.assertTrue(data['evu_contact_closed'])

    def test_ambiguous_registers_not_exposed(self):
        addresses = {x.address for x in MEASUREMENTS}
        self.assertFalse(addresses & {0x8013, 0x8014, 0x8022, 0x8023, 0x8025, 0x8027})

    def test_setpoint_bounds_and_nonfinite(self):
        for target in SETPOINTS.values():
            self.assertEqual(target.encode(target.minimum), target.minimum)
            self.assertEqual(target.encode(target.maximum), target.maximum)
            for value in [target.minimum - 1, target.maximum + 1, True, '35', float('inf'), float('nan'), 30.5]:
                with self.assertRaises(ValueError):
                    target.encode(value)

    def test_words_signed_and_invalid(self):
        self.assertEqual(signed(0xFFFF), -1)
        self.assertEqual(signed(0x8000), -32768)
        for value in [-1, 65536, True, 2.5]:
            with self.assertRaises(ValueError):
                signed(value)


if __name__ == '__main__':
    unittest.main()
