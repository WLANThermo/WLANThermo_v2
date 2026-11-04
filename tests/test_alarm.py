"""Tests für wlanthermo.alarm (ohne Hardware).

Start: python3 -m unittest tests/test_sensors.py tests/test_alarm.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.alarm import (AlarmMonitor, AlarmState, ChannelStatus, Evaluation,  # noqa: E402
                              NotificationSchedule, safe_format)

MIN = [0, 0]
MAX = [100, 100]


class SafeFormatTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(safe_format('{name}: {temperatur}{temp_unit}', {'name': 'Garraum', 'temperatur': 110.5, 'temp_unit': '°C'}),
                         'Garraum: 110.5°C')

    def test_missing_key_is_marked(self):
        with self.assertLogs('WLANthermo.alarm', 'ERROR'):
            self.assertEqual(safe_format('{name} {foo}', {'name': 'A'}), 'A !!foo!!')

    def test_broken_template_is_returned_unchanged(self):
        with self.assertLogs('WLANthermo.alarm', 'ERROR'):
            self.assertEqual(safe_format('Temp {temperatur', {'temperatur': 1}), 'Temp {temperatur')
        with self.assertLogs('WLANthermo.alarm', 'ERROR'):
            self.assertEqual(safe_format('{0}', {}), '{0}')
        with self.assertLogs('WLANthermo.alarm', 'ERROR'):
            # None mit Formatangabe
            self.assertEqual(safe_format('{temperatur:.1f}', {'temperatur': None}), '{temperatur:.1f}')


class AlarmMonitorTest(unittest.TestCase):
    def setUp(self):
        self.monitor = AlarmMonitor(2)

    def evaluate(self, *temps):
        return self.monitor.evaluate(list(temps), MIN, MAX)

    def test_all_ok(self):
        e = self.evaluate(50, 60)
        self.assertEqual(e.statuses, [ChannelStatus.OK, ChannelStatus.OK])
        self.assertFalse(e.active)
        self.assertFalse(e.new)

    def test_no_value_is_error_and_keeps_state(self):
        self.evaluate(120, 50)
        e = self.evaluate(None, 50)
        self.assertEqual(e.statuses[0], ChannelStatus.ERROR)
        self.assertEqual(self.monitor.states[0], AlarmState.HI)
        self.assertFalse(e.active)

    def test_new_alarm_then_still_active(self):
        e = self.evaluate(100, 50)  # Grenzwert zählt als überschritten
        self.assertEqual(e.statuses[0], ChannelStatus.HI)
        self.assertTrue(e.active and e.new)
        e = self.evaluate(110, 50)
        self.assertTrue(e.active)
        self.assertFalse(e.new)

    def test_low_alarm(self):
        e = self.evaluate(50, 0)
        self.assertEqual(e.statuses[1], ChannelStatus.LO)
        self.assertTrue(e.new)

    def test_acknowledged_alarm_is_silent_but_reported(self):
        self.evaluate(120, -5)
        self.monitor.acknowledge()
        self.assertEqual(self.monitor.states, [AlarmState.HI_ACK, AlarmState.LO_ACK])
        e = self.evaluate(120, -5)
        self.assertEqual(e.statuses, [ChannelStatus.HI, ChannelStatus.LO])
        self.assertFalse(e.active)
        self.assertFalse(e.new)

    def test_back_in_range_rearms(self):
        self.evaluate(120, 50)
        self.monitor.acknowledge()
        self.evaluate(90, 50)
        self.assertEqual(self.monitor.states[0], AlarmState.OK)
        self.assertTrue(self.evaluate(120, 50).new)

    def test_jump_from_high_to_low_is_new_alarm(self):
        self.evaluate(120, 50)
        self.monitor.acknowledge()
        e = self.evaluate(-10, 50)
        self.assertEqual(self.monitor.states[0], AlarmState.LO)
        self.assertTrue(e.new)


class NotificationScheduleTest(unittest.TestCase):
    QUIET = Evaluation([], active=False, new=False)
    ACTIVE = Evaluation([], active=True, new=False)
    NEW = Evaluation([], active=True, new=True)

    def setUp(self):
        self.schedule = NotificationSchedule()

    def test_nothing_without_intervals(self):
        self.assertEqual(self.schedule.check(self.ACTIVE, False, 0, 0, 1000), (False, False, False))

    def test_new_alarm_and_test_send_immediately(self):
        self.assertTrue(self.schedule.check(self.NEW, False, 0, 0, 1000)[2])
        self.assertTrue(self.schedule.check(self.QUIET, True, 0, 0, 1001)[2])

    def test_repeat_while_active(self):
        self.schedule.check(self.NEW, False, 60, 0, 1000)
        self.assertEqual(self.schedule.check(self.ACTIVE, False, 60, 0, 1030), (False, False, False))
        self.assertEqual(self.schedule.check(self.ACTIVE, False, 60, 0, 1061), (True, False, True))
        self.assertEqual(self.schedule.check(self.ACTIVE, False, 60, 0, 1100), (False, False, False))

    def test_no_repeat_when_quiet(self):
        self.schedule.check(self.NEW, False, 60, 0, 1000)
        self.assertEqual(self.schedule.check(self.QUIET, False, 60, 0, 2000), (False, False, False))

    def test_status_interval(self):
        self.assertEqual(self.schedule.check(self.QUIET, False, 0, 600, 1000), (False, True, True))
        self.assertEqual(self.schedule.check(self.QUIET, False, 0, 600, 1500), (False, False, False))
        self.assertEqual(self.schedule.check(self.QUIET, False, 0, 600, 1601), (False, True, True))

    def test_repeat_takes_precedence_over_status(self):
        self.schedule.check(self.NEW, False, 60, 60, 1000)
        self.assertEqual(self.schedule.check(self.ACTIVE, False, 60, 60, 1061), (True, False, True))

    def test_any_message_restarts_intervals(self):
        self.schedule.check(self.QUIET, False, 0, 600, 1000)
        self.schedule.check(self.QUIET, True, 0, 600, 1500)   # Testalarm
        self.assertEqual(self.schedule.check(self.QUIET, False, 0, 600, 1601), (False, False, False))


if __name__ == '__main__':
    unittest.main()
