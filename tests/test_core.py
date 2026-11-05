"""Tests für den Kernprozess: Pitmaster am DataHub, Quellen für comp, Verwaltung.

Start: python3 -m unittest tests/test_core.py   (benötigt: pip install pigpio bitstring psutil)
"""
import builtins
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.config import make_parser, read_config_file  # noqa: E402
from wlanthermo.core import service  # noqa: E402
from wlanthermo.core.hub import MEASUREMENT, DataHub, Measurement, PitState, pit_topic  # noqa: E402
from wlanthermo.core.sources import MAVERICK, MaverickHubSource, PitHubReader  # noqa: E402
from wlanthermo.pitmaster.inputs import HubInput  # noqa: E402
from wlanthermo.sensors.maverick.receiver import Reading  # noqa: E402

LOG = logging.getLogger('test.core')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'software', 'var', 'www', 'conf', 'WLANThermo.conf')


def measurement(age=0, temps=(100.123, None), statuses=('ok', 'er')):
    return Measurement(time=time.time() - age, temperatures=temps, statuses=statuses, unit='celsius')


class HubInputTest(unittest.TestCase):
    def setUp(self):
        self.hub = DataHub()
        self.input = HubInput(self.hub, max_age=15, logger=LOG)

    def test_waits_for_first_measurement(self):
        self.assertFalse(self.input.available())
        self.hub.publish(MEASUREMENT, measurement())
        self.assertTrue(self.input.available())

    def test_value_rounded_like_the_file(self):
        self.hub.publish(MEASUREMENT, measurement())
        self.assertEqual(self.input.value(0), (100.12, ''))

    def test_no_probe(self):
        self.hub.publish(MEASUREMENT, measurement())
        with self.assertLogs(LOG, 'INFO'):
            now, msg = self.input.value(1)
        self.assertIsNone(now)
        self.assertIn('no probe connected to channel 1', msg)

    def test_stale_measurement_is_invalid(self):
        self.hub.publish(MEASUREMENT, measurement(age=20))
        with self.assertLogs(LOG, 'ERROR'):
            now, msg = self.input.value(0)
        self.assertIsNone(now)
        self.assertIn('no current measurement for 20s', msg)


class SourcesTest(unittest.TestCase):
    def test_maverick(self):
        hub = DataHub()
        source = MaverickHubSource(hub)
        source.update()
        self.assertIsNone(source.values)
        hub.publish(MAVERICK, Reading(time.time(), 0x1234, 'et732', 80, ''))
        source.update()
        self.assertEqual((source.values['temperature_1'], source.values['temperature_2']), (80, ''))
        hub.publish(MAVERICK, Reading(time.time() - 31, 0x1234, 'et732', 80, ''))
        source.update()
        self.assertIsNone(source.values)

    def test_pit_values_like_the_file(self):
        hub = DataHub()
        reader = PitHubReader(hub, 1)
        self.assertIsNone(reader.read())
        hub.publish(pit_topic(1), PitState(1, time.time(), 110.0, 98.5, 45.0, ''))
        self.assertEqual(reader.read(), ('45.0', '110.0'))
        hub.publish(pit_topic(1), None)   # Pitmaster gestoppt
        self.assertIsNone(reader.read())


class ManagerTest(unittest.TestCase):
    def setUp(self):
        builtins._ = lambda text: text
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'WLANThermo.conf')
        shutil.copy(CONFIG_FILE, self.path)
        self.started = []
        self.receivers = []
        self.mtime = time.time()
        self.set(Hardware={'version': 'miniV2'})

    def tearDown(self):
        shutil.rmtree(self.dir)
        del builtins._

    def set(self, **sections):
        config = make_parser()
        read_config_file(config, self.path)
        for section, values in sections.items():
            for key, value in values.items():
                config.set(section, key, value)
        with open(self.path, 'w') as f:
            config.write(f)
        # mtime muss sich ändern, damit der ConfigWatcher neu liest
        self.mtime += 10
        os.utime(self.path, (self.mtime, self.mtime))

    def create_pitmaster(self, instance, max_age, stop_event):
        pitmaster = mock.Mock(instance=instance, max_age=max_age)
        pitmaster.run.side_effect = lambda: stop_event.wait(10)
        self.started.append(pitmaster)
        return pitmaster

    def create_receiver(self):
        receiver = mock.Mock()
        self.receivers.append(receiver)
        return receiver

    def manager(self):
        return service.Manager(DataHub(), on_failure=mock.Mock(), create_pitmaster=self.create_pitmaster,
                               create_receiver=self.create_receiver, config_path=self.path)

    def test_start_and_stop_by_config(self):
        manager = self.manager()
        manager.check()
        self.assertEqual(self.started, [])
        self.set(ToDo={'pit_on': 'True', 'pit2_on': 'True', 'maverick_enabled': 'True'})
        manager.check()
        self.assertEqual([p.instance for p in self.started], [0, 1])
        self.assertEqual(self.started[0].max_age, service.max_measurement_age(3.0))
        self.receivers[0].start.assert_called_once_with()
        manager.check()   # läuft schon
        self.assertEqual(len(self.started), 2)
        self.set(ToDo={'pit_on': 'False', 'pit2_on': 'True', 'maverick_enabled': 'False'})
        manager.check()
        self.started[0].stop.assert_called_once_with()
        self.started[1].stop.assert_not_called()
        self.receivers[0].stop.assert_called_once_with()
        manager.stop()
        self.started[1].stop.assert_called_once_with()

    def test_restart_flag(self):
        manager = self.manager()
        self.set(ToDo={'pit_on': 'True'})
        manager.check()
        self.set(ToDo={'restart_pitmaster': 'True'})
        manager.check()
        self.assertEqual(len(self.started), 2)
        self.started[0].stop.assert_called_once_with()
        config = make_parser()
        read_config_file(config, self.path)
        self.assertEqual(config.get('ToDo', 'restart_pitmaster'), 'False')
        manager.stop()

    def test_pitmaster_that_ended_itself_is_restarted(self):
        manager = self.manager()
        self.set(ToDo={'pit_on': 'True'})
        manager.check()
        manager.pitmasters[0][2].set()    # Thread endet
        manager.pitmasters[0][1].join(5)
        manager.check()
        self.assertEqual(len(self.started), 2)
        manager.stop()


class CoreTest(unittest.TestCase):
    def test_failure_of_a_service_stops_the_core(self):
        core = service.Core(startup=mock.Mock(), sensor_types={})
        core.run_comp = mock.Mock(side_effect=RuntimeError('ADC kaputt'))
        core.manager = mock.Mock()
        core.manager.check.side_effect = lambda: None
        with self.assertLogs('WLANthermo.core', 'CRITICAL'):
            failed = core.run()
        self.assertTrue(failed)
        self.assertEqual(core.failed, ['comp'])
        core.manager.stop.assert_called_once_with()

    def test_stop(self):
        core = service.Core(startup=mock.Mock(), sensor_types={})
        started = threading.Event()
        core.run_comp = lambda: (started.set(), core.stop_event.wait(10))
        core.manager = mock.Mock()
        threading.Timer(0.1, core.stop).start()
        self.assertFalse(core.run())
        self.assertTrue(started.is_set())

    def test_max_measurement_age(self):
        self.assertEqual(service.max_measurement_age(3), 15)
        self.assertEqual(service.max_measurement_age(10), 36)


if __name__ == '__main__':
    unittest.main()
