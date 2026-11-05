#!/usr/bin/env python3
# coding=utf-8

# wlanthermo-maverick (bisher maverick.py)
# Receives Wireless BBQ Thermometer Telegrams via RF-Receiver
#
# (c) Martin Raatz, 2016
# Changed from fix offset to calculating the min and max length of the pulses based on Header AA99
# the pulswidth changes with every transmission on my ET733
# Checksum is same on ET732 and 733
#
# (c) Björn Schrader, 2015
# Code based on
# https://github.com/martinr63/OregonPi
# https://forums.adafruit.com/viewtopic.php?f=8&t=25414
# http://www.grillsportverein.de/forum/threads/wlan-maverick-bbq-thermometer-raspberry-pi-edition.232283/
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without
# limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import argparse
import json
import math
import os
import queue
import random
import string
import threading
import time
from dataclasses import dataclass

import pigpio

# Paket: 104 Bit, je 4 Bit ("Quart") stehen für 2 Datenbits
PACKET_BITS = 104
# Byte der Präambel, wird zum Einlernen der Pulsdauern benutzt
PREAMBLE = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 1]


def quart(raw):
    # 4 zu 2 Umwandlung
    if raw == [0, 1, 0, 1]:
        return 0
    elif raw == [0, 1, 1, 0]:
        return 1
    elif raw == [1, 0, 0, 1]:
        return 2
    elif raw == [1, 0, 1, 0]:
        return 3
    else:
        print('Error in Quart conversion', raw)
        return -1


def get_state(bitlist, debug=False):
    # Wertet das Statusbyte aus
    state = quart(bitlist[6 * 4:6 * 4 + 4]) << 2
    state |= quart(bitlist[7 * 4:7 * 4 + 4])
    if debug:
        print('state ', state)
    if state == 7:
        return 'init'
    elif state == 2:
        return 'default'
    else:
        print('Unknown state:', state)
        return 'unknown ' + str(state)


def bitlist_to_int(bitlist):
    out = 0
    for bit in bitlist:
        out = (out << 1) | bit
    return out


def bitlist_to_hexlist(bitlist):
    # Gibt eine Bitliste als Hex aus, nützlich zum Debuggen
    return [hex(bitlist_to_int(bitlist[i * 8:i * 8 + 8])) for i in range(int(len(bitlist) / 8))]


def calc_chksum(bitlist):
    # Berechnet die Checksumme anhand der Daten
    chksum_data = 0
    for i in range(12):
        chksum_data |= quart(bitlist[(6 + i) * 4:(6 + i) * 4 + 4]) << 22 - 2 * i

    mask = 0x3331
    chksum = 0x0
    for i in range(24):
        if (chksum_data >> i) & 0x01:
            chksum ^= mask
        msb = (mask >> 15) & 0x01
        mask = (mask << 1) & 0xFFFF
        if msb == 1:
            mask ^= 0x1021
    return chksum


def chksum(bitlist):
    """(Typ, ID): prüft die errechnete Checksumme gegen die übertragene.

    Das Ergebnis ist gleichzeitig die zufällige ID des Senders.
    """
    chksum_data = calc_chksum(bitlist)

    chksum = 0
    for i in range(6):
        chksum |= quart(bitlist[(18 + i) * 4:((18 + i) * 4) + 4]) << 14 - i * 2
    # ET-733 wird wie ET-732 ausgewertet
    type = 'et732'
    chksum |= 0xFFFF & quart(bitlist[24 * 4:(24 * 4) + 4]) << 2
    chksum |= 0xFFFF & quart(bitlist[25 * 4:(25 * 4) + 4])

    chksum = (chksum_data & 0xffff) ^ chksum
    return type, chksum


def get_data(bitlist, fahrenheit=False):
    """[Fühler 1, Fühler 2]: Temperatur oder '' ohne Fühler."""
    sensor1 = 0
    sensor2 = 0
    for i in range(5):
        startbit = (4 - i) * 4
        sensor1 += quart(bitlist[startbit + 32:startbit + 32 + 4]) * (1 << (2 * i))
        sensor2 += quart(bitlist[startbit + 52:startbit + 52 + 4]) * (1 << (2 * i))

    values = []
    for sensor in (sensor1, sensor2):
        if sensor == 0:
            values.append('')
        else:
            sensor -= 532
            if fahrenheit:
                sensor = (((sensor * 9) / 5) + 32)
            values.append(sensor)
    return values


