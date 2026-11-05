"""Tests für den Maverick-Empfänger (wlanthermo.sensors.maverick.receiver) mit erzeugten Funktelegrammen.

Start: python3 -m unittest tests/test_maverick.py   (benötigt: pip install pigpio)
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.sensors.maverick import receiver  # noqa: E402

QUART = {0: [0, 1, 0, 1], 1: [0, 1, 1, 0], 2: [1, 0, 0, 1], 3: [1, 0, 1, 0]}
LONG, SHORT = 500, 240
TRAIN_LONG = receiver.Decoder.LONG_HIGH + receiver.Decoder.LONG_LOW


def base4(value, digits=5):
    return [(value >> (2 * i)) & 3 for i in reversed(range(digits))]


def telegram(temp1, temp2, init=True, sender=0x1234):
    """Flanken (Pegel, Dauer) einer Übertragung; temp2=None: kein Fühler.

    Die übertragene Prüfsumme ist so gewählt, dass die Sender-ID (Prüfsumme der
    Daten XOR übertragener Wert) konstant sender ist, wie bei einem echten Sender.
    """
    edges = [(1, 4500)] + [(0, 200), (1, 4500)] * 7 + [(0, 500)]
    # Pegel wechseln mit jeder Flanke, die letzte Präambelflanke hatte Pegel 0
    edges += [((n + 1) % 2, LONG if n in TRAIN_LONG else SHORT) for n in range(2, 19)]
    quarts = [0] * 22                   # Quart 4..25 des Pakets
    quarts[2], quarts[3] = (1, 3) if init else (0, 2)    # Status 7 (init) bzw. 2
    quarts[4:9] = base4(temp1 + 532)
    quarts[9:14] = base4(temp2 + 532 if temp2 is not None else 0)
    bits = receiver.PREAMBLE + [b for q in quarts for b in QUART[q]]
    quarts[14:22] = base4((receiver.calc_chksum(bits) & 0xffff) ^ sender, 8)
    level, bit = edges[-1][0], 1
    for want in [b for q in quarts for b in QUART[q]]:
        while True:
            level ^= 1
            if level == want:
                edges.append((level, SHORT if bit == want else LONG))
                bit = want
                break
            edges.append((level, SHORT))
    return edges


def feed(decoder, edges, tick=0):
    for level, duration in edges:
        tick += duration
        decoder.edge(22, level, tick)
    return tick


class DecoderTest(unittest.TestCase):
    def decode(self, edges):
        packets = []
        with contextlib.redirect_stdout(io.StringIO()):
            feed(receiver.Decoder(lambda t, bits: packets.append(bits)), edges)
        return packets

    def test_temperatures(self):
        packets = self.decode(telegram(25, 180))
        self.assertEqual(len(packets), 1)
        self.assertEqual(len(packets[0]), receiver.PACKET_BITS)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(receiver.get_data(packets[0]), [25, 180])
            self.assertEqual(receiver.get_data(packets[0], fahrenheit=True), [77, 356])
            self.assertEqual(receiver.get_state(packets[0]), 'init')

    def test_missing_probe(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(receiver.get_data(self.decode(telegram(60, None))[0]), [60, ''])

    def test_noise_and_repeated_telegrams(self):
        edges = [(1, 30), (0, 7000), (1, 900)] + telegram(20, 30) + [(0, 60), (1, 3000)] + telegram(21, 31)
        self.assertEqual(len(self.decode(edges)), 2)

    def test_broken_pulse_drops_telegram(self):
        edges = telegram(20, 30)
        edges[60] = (edges[60][0], 2000)
        self.assertEqual(self.decode(edges), [])


class ReceiverTest(unittest.TestCase):
    def packet(self, temp1, temp2, init=True):
        packets = []
        with contextlib.redirect_stdout(io.StringIO()):
            feed(receiver.Decoder(lambda t, bits: packets.append(bits)), telegram(temp1, temp2, init))
        return packets[0]

    def test_sync_and_rate_limit(self):
        r = receiver.MaverickReceiver(pi=None, on_reading=None)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(r.process(100, self.packet(20, 30, init=False)))   # unbekannt, nicht im Sync
            first = r.process(101, self.packet(20, 30))
            self.assertIsNone(r.process(103, self.packet(21, 30, init=False)))  # innerhalb 5 s
            later = r.process(107, self.packet(22, 30, init=False))
        self.assertEqual((first.temperature_1, first.temperature_2, first.unit), (20, 30, '°C'))
        self.assertEqual((later.temperature_1, later.checksum), (22, 0x1234))
        self.assertEqual(first.as_dict()['time'], 101)

    def test_nosync_accepts_new_sender(self):
        r = receiver.MaverickReceiver(pi=None, on_reading=None, nosync=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNotNone(r.process(100, self.packet(20, 30, init=False)))

    def test_start_stop_with_pigpio(self):
        pi = mock.Mock(**{'get_current_tick.return_value': 0})
        readings = []
        r = receiver.MaverickReceiver(pi, readings.append, pin=22)
        r.start()
        edge = pi.callback.call_args[0][2]
        with mock.patch('time.time', return_value=500.0), contextlib.redirect_stdout(io.StringIO()):
            feed(mock.Mock(edge=edge), [])
            tick = 0
            for level, duration in telegram(42, 43):
                tick += duration
                edge(22, level, tick)
            r.stop()   # verarbeitet die Warteschlange bis zum Ende
        pi.set_noise_filter.assert_called_once_with(22, 4500, 400000)
        pi.callback.return_value.cancel.assert_called_once_with()
        self.assertEqual([(x.time, x.temperature_1, x.temperature_2) for x in readings], [(500.0, 42, 43)])


class JsonWriterTest(unittest.TestCase):
    def test_noappend_is_readable_by_comp(self):
        import argparse
        import tempfile
        from wlanthermo.sensors.maverick import MaverickFile, MaverickProbe
        path = os.path.join(tempfile.mkdtemp(), 'maverick.json')
        writer = receiver.JsonWriter(argparse.Namespace(json=path, noappend=True))
        reading = receiver.Reading(time=1000.0, checksum=0x1234, type='et732', temperature_1=80, temperature_2='')
        writer.write(reading)
        source = MaverickFile(path)
        with mock.patch('time.time', return_value=1005.0):
            source.update()
        self.assertEqual([MaverickProbe(source, n).read() for n in (1, 2)], [80, None])
        self.assertEqual(source.values['checksum'], 0x1234)


if __name__ == '__main__':
    unittest.main()
