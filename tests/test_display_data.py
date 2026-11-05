"""Tests für wlanthermo.display.data: Werte vom Kernprozess oder aus den Dateien.

Start: python3 -m unittest tests/test_display_data.py
"""
import dataclasses
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.core.api import Api, ApiServer  # noqa: E402
from wlanthermo.core.client import CoreClient  # noqa: E402
from wlanthermo.core.hub import MEASUREMENT, DataHub, Measurement, PitState, pit_topic  # noqa: E402
from wlanthermo.display import data  # noqa: E402

STAMP = time.mktime(time.strptime('24.10.18 18:30:12', '%d.%m.%y %H:%M:%S'))


def as_json(value):
    return json.loads(json.dumps(dataclasses.asdict(value)))


class FormatTest(unittest.TestCase):
    """Gleiche Daten ergeben aus beiden Quellen genau dasselbe Format."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, 'w') as f:
            f.write(text)
        return path

    def test_temps(self):
        temps = (74.21000000000001, None, 20.049, 99.95)
        statuses = ('hi', 'er', 'ok', 'lo')
        line = ';'.join(['24.10.18 18:30:12'] + ['%.2f' % t if t is not None else '' for t in temps]
                        + list(statuses) + ['V', 'log'])
        from_file = data.temps_from_file(self.write('current.temp', line), 4)
        m = as_json(Measurement(STAMP + 0.7, temps, statuses, 'celsius'))
        self.assertEqual(data.temps_from_measurement(m, 4), from_file)
        self.assertEqual(from_file[0], {'alert': 'hi', 'value': '74.2'})
        self.assertEqual(from_file[1], {'alert': 'er', 'value': None})

    def test_pitmaster(self):
        for output in (0, 45.0, 100):
            path = self.write('pit.temp', '24.10.18 18:30:12;110.0;98.5;{}%;|current: 98.5|x;y'.format(output))
            state = as_json(PitState(0, STAMP + 0.2, 110.0, 98.5, output, '|current: 98.5|x;y'))
            self.assertEqual(data.pitmaster_from_state(state), data.pitmaster_from_file(path))
        path = self.write('pit.temp', '24.10.18 18:30:12;110.0;;0%;|no probe')
        self.assertIsNone(data.pitmaster_from_file(path)['now'])
        self.assertIsNone(data.pitmaster_from_file(os.path.join(self.dir, 'missing')))


class DisplayDataTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.dir, 'current.temp')
        self.pit_file = os.path.join(self.dir, 'pit.temp')
        self.config_file = os.path.join(self.dir, 'WLANThermo.conf')
        with open(self.config_file, 'w') as f:
            f.write('[a]\nb = 1\n')
        self.socket = os.path.join(self.dir, 'core.sock')
        self.hub = DataHub()
        self.server = None
        self.changes = []
        self.changed = threading.Condition()
        self.display = data.DisplayData(self.on_change, self.temp_file, [self.pit_file], self.config_file,
                                        client=CoreClient(self.socket, timeout=2), poll=0.05)
        self.display.RETRY = 0.3

    def tearDown(self):
        self.display.stop()
        if self.server is not None:
            self.server.close()
        shutil.rmtree(self.dir)

    def on_change(self, name):
        with self.changed:
            self.changes.append(name)
            self.changed.notify_all()

    def wait_for(self, name, timeout=3):
        with self.changed:
            return self.changed.wait_for(lambda: name in self.changes, timeout)

    def start_core(self):
        self.server = ApiServer(Api(self.hub), self.socket, group='nogroup-does-not-exist')
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def test_live_values_from_core(self):
        self.start_core()
        self.display.start()
        self.hub.publish(MEASUREMENT, Measurement(time.time(), (100.0, None), ('ok', 'er'), 'celsius'))
        self.assertTrue(self.wait_for('temps'))
        self.assertTrue(self.display.connected)
        self.assertEqual(self.display.temps(2)[0]['value'], '100.0')
        self.hub.publish(pit_topic(0), PitState(0, time.time(), 110.0, 100.0, 30.0, '|x'))
        self.assertTrue(self.wait_for('pit'))
        self.assertEqual(self.display.pitmaster(0)['new'], 30.0)
        self.changes.clear()
        self.hub.publish(pit_topic(0), None)
        self.assertTrue(self.wait_for('pit'))
        self.assertIsNone(self.display.pitmaster(0))

    def test_files_without_core(self):
        self.display.start()
        time.sleep(0.2)
        self.assertFalse(self.display.connected)
        with open(self.temp_file, 'w') as f:
            f.write('24.10.18 18:30:12;55.00;ok;V;log')
        self.assertTrue(self.wait_for('temps'))
        self.assertEqual(self.display.temps(1)[0]['value'], '55.0')

    def test_config_change(self):
        self.display.start()
        time.sleep(0.2)
        with open(self.config_file, 'w') as f:
            f.write('[a]\nb = 2\n')
        os.utime(self.config_file, (time.time() + 5, time.time() + 5))
        self.assertTrue(self.wait_for('config'))

    def test_switches_to_core_when_it_starts(self):
        self.display.start()
        time.sleep(0.2)
        self.assertFalse(self.display.connected)
        self.start_core()
        self.hub.publish(MEASUREMENT, Measurement(time.time(), (42.0,), ('ok',), 'celsius'))
        deadline = time.monotonic() + 3
        while not self.display.connected and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.display.connected)
        self.assertTrue(self.wait_for('temps'))
        self.assertEqual(self.display.temps(1)[0]['value'], '42.0')


if __name__ == '__main__':
    unittest.main()