class PulseWidths:
    """Mittelwert und Grenzen einer Pulsart, eingelernt aus der Präambel."""

    def __init__(self):
        self.sum = 0
        self.min = None
        self.max = None

    def add(self, duration):
        self.sum += duration
        if self.min is None or self.min > duration:
            self.min = duration
        if self.max is None or self.max < duration:
            self.max = duration

    def finish(self, count, min_factor, max_factor):
        average = self.sum / count
        if self.min > average * min_factor:
            self.min = average * min_factor
        if self.max < average * max_factor:
            self.max = average * max_factor
        self.max = math.floor(self.max)
        self.min = math.ceil(self.min)
        self.sum = average

    def __contains__(self, duration):
        return self.min <= duration <= self.max


class Decoder:
    """Dekodiert die Flanken des Funkempfängers zu Paketen.

    edge() wird für jede Flanke aufgerufen (pigpio-Callback); vollständige
    Pakete gehen als (Zeit, Bitliste) an on_packet.

    Ablauf: lange Pausen (Präambel), dann 18 Pulse zum Einlernen der Pulsdauern
    (train), dann die Daten: langer Puls = Pegelwechsel, kurzer = Wiederholung.
    """

    # Position der Pulse im Einlernteil
    # L l   L h   L l   L h   L l   L h   L l   L h   L l   S h   S l   L h   S l   S h   L l   S h   S l   L h
    # 1     2     3     4     5     6     7     8     9     10    11    12    13    14    15    16    17    18
    LONG_HIGH = (2, 4, 6, 8, 12, 18)
    LONG_LOW = (3, 5, 7, 9, 15)
    SHORT_HIGH = (10, 14, 16)
    SHORT_LOW = (11, 13, 17)

    def __init__(self, on_packet, debug=False):
        self.on_packet = on_packet
        self.debug = debug
        self.oldtick = 0
        self.oldlevel = None
        self.state = 'wait'
        self.packet = []
        self.bit = 0
        self.preamblecount = 0
        self.traincount = 0
        self._reset_widths()

    def _reset_widths(self):
        self.long_high = PulseWidths()
        self.long_low = PulseWidths()
        self.short_high = PulseWidths()
        self.short_low = PulseWidths()

    def _wait(self):
        self.state = 'wait'
        self.preamblecount = 0

    def edge(self, gpio, level, tick):
        debug = self.debug
        if self.oldlevel is None:
            self.oldlevel = level
        elif self.oldlevel == level:
            print('\nLost_Tick!')
        self.oldlevel = level
        duration = tick - self.oldtick
        self.oldtick = tick

        if duration < 70:
            return
        if debug and self.preamblecount > 0:
            print(duration, ":", level, " ", sep="", end="", flush=False)

        if self.state == 'wait' and level == 1:
            # lange Ruhe = vermutlich Präambel
            if 4000 < duration < 5500:
                self.state = 'preamble'
                self.preamblecount = 1
                if debug:
                    print('\npreamble', flush=True)
        elif self.state == 'preamble':
            self._preamble(duration)
        elif self.state == 'train':
            self._train(duration)
        elif self.state == 'data':
            self._data(level, duration)

        if len(self.packet) == PACKET_BITS:
            # komplettes Paket empfangen
            if debug:
                print('wait - ready', flush=True)
            self._wait()
            self.on_packet(time.time(), list(self.packet))
            self.packet[:] = []

    def _preamble(self, duration):
        debug = self.debug
        if 380 < duration < 650:
            if self.preamblecount > 6:
                self.state = 'train'
                self.traincount = 1
                if debug:
                    print('train', flush=True)
                self.bit = 1
                self.packet[:] = list(PREAMBLE)
                self._reset_widths()
                # Der erste Impuls der Präambel ist long low
                self.long_low.sum = duration
                self.long_low.min = duration
                self.long_low.max = duration
            else:
                self._wait()
                if debug:
                    print('not enough long pulses', flush=True)
        elif 100 < duration < 350:
            self.state = 'preamble'
        elif 4000 < duration < 5500:
            self.preamblecount += 1
            if debug:
                print('preamble', self.preamblecount, flush=True)
        else:
            self.state = 'wait'
            if debug:
                print('wait', flush=True)
            self.preamblecount = 0

    def _train(self, duration):
        self.traincount += 1
        if self.debug:
            print('train', self.traincount, flush=True)
        # Die erste Flanke wurde schon gezählt
        if self.traincount in self.LONG_HIGH:
            self.long_high.add(duration)
        elif self.traincount in self.LONG_LOW:
            self.long_low.add(duration)
        elif self.traincount in self.SHORT_HIGH:
            self.short_high.add(duration)
        elif self.traincount in self.SHORT_LOW:
            self.short_low.add(duration)

        if self.traincount == 18:
            self.long_high.finish(6, 0.75, 1.4)
            self.long_low.finish(6, 0.75, 1.4)
            self.short_high.finish(3, 0.2, 1.25)
            self.short_low.finish(3, 0.2, 1.25)
            self.state = 'data'
            if self.debug:
                for name in ('long_high', 'short_high', 'long_low', 'short_low'):
                    w = getattr(self, name)
                    print(name, round(w.sum), "min", w.min, "max", w.max, flush=False)
                print('data', flush=True)

    def _data(self, level, duration):
        debug = self.debug
        if level == 0:
            # level == 0 heisst, es wurde ein HIGH-Impuls ausgewertet
            if duration in self.short_low:
                # kurzer LOW = 0 wiederholt
                if debug:
                    print("SL    ", end="", flush=False)
                if self.bit == 0:
                    self.packet.append(0)
            elif duration in self.long_low:
                # langes LOW = 0
                if debug:
                    print("LL    ", end="", flush=False)
                self.packet.append(0)
                self.bit = 0
            else:
                # ungueltige Zeit
                self._wait()
                if debug:
                    print('wait ungueltig 0 bei ', len(self.packet), flush=True)
        else:
            if duration in self.short_high:
                # kurzer HIGH = 1 wiederholt
                if debug:
                    print("SH    ", end="", flush=False)
                if self.bit == 1:
                    self.packet.append(1)
            elif duration in self.long_high:
                # langes HIGH = 1
                if debug:
                    print("LH    ", end="", flush=False)
                self.packet.append(1)
                self.bit = 1
            else:
                # ungueltige Zeit
                self._wait()
                if debug:
                    print('wait ungueltig 1 bei ', len(self.packet), flush=True)


