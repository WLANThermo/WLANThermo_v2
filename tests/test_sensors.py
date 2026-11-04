"""Tests für wlanthermo.sensors (ohne Hardware).

Start: python3 -m unittest tests/test_sensors.py   (benötigt: pip install bitstring)
"""
import configparser
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.sensors import TemperatureSensor  # noqa: E402
from wlanthermo.sensors.adc import AdcChannel, AdcSampler, Mcp3208, median_filter  # noqa: E402
from wlanthermo.sensors.catalog import SensorType, load_sensor_types  # noqa: E402
from wlanthermo.sensors.maverick import MaverickFile, MaverickProbe, read_maverick  # noqa: E402
from wlanthermo.sensors.resistive import NtcProbe, PtProbe, ResistiveProbe, resistance_from_adc  # noqa: E402
from wlanthermo.sensors.thermocouple import Ad595Thermocouple, Max31855, Max31855Thermocouple  # noqa: E402

SENSOR_CONF = os.path.join(os.path.dirname(__file__), '..', 'software', 'var', 'www', 'conf', 'sensor.conf')
FANTAST = dict(a=3.3558340e-03, b=2.5698192e-04, c=1.6391056e-06, rn=50.08)


class FakePi:
    """MCP3208 an CS 25 mit festen Rohwerten, MAX31855 an allen anderen CS."""

    def __init__(self, adc=None, max31855=None):
        self.adc = adc or [0] * 8
        self.max31855 = max31855 or {}
        self.reads = []

    def bb_spi_xfer(self, cs, data):
        if cs == 25:
            channel = (struct.unpack('>H', data[:2])[0] >> 6) - 0x18
            self.reads.append(channel)
            value = self.adc[channel]
            value = next(value) if hasattr(value, '__next__') else value
            return 3, b'\x00' + struct.pack('>H', value)
        return 2, self.max31855[cs]


def channel_with(value):
    channel = AdcChannel(0)
    channel.samples = [value]
    return channel


class InterfaceTest(unittest.TestCase):
    def test_all_sensors_are_temperature_sensors(self):
        for cls in (NtcProbe, PtProbe, Ad595Thermocouple, Max31855Thermocouple, MaverickProbe):
            self.assertTrue(issubclass(cls, TemperatureSensor), cls)

    def test_abstract(self):
        with self.assertRaises(TypeError):
            TemperatureSensor()
        with self.assertRaises(TypeError):
            ResistiveProbe('x')


class NtcProbeTest(unittest.TestCase):
    def setUp(self):
        self.probe = NtcProbe('Fantast', **FANTAST)

    def test_nominal_resistance_gives_1_over_a(self):
        self.assertAlmostEqual(self.probe.temperature(50.08), 1 / 3.3558340e-03 - 273)

    def test_temperature_falls_with_resistance(self):
        self.assertGreater(self.probe.temperature(10), self.probe.temperature(100))

    def test_invalid_resistance(self):
        self.assertIsNone(self.probe.temperature(0))
        self.assertIsNone(self.probe.temperature(-5))

    def test_read_from_channel(self):
        # Spannungsteiler in der Mitte: Fühler = Messwiderstand = Rn
        probe = NtcProbe('Fantast', channel=channel_with(2048), resistor=50.08, **FANTAST)
        self.assertEqual(probe.read(), round(1 / 3.3558340e-03 - 273, 2))

    def test_read_out_of_range(self):
        for value in (0, 15, 4080, 4095):
            self.assertIsNone(NtcProbe('Fantast', channel=channel_with(value), resistor=47, **FANTAST).read())


class PtProbeTest(unittest.TestCase):
    def test_pt100_reference_points(self):
        probe = PtProbe('PT100', 0.1)
        self.assertAlmostEqual(probe.temperature(0.1), 0, places=6)
        # DIN EN 60751: 138,51 Ohm bei 100 °C
        self.assertAlmostEqual(probe.temperature(0.13851), 100, places=1)

    def test_pt1000_reference_points(self):
        probe = PtProbe('PT1000', 1.0)
        self.assertAlmostEqual(probe.temperature(1.0), 0, places=6)
        self.assertAlmostEqual(probe.temperature(1.3851), 100, places=1)

    def test_lead_compensation(self):
        self.assertAlmostEqual(PtProbe('PT1000', 1.0, rkomp=0.002).temperature(1.002), 0, places=6)

    def test_out_of_range(self):
        self.assertIsNone(PtProbe('PT100', 0.1).temperature(1000))


class ThermocoupleTest(unittest.TestCase):
    def test_ad595_10mv_per_degree(self):
        self.assertAlmostEqual(Ad595Thermocouple('KTYPE', channel=channel_with(2048)).read(), 165)
        self.assertIsNone(Ad595Thermocouple('KTYPE', channel=channel_with(10)).read())
        self.assertFalse(Ad595Thermocouple.voltage_divider)

    def test_max31855(self):
        pi = FakePi(max31855={8: struct.pack('>h', int(123.25 * 4) << 2), 7: struct.pack('>h', int(-10.5 * 4) << 2)})
        self.assertEqual(Max31855Thermocouple(Max31855(pi, 8)).read(), 123.25)
        self.assertEqual(Max31855(pi, 7).read(), -10.5)

    def test_max31855_fault_bit(self):
        self.assertIsNone(Max31855(FakePi(max31855={7: b'\x00\x01'}), 7).read())


