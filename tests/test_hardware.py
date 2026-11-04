"""Tests für wlanthermo.comp.hardware und wlanthermo.comp.channels mit einem simulierten pigpio.

Start: python3 -m unittest tests/test_hardware.py   (benötigt: pip install pigpio bitstring)
"""
import os
import struct
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import pigpio  # noqa: E402
from wlanthermo.comp import hardware  # noqa: E402
from wlanthermo.comp.channels import Channels  # noqa: E402
from wlanthermo.comp.hardware import Beeper, Board  # noqa: E402
from wlanthermo.comp.settings import ChannelSettings  # noqa: E402
from wlanthermo.sensors.adc import Mcp3208  # noqa: E402
from wlanthermo.sensors.catalog import SensorType  # noqa: E402
from wlanthermo.sensors.maverick import MaverickProbe  # noqa: E402
from wlanthermo.sensors.resistive import NtcProbe  # noqa: E402
from wlanthermo.sensors.thermocouple import Ad595Thermocouple, Max31855, Max31855Thermocouple  # noqa: E402


class FakePi:
    """Zeichnet alle Aufrufe auf; adc[kanal] liefert die Rohwerte des MCP3208."""

    def __init__(self, connected=True, in_use=()):
        self.connected = connected
        self.in_use = in_use
        self.calls = []
        self.adc = [0] * 8
        self.max31855 = {}

    def bb_spi_open(self, cs, *args):
        self.calls.append(('open', cs) + args)
        if cs in self.in_use:
            raise pigpio.error(pigpio.error_text(pigpio.PI_GPIO_IN_USE))

    def bb_spi_close(self, cs):
        self.calls.append(('close', cs))

    def bb_spi_xfer(self, cs, data):
        if cs == hardware.CS_MCP:
            channel = (struct.unpack('>H', data[:2])[0] >> 6) - 0x18
            self.calls.append(('adc', channel))
            return 3, b'\x00' + struct.pack('>H', self.adc[channel])
        return 2, self.max31855[cs]

    def set_mode(self, gpio, mode):
        self.calls.append(('mode', gpio, mode))

    def write(self, gpio, value):
        self.calls.append(('write', gpio, value))

    def stop(self):
        self.calls.append(('stop',))


class BeeperTest(unittest.TestCase):
    def test_pattern(self):
        pi = FakePi()
        with mock.patch('time.sleep') as sleep:
            Beeper(pi, 17).beep(3)
        self.assertEqual(pi.calls, [('write', 17, 1), ('write', 17, 0)] * 3)
        self.assertEqual(sleep.call_count, 5)  # an, aus, an, aus, an (ohne Pause am Ende)


class BoardTest(unittest.TestCase):
    def test_open_and_close(self):
        pi = FakePi(in_use=(8,))   # Bus noch von einem vorherigen Lauf offen
        with Board(lambda: pi) as board:
            self.assertIsInstance(board.adc, Mcp3208)
            self.assertEqual([chip.cs for chip in board.thermocouples], [8, 7])
        opened = [c[1] for c in pi.calls if c[0] == 'open']
        closed = [c[1] for c in pi.calls if c[0] == 'close']
        self.assertEqual(opened, [25, 8, 7])
        self.assertEqual(closed, [25, 8, 7])
        self.assertIn(('write', hardware.PWM, 0), pi.calls)
        self.assertEqual(pi.calls[-1], ('stop',))

    def test_closes_after_error(self):
        pi = FakePi()
        with self.assertRaises(KeyError):
            with Board(lambda: pi):
                raise KeyError()
        self.assertEqual(pi.calls[-1], ('stop',))

    def test_other_spi_error_is_raised(self):
        pi = FakePi()
        pi.bb_spi_open = mock.Mock(side_effect=pigpio.error('bad SPI baud rate'))
        with self.assertRaises(pigpio.error):
            with Board(lambda: pi):
                pass

    def test_pigpiod_not_running(self):
        with self.assertRaises(RuntimeError):
            with Board(lambda: FakePi(connected=False)):
                pass


FANTAST = SensorType('Fantast', NtcProbe, a=3.3558340e-03, b=2.5698192e-04, c=1.6391056e-06, rn=50.08)
KTYPE = SensorType('KTYPE', Ad595Thermocouple)


def startup(version='v3', maverick=False, max31855=False):
    return mock.Mock(version=version, maverick=maverick, max31855=max31855)


def settings(*sensor_types, resistor=47):
    return mock.Mock(channels=[ChannelSettings(name='', sensor_number='', sensor_type=t, temp_min=0,
                                               temp_max=100, resistor=resistor) for t in sensor_types])


class ChannelsTest(unittest.TestCase):
    def board(self, pi):
        return mock.Mock(adc=Mcp3208(pi, hardware.CS_MCP),
                         thermocouples=[Max31855(pi, cs) for cs in hardware.CS_MAX])

    def test_layout_v3(self):
        channels = Channels(startup(maverick=True), self.board(FakePi()))
        channels.configure(settings(*[FANTAST] * 7, None))
        sensors = channels.sensors
        self.assertEqual(len(sensors), 10)
        self.assertIsInstance(sensors[0], NtcProbe)
        self.assertIsNone(sensors[7])
        self.assertEqual([type(s) for s in sensors[8:]], [MaverickProbe, MaverickProbe])

    def test_layout_mini_v2(self):
        sensors = Channels(startup('miniV2', max31855=True), self.board(FakePi())).fixed
        self.assertEqual([s is None for s in sensors[:2]], [True, True])   # Maverick aus
        self.assertEqual([type(s) for s in sensors[2:]], [Max31855Thermocouple] * 2)
        sensors = Channels(startup('miniV2', max31855=False), self.board(FakePi())).fixed
        self.assertEqual(sensors, [None] * 4)

    def test_probes_only_rebuilt_on_new_settings(self):
        channels = Channels(startup(), self.board(FakePi()))
        current = settings(*[FANTAST] * 8)
        channels.configure(current)
        first = channels.adc_probes
        channels.configure(current)
        self.assertIs(channels.adc_probes, first)
        channels.configure(settings(*[KTYPE] * 8))
        self.assertIsInstance(channels.adc_probes[0], Ad595Thermocouple)

    def test_measure(self):
        pi = FakePi()
        pi.adc = [2048, 2048] + [0] * 6
        channels = Channels(startup(), self.board(pi))
        channels.configure(settings(FANTAST, KTYPE, *[FANTAST] * 6, resistor=50.08))
        temperatures = channels.measure(iterations=3)
        self.assertEqual([c[1] for c in pi.calls], list(range(8)) * 3)
        # Kanal 0 invertiert (Spannungsteiler, v3): 4095 - 2048 = 2047
        self.assertEqual(temperatures[0], FANTAST.create(channels.sampler.channels[0], 50.08).read())
        self.assertEqual(channels.sampler.channels[0].samples, [2047] * 3)
        self.assertAlmostEqual(temperatures[1], 165)   # AD595 nicht invertiert
        self.assertEqual(temperatures[2:], [None] * 8)  # ADC 0 = kein Fühler, Maverick aus


if __name__ == '__main__':
    unittest.main()
