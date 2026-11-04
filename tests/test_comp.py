"""Tests für wlanthermo.comp.service (ohne Hardware).

Start: python3 -m unittest tests/test_comp.py   (benötigt: pip install pigpio bitstring psutil)
"""
import builtins
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.comp import service as comp  # noqa: E402
from wlanthermo.comp.alarm import ChannelStatus, Evaluation  # noqa: E402
from wlanthermo.comp.datafiles import PitValues  # noqa: E402
from wlanthermo.core.hub import MEASUREMENT, DataHub  # noqa: E402
from wlanthermo.comp.settings import AlertSettings, ChannelSettings, Settings, StartupSettings  # noqa: E402


def settings(**changes):
    values = dict(
        channels=[ChannelSettings(name='Garraum', sensor_number='1', sensor_type=None, temp_min=10, temp_max=60, resistor=47),
                  ChannelSettings(name='Kern', sensor_number='1', sensor_type=None, temp_min=10, temp_max=60, resistor=47)],
        pit_on=[True, False], beeper=True, iterations=1, delay=3.0, temp_unit='celsius',
        alert=AlertSettings(high_template='{name} zu heiß: {temperatur}{temp_unit}{lf}',
                            low_template='{name} zu kalt{lf}',
                            status_template='{name}: {temperatur} {temp_unit_long}{lf}',
                            message_template='{hostname}{lf}{alarme}{statusse}Pit {pit_new}/{pit_set} Pit2 {pit2_new}',
                            status_interval=0, alarm_interval=0),
        email=None, telegram=None, push=None)
    values.update(changes)
    return Settings(**values)


class GettextTest(unittest.TestCase):
    def setUp(self):
        builtins._ = lambda text: text

    def tearDown(self):
        del builtins._


class BuildMessageTest(GettextTest):
    def test_message(self):
        evaluation = Evaluation([ChannelStatus.HI, ChannelStatus.OK], active=True, new=True)
        message = comp.build_message(settings(), [74.21000000000001, 30], evaluation,
                                     [PitValues('55', '110'), None], 'grill')
        self.assertEqual(message, 'grill\nGarraum zu heiß: 74.21°C\nKern: 30 degrees Celsius\nPit 55/110 Pit2 -')

    def test_no_value_is_not_reported(self):
        evaluation = Evaluation([ChannelStatus.ERROR, ChannelStatus.LO], active=True, new=False)
        message = comp.build_message(settings(), [None, 5], evaluation, [None, None], 'grill')
        self.assertEqual(message, 'grill\nKern zu kalt\nPit -/- Pit2 -')

    def test_fahrenheit(self):
        evaluation = Evaluation([ChannelStatus.OK, ChannelStatus.ERROR], active=False, new=False)
        message = comp.build_message(settings(temp_unit='fahrenheit'), [100.0, None], evaluation, [None, None], 'g')
        self.assertIn('Garraum: 100.0 degrees Fahrenheit', message)

    def test_to_fahrenheit(self):
        self.assertEqual(comp.to_fahrenheit(100), 212)
        self.assertIsNone(comp.to_fahrenheit(None))


class PidfileTest(GettextTest):
    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp()
        self.pidfile = os.path.join(self.dir, 'comp.pid')
        patcher = mock.patch.object(comp, 'PIDFILE', self.pidfile)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.dir)
        super().tearDown()

    def write(self, text):
        with open(self.pidfile, 'w') as f:
            f.write(text)

    def read(self):
        with open(self.pidfile) as f:
            return f.read()

    def test_new(self):
        comp.claim_pidfile()
        self.assertEqual(self.read(), str(os.getpid()))

    def test_stale_or_invalid(self):
        self.write('999999999')
        with mock.patch.object(comp, 'process_running', return_value=False):
            comp.claim_pidfile()
        self.assertEqual(self.read(), str(os.getpid()))
        for text in ('kaputt', ''):
            self.write(text)
            with self.assertLogs('WLANthermo', 'WARNING'):
                comp.claim_pidfile()
            self.assertEqual(self.read(), str(os.getpid()))

    def test_already_running(self):
        self.write('1234')
        with mock.patch.object(comp, 'process_running', return_value=True), \
                mock.patch('builtins.print'), self.assertRaises(SystemExit):
            comp.claim_pidfile()
        self.assertEqual(self.read(), '1234')


