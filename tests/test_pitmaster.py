"""Tests für wlanthermo.pitmaster mit einem simulierten pigpio.

Start: python3 -m unittest tests/test_pitmaster.py   (benötigt: pip install pigpio)
"""
import builtins
import configparser
import logging
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.pitmaster.actuators import (GPIOS, Actuator, Damper, Fan, FanPwm, Io, IoPwm,  # noqa: E402
                                            Output, Servo, ServoLimiter, create_actuator)
from wlanthermo.pitmaster.controller import (OpenLidDetector, PidController,  # noqa: E402
                                             StepCurveController, limit_rate)
from wlanthermo.pitmaster.settings import (ActuatorSettings, parse_curve,  # noqa: E402
                                           parse_pitmaster_settings, section_suffix)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'software', 'var', 'www', 'conf', 'WLANThermo.conf')
LOG = logging.getLogger('test.pitmaster')


class FakePi:
    def __init__(self):
        self.calls = []
        self.waves = 0

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name,) + args)
            if name == 'wave_create':
                self.waves += 1
                return self.waves
            return 0
        return call


def actuator_settings(**changes):
    values = dict(pwm_min=20, pwm_max=100, inverted=False, servo_min=1000, servo_max=2000, servo_inverted=False,
                  servo_deadband=5, startup_min=50, startup_threshold=0, startup_time=0.5,
                  damper_offset=0, damper_pitch=1)
    values.update(changes)
    return ActuatorSettings(**values)


def load_config():
    config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
    config.read(CONFIG_FILE, encoding='utf-8')
    return config


class GettextTest(unittest.TestCase):
    def setUp(self):
        builtins._ = lambda text: text

    def tearDown(self):
        del builtins._


class ActuatorTest(GettextTest):
    def setUp(self):
        super().setUp()
        self.pi = FakePi()

    def test_all_are_actuators(self):
        for cls in (Fan, FanPwm, Servo, IoPwm, Io, Damper):
            self.assertTrue(issubclass(cls, Actuator))

    def test_fan(self):
        fan = Fan(self.pi, 4, actuator_settings(), LOG)
        fan.start()
        fan.set(50)
        fan.set(0)
        fan.stop()
        self.assertEqual(self.pi.calls, [('set_mode', 4, 1), ('set_PWM_frequency', 4, 500),
                                         ('set_PWM_dutycycle', 4, 20 * 2.55), ('set_PWM_dutycycle', 4, 153),
                                         ('set_PWM_dutycycle', 4, 0), ('set_PWM_dutycycle', 4, 0)])

    def test_fan_inverted(self):
        fan = Fan(self.pi, 4, actuator_settings(inverted=True), LOG)
        fan.set(0)
        fan.set(100)
        self.assertEqual(self.pi.calls, [('set_PWM_dutycycle', 4, 255), ('set_PWM_dutycycle', 4, 51)])

    def test_fan_pwm_replaces_wave(self):
        fan = FanPwm(self.pi, 6, actuator_settings(pwm_min=0), LOG)
        fan.start()
        fan.set(50)
        self.assertEqual(fan.wave, 2)
        self.assertIn(('wave_delete', 1), self.pi.calls)
        pulses = [c for c in self.pi.calls if c[0] == 'wave_add_generic'][-1][1]
        width, pause = pulses[0].delay, pulses[1].delay
        self.assertEqual((width, pause), (24, 23))   # 50 % von 46 µs + 1
        fan.stop()
        self.assertEqual(self.pi.calls[-2:], [('wave_tx_stop',), ('write', 6, 0)])

    def test_servo_deadband(self):
        servo = Servo(self.pi, 6, actuator_settings(), LOG)
        servo.start()
        for value in (50, 52, 60, 100):
            servo.set(value)
        widths = [c[2] for c in self.pi.calls if c[0] == 'set_servo_pulsewidth']
        # Start, 50 %, 52 % liegt im Totband (5 % = 50 µs), 60 %, Anschlag
        self.assertEqual(widths, [1000, 1500, 1500, 1600, 2000])

    def test_io(self):
        io = Io(self.pi, 4, actuator_settings(inverted=True), LOG)
        io.start()
        io.set(60)
        io.set(40)
        self.assertEqual([c for c in self.pi.calls if c[0] == 'write'], [('write', 4, 1), ('write', 4, 0), ('write', 4, 1)])

    def test_io_pwm_cycle(self):
        io = IoPwm(self.pi, 4, actuator_settings(pwm_min=0), LOG)
        io.set(25)
        self.assertEqual((io.on, io.off), (0.5, 1.5))
        io.settings = actuator_settings(pwm_min=0, inverted=True)
        io.set(25)
        self.assertEqual((io.on, io.off), (1.5, 0.5))

    def test_io_pwm_thread(self):
        io = IoPwm(self.pi, 4, actuator_settings(pwm_min=0), LOG)
        with mock.patch('time.sleep', side_effect=lambda s: io.end.set()):
            io.start()
            io.thread.join(1)
            io.stop()
        self.assertFalse(io.thread.is_alive())
        self.assertEqual(self.pi.calls[-1], ('write', 4, 0))

    def test_damper(self):
        damper = Damper(self.pi, 4, 6, actuator_settings(damper_offset=10, damper_pitch=2), LOG)
        damper.set(50)
        # Klappe 50 % * 2 + 10 -> begrenzt auf 100 %, Lüfter 50 %
        self.assertEqual(self.pi.calls, [('set_servo_pulsewidth', 6, 2000), ('set_PWM_dutycycle', 4, 153)])

    def test_create_actuator(self):
        gpios = GPIOS['miniV2'][1]
        self.assertEqual(create_actuator('servo', gpios, self.pi, actuator_settings(), LOG).gpio, 12)
        self.assertEqual(create_actuator('io', gpios, self.pi, actuator_settings(), LOG).gpio, 5)
        damper = create_actuator('damper', gpios, self.pi, actuator_settings(), LOG)
        self.assertEqual((damper.gpio, damper.servo_gpio), (5, 12))
        with self.assertLogs(LOG, 'ERROR'):
            self.assertIsNone(create_actuator('damper', GPIOS['v3'][0], self.pi, actuator_settings(), LOG))
        with self.assertRaises(KeyError):
            create_actuator('fan', GPIOS['v1'][0], self.pi, actuator_settings(), LOG)