@dataclass(frozen=True)
class Reading:
    """Ein empfangenes Telegramm."""
    time: float
    checksum: int        # zufällige ID des Senders
    type: str
    temperature_1: object   # Zahl oder '' ohne Fühler
    temperature_2: object
    unit: str = '°C'

    def as_dict(self):
        """Wie in maverick.json."""
        return {'time': self.time, 'checksum': self.checksum, 'type': self.type, 'unit': self.unit,
                'temperature_1': self.temperature_1, 'temperature_2': self.temperature_2}

    def age(self, now=None):
        return (time.time() if now is None else now) - self.time


class MaverickReceiver:
    """Empfängt die Telegramme am Funkempfänger und meldet neue Werte an on_reading.

    Die Flanken wertet pigpio aus (Zeitstempel kommen von pigpiod, daher ist
    die Verzögerung in Python unkritisch); die Pakete werden in einem eigenen
    Thread geprüft. Ein Sender wird nur angenommen, wenn er im Sync-Status ist
    (Taste am Sender) oder nosync gesetzt ist, und höchstens alle 5 s gemeldet.
    """

    def __init__(self, pi, on_reading, pin=22, nosync=False, fahrenheit=False, debug=False, verbose=False):
        self.pi = pi
        self.on_reading = on_reading
        self.pin = pin
        self.nosync = nosync
        self.fahrenheit = fahrenheit
        self.debug = debug
        self.verbose = verbose
        self.unit_list = {}   # ID -> Zeit der letzten Meldung
        self.packets = queue.Queue()
        self.decoder = Decoder(lambda t, bits: self.packets.put((t, bits)), debug)
        self.callback = None
        self.worker = None

    def start(self):
        self.decoder.oldtick = self.pi.get_current_tick()
        self.pi.set_mode(self.pin, pigpio.INPUT)
        self.pi.set_noise_filter(self.pin, 4500, 400000)
        self.callback = self.pi.callback(self.pin, pigpio.EITHER_EDGE, self.decoder.edge)
        self.worker = threading.Thread(target=self._run, name='maverick', daemon=True)
        self.worker.start()

    def stop(self):
        if self.callback is not None:
            self.callback.cancel()
            self.callback = None
        if self.worker is not None:
            self.packets.put(None)
            self.worker.join(5)
            self.worker = None

    def updated(self, id, state, timestamp):
        """Ob das Paket gemeldet werden soll (nicht schon innerhalb der letzten 5 s vom gleichen Sender)."""
        if id in self.unit_list:
            if (self.unit_list[id] + 5) < timestamp:
                self.unit_list[id] = timestamp
                if self.debug:
                    print('units:', self.unit_list)
                return True
            return False
        if state == 'init' or self.nosync:
            # trägt neue Sender nur ein, wenn diese im Sync-Status sind, oder --nosync aktiv ist
            self.unit_list[id] = timestamp
            if self.debug:
                print('units:', self.unit_list)
            return True
        return False

    def process(self, item_time, item):
        type, chksum_is = chksum(item)
        temp1, temp2 = get_data(item, self.fahrenheit)
        state = get_state(item, self.debug)
        if not self.updated(chksum_is, state, item_time):
            return None
        reading = Reading(item_time, chksum_is, type, temp1, temp2, '°F' if self.fahrenheit else '°C')
        if self.verbose:
            print(time.strftime('%c:', time.localtime(item_time)), '-', chksum_is, '- Temperatur 1:', temp1,
                  reading.unit, 'Temperatur 2:', temp2, reading.unit)
        if self.debug:
            print('raw:', item)
            print('hex', bitlist_to_hexlist(item))
        return reading

    def _run(self):
        if self.verbose:
            print('Main task running')
        while True:
            entry = self.packets.get()
            if entry is None:
                return
            reading = self.process(*entry)
            if reading is not None:
                self.on_reading(reading)