class CatalogTest(unittest.TestCase):
    def test_shipped_sensor_conf(self):
        config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
        config.read(SENSOR_CONF, encoding='utf-8')
        types = load_sensor_types(config)
        self.assertEqual(set(types), set(config.sections()))
        self.assertEqual((types['9'].probe_class, types['9'].parameters['r0']), (PtProbe, 0.1))
        self.assertEqual(types['10'].probe_class, PtProbe)
        self.assertEqual(types['11'].probe_class, Ad595Thermocouple)
        self.assertEqual((types['1'].probe_class, types['1'].name), (NtcProbe, 'Fantast'))

    def test_create_binds_channel_and_resistor(self):
        channel = AdcChannel(3)
        probe = SensorType('Fantast', NtcProbe, **FANTAST).create(channel, 47)
        self.assertIsInstance(probe, NtcProbe)
        self.assertEqual((probe.name, probe.channel, probe.resistor, probe.rn), ('Fantast', channel, 47, 50.08))
        self.assertTrue(SensorType('Fantast', NtcProbe, **FANTAST).voltage_divider)
        self.assertFalse(SensorType('KTYPE', Ad595Thermocouple).voltage_divider)

    def test_invalid_section_is_skipped(self):
        config = configparser.ConfigParser()
        config.read_string('[1]\nname = X\na = 1\n[2]\nname = KTYPE\n')
        with self.assertLogs('WLANthermo.sensors', 'ERROR'):
            types = load_sensor_types(config)
        self.assertEqual(list(types), ['2'])


class AdcTest(unittest.TestCase):
    def test_mcp3208(self):
        pi = FakePi(adc=[0, 0, 0, 0, 0, 1234, 0, 0])
        self.assertEqual(Mcp3208(pi, 25).read(5), 1234)
        with self.assertRaises(ValueError):
            Mcp3208(pi, 25).read(8)

    def test_interleaved_sampling_and_inversion(self):
        pi = FakePi(adc=[1000] * 8)
        sampler = AdcSampler(Mcp3208(pi, 25), version='v3')
        sampler.sample([True, False] + [False] * 6, iterations=2)
        self.assertEqual(pi.reads, list(range(8)) * 2)
        self.assertEqual(sampler.channels[0].samples, [3095, 3095])
        self.assertEqual(sampler.channels[1].samples, [1000, 1000])

    def test_v1_not_inverted(self):
        sampler = AdcSampler(Mcp3208(FakePi(adc=[1000] * 8), 25), version='v1')
        sampler.sample([True] * 8, iterations=1)
        self.assertEqual(sampler.channels[0].samples, [1000])

    def test_samples_are_reset_each_cycle(self):
        sampler = AdcSampler(Mcp3208(FakePi(adc=[1000] * 8), 25), version='v1')
        sampler.sample([True] * 8, iterations=3)
        sampler.sample([True] * 8, iterations=2)
        self.assertEqual(len(sampler.channels[0].samples), 2)

    def test_noisy_channel_warns(self):
        adc = [iter([1000, 1100] * 5)] + [1000] * 7
        sampler = AdcSampler(Mcp3208(FakePi(adc=adc), 25), version='v3')
        with self.assertLogs('WLANthermo.sensors', 'WARNING'):
            sampler.sample([True] * 8, iterations=10)

    def test_resistance_from_adc(self):
        # Spannungsteiler in der Mitte: Fühler = Messwiderstand
        self.assertAlmostEqual(resistance_from_adc(2048, 47), 47)
        self.assertAlmostEqual(resistance_from_adc(1024, 47), 141)

    def test_median_filter_ignores_outliers(self):
        self.assertAlmostEqual(median_filter([100] * 47 + [0, 4095, 4095]), 100)

    def test_median_filter_averages_around_median(self):
        self.assertAlmostEqual(median_filter(list(range(50))), 25)

    def test_median_filter_few_values(self):
        self.assertEqual(median_filter([7]), 7)
        # früher begann der Bereich bei 2 Werten bei Index -1 und lieferte nur den größten Wert
        self.assertEqual(median_filter([10, 20]), 15)


class MaverickTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'maverick.json')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, text):
        with open(self.path, 'w') as f:
            f.write(text)

    def test_probes(self):
        self.write(json.dumps({'time': time.time(), 'temperature_1': 80.5, 'temperature_2': ''}))
        source = MaverickFile(self.path)
        probes = [MaverickProbe(source, 1), MaverickProbe(source, 2)]
        self.assertEqual([p.read() for p in probes], [None, None])   # noch nicht gelesen
        source.update()
        self.assertEqual([p.read() for p in probes], [80.5, None])

    def test_old_values_are_ignored(self):
        self.write(json.dumps({'time': time.time() - 31}))
        self.assertIsNone(read_maverick(self.path))

    def test_invalid_or_missing(self):
        self.write('{')
        with self.assertLogs('WLANthermo.sensors', 'ERROR'):
            self.assertIsNone(read_maverick(self.path))
        self.assertIsNone(read_maverick(os.path.join(self.dir, 'missing.json')))


if __name__ == '__main__':
    unittest.main()