class ServoLimiterTest(GettextTest):
    def test_counts(self):
        limiter = ServoLimiter(LOG)
        s = actuator_settings(servo_deadband=10)
        self.assertEqual([limiter.limit(w, s) for w in (1500, 1550, 1560, 1601, 2000)], [1500, 1500, 1500, 1601, 2000])
        self.assertEqual((limiter.move_count, limiter.nomove_count), (3, 2))


class OutputTest(GettextTest):
    def test_startup_boost(self):
        output = Output(LOG)
        fan = mock.Mock(startup_boost=True, settings=actuator_settings(startup_min=50, startup_time=0.5))
        output.actuator = fan
        with mock.patch('time.sleep') as sleep:
            output.set(30)
        self.assertEqual(fan.set.call_args_list, [mock.call(50), mock.call(30)])
        sleep.assert_called_once_with(0.5)
        fan.set.reset_mock()
        output.set(20)   # läuft schon
        fan.set.assert_called_once_with(20)

    def test_limits_and_no_actuator(self):
        output = Output(LOG)
        output.set(150)
        self.assertEqual(output.value, 100.0)
        output.set(-5)
        self.assertEqual(output.value, 0.0)

    def test_change_stops_previous(self):
        output = Output(LOG)
        first, second = mock.Mock(), mock.Mock()
        output.change(first)
        output.change(second)
        first.stop.assert_called_once_with()
        second.start.assert_called_once_with()
        output.stop()
        second.stop.assert_called_once_with()
        self.assertIsNone(output.actuator)


def pit_settings(**changes):
    settings = parse_pitmaster_settings(load_config(), 0, LOG)
    for key, value in changes.items():
        setattr(settings, key, value)
    return settings