# ---------------------------------------------------------------- Kommandozeile: Ausgaben

def get_random_filename(filename):
    return filename + '_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))


class QueueWriter:
    """Schreibt Werte in einem eigenen Thread, damit der Empfang nicht wartet."""

    def __init__(self, options):
        self.options = options
        self.queue = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def put(self, reading):
        self.queue.put(reading)

    def _loop(self):
        self.run()

    def run(self):
        while True:
            self.write(self.queue.get())
            self.queue.task_done()


class JsonWriter(QueueWriter):
    # schreibt ein JSON-Logfile
    def write(self, reading):
        options = self.options
        if options.noappend:
            tmp_filename = get_random_filename(options.json)
            with open(tmp_filename, 'w') as json_file:
                json_file.write(json.dumps(reading.as_dict()))
                json_file.flush()
                os.fsync(json_file.fileno())
            os.rename(tmp_filename, options.json)
        else:
            with open(options.json, 'a') as json_file:
                json_file.write(json.dumps(reading.as_dict()) + ',')
                json_file.flush()


class HtmlWriter(QueueWriter):
    # schreibt eine HTML-Datei (ohne Header und Footer)
    def write(self, reading):
        unit = 'F' if self.options.fahrenheit else '°C'
        with open(self.options.html, 'a') as html_file:
            print(time.strftime('%c:', time.localtime(reading.time)), reading.type, '-', reading.checksum,
                  '- Temperatur 1:', reading.temperature_1, unit, 'Temperatur 2:', reading.temperature_2, unit,
                  '<br>', file=html_file)