class CycleTest(GettextTest):
    """Ein Messzyklus mit Attrappen für Hardware und Dateien."""

    def setUp(self):
        super().setUp()
        startup = StartupSettings(version='v3', max31855=False, maverick=False, current_temp_file='/x',
                                  pit_files=['/p1', '/p2'], log_channels=[True] * 10, beeper_on_start=False,
                                  new_log_on_restart=False, separator=',', log_file='/l', log_level='ERROR')
        self.board = mock.Mock()
        self.board.adc.channels = 8
        self.comp = comp.Comp(startup, sensor_types={}, board=self.board)
        self.comp.current_temp_file = mock.Mock()
        self.comp.temperature_log = mock.Mock(**{'line.return_value': 'line'})
        self.comp.temperature_log.name = 'log'   # Mock(name=...) setzt den Namen des Mocks
        self.comp.config = mock.Mock(**{'current.return_value': settings(
            channels=settings().channels * 5, email=object())})
        self.comp.channels = mock.Mock(**{'measure.return_value': [70.0] + [30.0] * 7 + [None, None]})
        self.comp.pit_readers = [mock.Mock(**{'read.return_value': PitValues('55', '110')}), mock.Mock()]
        self.notifier = mock.Mock()
        for name, value in (('psutil.cpu_percent', [1.0]), ('psutil.virtual_memory', mock.Mock(free=0)),
                            ('time.sleep', None), ('os.path.isfile', False)):
            patcher = mock.patch(name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Nachrichten sofort statt im eigenen Thread versenden
        self.comp.notifications = mock.Mock(**{'submit.side_effect': lambda notifiers, message, urgent: [
            n.send(message, urgent=urgent) for n in notifiers]})
        patcher = mock.patch.object(comp, 'build_notifiers', return_value=[self.notifier])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_alarm_cycle(self):
        self.comp.cycle()
        temperatures = [70.0] + [30.0] * 7 + [None, None]
        _, temps, statuses, version, log_name = self.comp.current_temp_file.write.call_args[0]
        self.assertEqual(temps, ['70.00'] + ['30.00'] * 7 + ['', ''])
        self.assertEqual(statuses, [ChannelStatus.HI] + [ChannelStatus.OK] * 7 + [ChannelStatus.ERROR] * 2)
        self.assertEqual(log_name, 'log')
        self.comp.temperature_log.line.assert_called_once_with(mock.ANY, temperatures,
                                                               [PitValues('55', '110'), None])
        self.comp.pit_readers[1].read.assert_not_called()   # pit2 aus
        self.board.beeper.beep.assert_called_once_with(3)
        message = self.notifier.send.call_args[0][0]
        self.assertIn('Garraum zu heiß: 70.0°C', message)
        self.assertEqual(self.notifier.send.call_args[1], {'urgent': True})

    def test_second_cycle_does_not_resend(self):
        self.comp.cycle()
        self.comp.cycle()
        self.assertEqual(self.notifier.send.call_count, 1)
        self.assertEqual(self.board.beeper.beep.call_count, 2)  # Summer, solange nicht quittiert

    def test_publishes_measurement(self):
        hub = DataHub()
        self.comp.hub = hub
        with mock.patch('time.time', return_value=1000.0):
            self.comp.cycle()
        measurement = hub.latest(MEASUREMENT)
        self.assertEqual(measurement.time, 1000.0)
        self.assertEqual(measurement.temperatures, (70.0,) + (30.0,) * 7 + (None, None))
        self.assertEqual(measurement.statuses, ('hi',) + ('ok',) * 7 + ('er', 'er'))
        self.assertEqual(measurement.unit, 'celsius')

    def test_test_alarm(self):
        self.comp.channels.measure.return_value = [30.0] * 8 + [None, None]
        self.comp.test_alarm = True
        self.comp.cycle()
        self.assertTrue(self.notifier.send.call_args[0][0].startswith('test message\n'))
        self.assertEqual(self.notifier.send.call_args[1], {'urgent': False})
        self.assertFalse(self.comp.test_alarm)
        self.board.beeper.beep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