class ControllerTest(GettextTest):
    def test_step_curve(self):
        s = pit_settings(setpoint=110, curve=[(-15, 100), (-10, 75), (-5, 40), (-1, 0)])
        self.assertEqual(StepCurveController().compute(90, s)[0], 100.0)
        self.assertEqual(StepCurveController().compute(98, s)[0], 75.0)
        self.assertEqual(StepCurveController().compute(105, s)[0], 40.0)  # Abweichung -5
        self.assertEqual(StepCurveController().compute(108, s)[0], 0.0)   # Schritt -1!0
        self.assertEqual(StepCurveController().compute(110, s), (0, '|dif: 0|new overshoot: 0'))
        self.assertEqual(StepCurveController().compute(109.5, s)[0], 0)   # keine Regel passt
        self.assertTrue(StepCurveController().compute(109.5, s)[1].endswith('|no matching rule, stop pit!'))

    def test_pid_limits_and_anti_windup(self):
        s = pit_settings(setpoint=110, pause=3)
        s.pid.kp, s.pid.ki, s.pid.kd, s.pid.switch_a = 2, 0.1, 0, 0
        s.pid.iterm_min, s.pid.iterm_max = 0, 30
        pid = PidController()
        self.assertEqual(pid.compute(20, s)[0], 100)      # P = 180, begrenzt
        self.assertEqual(pid.dif_sum, 0)                   # an der Grenze kein I-Anteil
        output, msg = pid.compute(105, s)                  # P = 10, I = 0.1 * 15
        self.assertAlmostEqual(output, 11.5)
        self.assertIn('|PID values P 10', msg)
        for _ in range(100):
            pid.compute(109, s)
        self.assertAlmostEqual(pid.dif_sum * 0.1, 30)      # I-Anteil auf iterm_max begrenzt

    def test_pid_switch_parameters(self):
        s = pit_settings(setpoint=100, pause=1)
        s.pid.kp, s.pid.ki, s.pid.kd = 1, 0, 0
        s.pid.kp_a, s.pid.ki_a, s.pid.kd_a, s.pid.switch_a = 3, 0, 0, 90
        self.assertEqual(PidController().compute(80, s)[0], 60)   # unter 90 %: kp_a
        self.assertEqual(PidController().compute(95, s)[0], 5)    # darüber: kp

    def test_open_lid(self):
        s = pit_settings(pause=3)
        s.lid.enabled, s.lid.pause, s.lid.falling_border, s.lid.rising_border = True, 9, 95, 100
        lid = OpenLidDetector(LOG)
        for t in (100, 100, 100, 100, 100):
            self.assertEqual(lid.update(t, s), (False, ''))
        self.assertEqual(lid.update(80, s), (True, '|open lid detected'))
        self.assertTrue(lid.detected)
        self.assertEqual(lid.update(90, s), (False, ''))
        self.assertEqual(lid.update(101, s), (False, '|lid closed'))
        self.assertFalse(lid.detected)

    def test_open_lid_timeout(self):
        s = pit_settings(pause=3)
        s.lid.enabled, s.lid.pause, s.lid.falling_border, s.lid.rising_border = True, 6, 95, 100
        lid = OpenLidDetector(LOG)
        for t in (100, 100, 100, 100, 100, 80):
            lid.update(t, s)
        self.assertEqual(lid.update(81, s), (False, ''))
        self.assertEqual(lid.update(82, s), (False, '|timeout open lid detection'))

    def test_rate_limit(self):
        s = pit_settings(pause=3, ratelimit_rise=30, ratelimit_fall=0)
        self.assertEqual(limit_rate(100, 0, s, LOG), 10)    # 100 % in 30 s, 3 s Zyklus
        self.assertEqual(limit_rate(5, 0, s, LOG), 5)
        self.assertEqual(limit_rate(0, 100, s, LOG), 0)     # Absenken nicht begrenzt


class SettingsTest(GettextTest):
    def test_shipped_config(self):
        config = load_config()
        s = parse_pitmaster_settings(config, 0, LOG)
        self.assertEqual((s.pit_type, s.controller_type, s.setpoint), ('fan', 'False', 110))
        self.assertEqual(s.curve[0], (-15.0, 100.0))
        self.assertEqual(parse_pitmaster_settings(config, 1, LOG).actuator.servo_max, 1500)

    def test_curve_with_bad_step(self):
        with self.assertLogs(LOG, 'ERROR'):
            self.assertEqual(parse_curve('-5!40|x!1|-1!0', LOG), [(-5.0, 40.0), (-1.0, 0.0)])

    def test_suffix(self):
        self.assertEqual((section_suffix(0), section_suffix(1)), ('', '2'))


if __name__ == '__main__':
    unittest.main()