class SqliteWriter(QueueWriter):
    # speichert die empfangenen Daten in eine SQLite-Datei
    def run(self):
        import sqlite3
        conn = sqlite3.connect(self.options.sqlite)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS maverick
                 (date integer, type text, id integer, temperature_1 real, temperature_2 real)''')
        while True:
            r = self.queue.get()
            cursor.execute("INSERT INTO maverick VALUES (?, ?, ?, ?, ?)",
                           (int(r.time), r.type, r.checksum, r.temperature_1, r.temperature_2))
            conn.commit()
            self.queue.task_done()


class ThingSpeakWriter(QueueWriter):
    """Postet die Daten auf ThingSpeak: bis zu 4 Sender mit je 2 Kanälen (8 Felder)."""

    def run(self):
        import urllib.parse
        import urllib.request
        options = self.options
        unit_list = {}
        while True:
            # Bei neuen Daten sofort senden, sonst nach 15 s (Mindestintervall von ThingSpeak)
            try:
                r = self.queue.get(True, 15)
            except queue.Empty:
                r = None
            if r is not None:
                if r.checksum in unit_list:
                    unit_list[r.checksum].update(timestamp=int(r.time), temp1=r.temperature_1, temp2=r.temperature_2)
                else:
                    if len(unit_list) >= 4:
                        maxage = int(time.time() - 20)
                        oldestage = time.time()
                        oldestchksum = 0
                        for checksum, unit in unit_list.items():
                            if unit['timestamp'] <= maxage and unit['timestamp'] < oldestage:
                                oldestchksum = checksum
                                oldestage = unit['timestamp']
                                id = unit['id']
                        if oldestchksum != 0:
                            del unit_list[oldestchksum]
                        else:
                            print('All Slots in use, ignoring Device ', r.checksum)
                            continue
                    else:
                        slots = list(range(4))
                        for unit in unit_list.values():
                            slots.remove(unit['id'])
                        id = slots[0]
                    unit_list[r.checksum] = {'timestamp': int(r.time), 'id': id,
                                             'temp1': r.temperature_1, 'temp2': r.temperature_2}
            elif options.verbose:
                print('Nothing new received')
            # in den letzten 30 s empfangene Sender senden; der Status ordnet die Kanäle den Sendern zu
            status = ''
            fields = {}
            tosend = False
            for checksum, unit in unit_list.items():
                if unit['timestamp'] >= time.time() - 30:
                    tosend = True
                    fields.update({'field' + str(unit['id'] * 2 + 1): unit['temp1'],
                                   'field' + str(unit['id'] * 2 + 2): unit['temp2']})
                status += str(unit['id'] * 2 + 1) + '/' + str(unit['id'] * 2 + 2) + ':' + str(checksum) + ' '
            data = {'api_key': options.thingspeak, 'status': status}
            data.update(fields)
            request = urllib.request.Request('http://api.thingspeak.com/update',
                                             urllib.parse.urlencode(data).encode('utf-8'),
                                             {"Content-type": "application/x-www-form-urlencoded",
                                              "Accept": "text/plain"})
            if tosend:
                if options.verbose:
                    print('Sending to ThingSpeak')
                with urllib.request.urlopen(request):
                    pass


def main():
    parser = argparse.ArgumentParser(description='Receives Wireless BBQ Thermometer Telegrams via RF-Receiver')
    parser.add_argument('--html', nargs='?', const='maverick.html', help='Writes a HTML file')
    parser.add_argument('--json', nargs='?', const='maverick.json', help='Writes a JSON file')
    parser.add_argument('--sqlite', nargs='?', const='maverick.sqlite', help='Writes to an SQLite Database')
    parser.add_argument('--thingspeak', nargs='?', const='maverick.thingspeak', help='Writes to ThingSpeak (enter Write-API key)')
    parser.add_argument('--debug', action='store_true', help='Generates additional debugging Output')
    parser.add_argument('--pin', default=22, type=int, help='Sets the Pin number')
    parser.add_argument('--nosync', action='store_true', help='Always register new IDs')
    parser.add_argument('--fahrenheit', action='store_true', help='Sets the Output to Fahrenheit')
    parser.add_argument('--noappend', action='store_true', help='Don´t append to file')
    parser.add_argument('--verbose', action='store_true', help='Print more Information to stdout')
    options = parser.parse_args()
    if options.debug:
        print(options)

    writers = []
    for option, cls in (('html', HtmlWriter), ('json', JsonWriter), ('sqlite', SqliteWriter),
                        ('thingspeak', ThingSpeakWriter)):
        if getattr(options, option) is not None:
            if options.verbose:
                print('Starting {} writer Task'.format(option))
            writers.append(cls(options))

    def on_reading(reading):
        for writer in writers:
            writer.put(reading)

    pi = pigpio.pi()
    receiver = MaverickReceiver(pi, on_reading, pin=options.pin, nosync=options.nosync,
                                fahrenheit=options.fahrenheit, debug=options.debug, verbose=options.verbose)
    receiver.start()
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
        pi.stop()


if __name__ == '__main__':
    main()
