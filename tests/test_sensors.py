"""Tests für wlanthermo.sensors (ohne Hardware).

Start: python3 -m unittest tests/test_sensors.py tests/test_alarm.py
"""
import configparser
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.sensors import (KTypeSensor, NtcSensor, PtSensor, load_sensors,  # noqa: E402
                                median_filter, resistance_from_adc)

SENSOR_CONF = os.path.join(os.path.dirname(__file__), '..', 'software', 'var', 'www', 'conf', 'sensor.conf')


class NtcSensorTest(unittest.TestCase):
    def setUp(self):
        # Fantast aus sensor.conf
        self.sensor = NtcSensor('Fantast', 3.3558340e-03, 2.5698192e-04, 1.6391056e-06, 50.08)

    def test_nominal_resistance_gives_1_over_a(self):
        self.assertAlmostEqual(self.sensor.temperature(50.08), 1 / 3.3558340e-03 - 273)

    def test_temperature_falls_with_resistance(self):
        self.assertGreater(self.sensor.temperature(10), self.sensor.temperature(100))

    def test_invalid_resistance(self):
        self.assertIsNone(self.sensor.temperature(0))
        self.assertIsNone(self.sensor.temperature(-5))


class PtSensorTest(unittest.TestCase):
    def test_pt100_reference_points(self):
        sensor = PtSensor('PT100', 0.1)
        self.assertAlmostEqual(sensor.temperature(0.1), 0, places=6)
        # DIN EN 60751: 138,51 Ohm bei 100 °C
        self.assertAlmostEqual(sensor.temperature(0.13851), 100, places=1)

    def test_pt1000_reference_points(self):
        sensor = PtSensor('PT1000', 1.0)
        self.assertAlmostEqual(sensor.temperature(1.0), 0, places=6)
        self.assertAlmostEqual(sensor.temperature(1.3851), 100, places=1)

    def test_lead_compensation(self):
        sensor = PtSensor('PT1000', 1.0, rkomp=0.002)
        self.assertAlmostEqual(sensor.temperature(1.002), 0, places=6)

    def test_out_of_range(self):
        self.assertIsNone(PtSensor('PT100', 0.1).temperature(1000))


class KTypeSensorTest(unittest.TestCase):
    def test_ad595_10mv_per_degree(self):
        self.assertAlmostEqual(KTypeSensor('KTYPE').temperature_from_adc(2048), 165)


class LoadSensorsTest(unittest.TestCase):
    def test_shipped_sensor_conf(self):
        config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
        config.read(SENSOR_CONF, encoding='utf-8')
        sensors = load_sensors(config)
        self.assertEqual(set(sensors), set(config.sections()))
        self.assertIsInstance(sensors['9'], PtSensor)
        self.assertEqual(sensors['9'].r0, 0.1)
        self.assertIsInstance(sensors['10'], PtSensor)
        self.assertIsInstance(sensors['11'], KTypeSensor)
        self.assertIsInstance(sensors['1'], NtcSensor)
        self.assertEqual(sensors['1'].name, 'Fantast')

    def test_invalid_section_is_skipped(self):
        config = configparser.ConfigParser()
        config.read_string('[1]\nname = X\na = 1\n[2]\nname = KTYPE\n')
        with self.assertLogs('WLANthermo.sensors', 'ERROR'):
            sensors = load_sensors(config)
        self.assertEqual(list(sensors), ['2'])


class AdcTest(unittest.TestCase):
    def test_resistance_from_adc(self):
        # Spannungsteiler in der Mitte: Fühler = Messwiderstand
        self.assertAlmostEqual(resistance_from_adc(2048, 47), 47)
        self.assertAlmostEqual(resistance_from_adc(1024, 47), 141)

    def test_median_filter_ignores_outliers(self):
        self.assertAlmostEqual(median_filter([100] * 47 + [0, 4095, 4095]), 100)

    def test_median_filter_averages_around_median(self):
        values = list(range(50))
        self.assertAlmostEqual(median_filter(values), 25)

    def test_median_filter_few_values(self):
        self.assertEqual(median_filter([7]), 7)
        # früher begann der Bereich bei 2 Werten bei Index -1 und lieferte nur den größten Wert
        self.assertEqual(median_filter([10, 20]), 15)


if __name__ == '__main__':
    unittest.main()
