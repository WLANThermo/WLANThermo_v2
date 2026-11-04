"""Tests für wlanthermo.comp.settings (ohne Hardware).

Start: python3 -m unittest tests/test_settings.py
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.sensors.catalog import load_sensor_types  # noqa: E402
from wlanthermo.sensors.resistive import NtcProbe  # noqa: E402
from wlanthermo.comp.settings import (ConfigWatcher, make_parser, parse_settings,  # noqa: E402
                                 parse_startup_settings, read_config_file)

CONF_DIR = os.path.join(os.path.dirname(__file__), '..', 'software', 'var', 'www', 'conf')
CONFIG_FILE = os.path.join(CONF_DIR, 'WLANThermo.conf')
SENSOR_FILE = os.path.join(CONF_DIR, 'sensor.conf')


def load(path):
    config = make_parser()
    read_config_file(config, path)
    return config


class ShippedConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = load(CONFIG_FILE)
        self.sensors = load_sensor_types(load(SENSOR_FILE))

    def test_startup_settings(self):
        startup = parse_startup_settings(self.config)
        self.assertEqual(startup.channel_count, 10 if startup.version != 'miniV2' else 12)
        self.assertEqual(len(startup.pit_files), 2)

    def test_settings(self):
        settings = parse_settings(self.config, self.sensors, 10)
        self.assertEqual(len(settings.channels), 10)
        channel = settings.channels[0]
        self.assertEqual(channel.sensor_number, self.config.get('Sensoren', 'CH0'))
        self.assertEqual(channel.sensor_type.probe_class, NtcProbe)
        self.assertEqual(channel.resistor, 47)
        self.assertGreater(settings.iterations, 0)
        self.assertIn(settings.temp_unit, ('celsius', 'fahrenheit'))


class ParseSettingsTest(unittest.TestCase):
    def setUp(self):
        self.sensors = load_sensor_types(load(SENSOR_FILE))

    def config(self, **changes):
        config = load(CONFIG_FILE)
        for key, value in changes.items():
            section, option = key.split('__')
            config.set(section, option, value)
        return config

    def test_percent_in_values_is_not_interpolated(self):
        config = self.config(Push__push_on='True', Push__push_url='https://example.org/?a=%20{messagetext}')
        settings = parse_settings(config, self.sensors, 10)
        self.assertEqual(settings.push.url, 'https://example.org/?a=%20{messagetext}')

    def test_disabled_notifiers_are_none(self):
        config = self.config(Email__email_alert='False', Telegram__telegram_alert='False', Push__push_on='False')
        settings = parse_settings(config, self.sensors, 10)
        self.assertIsNone(settings.email)
        self.assertIsNone(settings.telegram)
        self.assertIsNone(settings.push)

    def test_invalid_values_fall_back(self):
        config = self.config(temp_min__temp_min0='x', temp_max__temp_max0='', Messen__messwiderstand0='?',
                             Alert__alarm_interval='never')
        with self.assertLogs('WLANthermo.settings', 'ERROR'):
            settings = parse_settings(config, self.sensors, 10)
        channel = settings.channels[0]
        self.assertEqual((channel.temp_min, channel.temp_max, channel.resistor), (-20, 200, 47))
        self.assertEqual(settings.alert.alarm_interval, 0)

    def test_unknown_sensor_type(self):
        with self.assertLogs('WLANthermo.settings', 'ERROR'):
            settings = parse_settings(self.config(), {}, 10)
        self.assertIsNone(settings.channels[0].sensor_type)


class ConfigWatcherTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'test.conf')
        self.write('[a]\nvalue = 1\n', mtime=1000)
        self.parsed = 0

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, text, mtime):
        with open(self.path, 'w') as f:
            f.write(text)
        os.utime(self.path, (mtime, mtime))

    def parse(self, config):
        self.parsed += 1
        return config.getint('a', 'value')

    def test_reads_only_when_changed(self):
        watcher = ConfigWatcher(self.path, self.parse)
        self.assertEqual(watcher.current(), 1)
        self.assertEqual(watcher.current(), 1)
        self.assertEqual(self.parsed, 1)
        self.write('[a]\nvalue = 2\n', mtime=2000)
        self.assertEqual(watcher.current(), 2)

    def test_removed_keys_disappear(self):
        watcher = ConfigWatcher(self.path, lambda c: c.has_option('a', 'value'))
        self.assertTrue(watcher.current())
        self.write('[a]\nother = 1\n', mtime=2000)
        self.assertFalse(watcher.current())

    def test_invalid_change_keeps_previous_settings(self):
        watcher = ConfigWatcher(self.path, self.parse)
        watcher.current()
        self.write('[a]\nvalue = x\n', mtime=2000)
        with self.assertLogs('WLANthermo.settings', 'ERROR'):
            self.assertEqual(watcher.current(), 1)
        # wird im nächsten Zyklus erneut versucht
        self.write('[a]\nvalue = 3\n', mtime=2000)
        self.assertEqual(watcher.current(), 3)

    def test_invalid_first_read_raises(self):
        self.write('[a]\nvalue = x\n', mtime=2000)
        with self.assertRaises(ValueError):
            ConfigWatcher(self.path, self.parse).current()


if __name__ == '__main__':
    unittest.main()
