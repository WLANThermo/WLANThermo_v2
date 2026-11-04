"""Tests für wlanthermo.core.hub.

Start: python3 -m unittest tests/test_hub.py
"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.core.hub import DataHub, Measurement, PitState, pit_topic  # noqa: E402


class DataHubTest(unittest.TestCase):
    def test_latest(self):
        hub = DataHub()
        self.assertIsNone(hub.latest('measurement'))
        hub.publish('measurement', 1)
        hub.publish('measurement', 2)
        self.assertEqual(hub.latest('measurement'), 2)

    def test_changes_since(self):
        hub = DataHub()
        hub.publish('a', 1)
        seq = hub.sequence
        hub.publish('b', 2)
        hub.publish('a', 3)
        sequence, changed = hub.changes(seq, timeout=0)
        self.assertEqual(changed, {'a': 3, 'b': 2})
        self.assertEqual(hub.changes(sequence, timeout=0), (sequence, {}))

    def test_topic_filter(self):
        hub = DataHub()
        hub.publish(pit_topic(0), 'p')
        hub.publish('measurement', 'm')
        self.assertEqual(hub.changes(0, timeout=0, topics=['pit/'])[1], {'pit/0': 'p'})

    def test_waits_for_change(self):
        hub = DataHub()
        threading.Timer(0.05, hub.publish, ('measurement', 'neu')).start()
        start = time.monotonic()
        _, changed = hub.changes(0, timeout=5)
        self.assertEqual(changed, {'measurement': 'neu'})
        self.assertLess(time.monotonic() - start, 1)

    def test_timeout_without_change(self):
        start = time.monotonic()
        self.assertEqual(DataHub().changes(0, timeout=0.05), (0, {}))
        self.assertGreaterEqual(time.monotonic() - start, 0.04)


class ValuesTest(unittest.TestCase):
    def test_measurement(self):
        m = Measurement(time=100, temperatures=(20.5, None), statuses=('ok', 'er'), unit='celsius')
        self.assertEqual(m.age(now=103), 3)
        self.assertEqual((m.temperature(0), m.temperature(1), m.temperature(5), m.temperature(-1)),
                         (20.5, None, None, None))

    def test_pit_state(self):
        self.assertEqual(PitState(0, 10, 110, None, 0, '').age(now=12), 2)


if __name__ == '__main__':
    unittest.main()
