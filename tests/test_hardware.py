"""Tests für wlanthermo.hardware und wlanthermo.channels mit einem simulierten pigpio.

Start: python3 -m unittest tests/test_hardware.py   (benötigt: pip install pigpio bitstring)
"""
import os
import struct
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import pigpio  # noqa: E402
from wlanthermo import hardware  # noqa: E402
from wlanthermo.channels import AdcInput, MaverickInput, ThermocoupleInput  # noqa: E402
from wlanthermo.hardware import Beeper, Board, Max31855, Mcp3208  # noqa: E402
from wlanthermo.sensors import KTypeSensor, NtcSensor  # noqa: E402
from wlanthermo.settings import ChannelSettings  # noqa: E402


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


class Mcp3208Test(unittest.TestCase):
    def test_read_channel(self):
        pi = FakePi()
        pi.adc[5] = 1234
        self.assertEqual(Mcp3208(pi, hardware.CS_MCP).read(5), 1234)
        self.assertEqual(pi.calls, [('adc', 5)])

    def test_invalid_channel(self):
        with self.assertRaises(ValueError):
            Mcp3208(FakePi(), hardware.CS_MCP).read(8)


class Max31855Test(unittest.TestCase):
    def test_temperature(self):
        pi = FakePi()
        pi.max31855[8] = struct.pack('>h', int(123.25 * 4) << 2)
        self.assertEqual(Max31855(pi, 8).read(), 123.25)
        pi.max31855[8] = struct.pack('>h', int(-10.5 * 4) << 2)
        self.assertEqual(Max31855(pi, 8).read(), -10.5)

    def test_fault_bit(self):
        pi = FakePi()
        pi.max31855[7] = b'\x00\x01'
        self.assertIsNone(Max31855(pi, 7).read())


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


def channel(sensor, resistor=47):
    return ChannelSettings(name='', sensor_type='', sensor=sensor, temp_min=0, temp_max=100, resistor=resistor)


NTC = NtcSensor('Fantast', 3.3558340e-03, 2.5698192e-04, 1.6391056e-06, 50.08)


class AdcInputTest(unittest.TestCase):
    def test_interleaved_sampling_and_inversion(self):
        pi = FakePi()
        pi.adc[0] = 1000
        pi.adc[1] = 1000
        adc = AdcInput(Mcp3208(pi, hardware.CS_MCP), version='v3')
        samples = adc.sample([channel(NTC), channel(KTypeSensor('KTYPE'))], iterations=2)
        self.assertEqual([c[1] for c in pi.calls], [0, 1, 0, 1])
        self.assertEqual(samples, [[3095, 3095], [1000, 1000]])

    def test_v1_not_inverted(self):
        pi = FakePi()
        pi.adc[0] = 1000
        adc = AdcInput(Mcp3208(pi, hardware.CS_MCP), version='v1')
        self.assertEqual(adc.sample([channel(NTC)], iterations=1), [[1000]])

    def test_temperature(self):
        # Spannungsteiler in der Mitte: Fühler = Messwiderstand = Rn -> 1/a - 273
        self.assertEqual(AdcInput.temperature(channel(NTC, resistor=50.08), 2048), round(1 / 3.3558340e-03 - 273, 2))
        self.assertAlmostEqual(AdcInput.temperature(channel(KTypeSensor('KTYPE')), 2048), 165)

    def test_out_of_range_or_unknown_sensor(self):
        for value in (0, 15, 4080, 4095):
            self.assertIsNone(AdcInput.temperature(channel(NTC), value))
        self.assertIsNone(AdcInput.temperature(channel(None), 2048))

    def test_noisy_channel_warns(self):
        pi = FakePi()
        values = iter([1000, 1100] * 5)
        pi.bb_spi_xfer = lambda cs, data: (3, b'\x00' + struct.pack('>H', next(values)))
        adc = AdcInput(Mcp3208(pi, hardware.CS_MCP), version='v3')
        with self.assertLogs('WLANthermo.channels', 'WARNING'):
            adc.read([channel(NTC)], iterations=10)


class MaverickInputTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(MaverickInput().read({'temperature_1': 80.5, 'temperature_2': ''}), [80.5, None])
        self.assertEqual(MaverickInput().read(None), [None, None])


class ThermocoupleInputTest(unittest.TestCase):
    def test_enabled_and_disabled(self):
        chips = [mock.Mock(**{'read.return_value': 250.0}), mock.Mock(**{'read.return_value': None})]
        self.assertEqual(ThermocoupleInput(chips, enabled=True).read(), [250.0, None])
        self.assertEqual(ThermocoupleInput(chips, enabled=False).read(), [None, None])
        chips[0].read.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
