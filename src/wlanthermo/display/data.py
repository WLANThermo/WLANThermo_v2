"""Aktuelle Werte für die Displays und Benachrichtigung bei Änderungen.

Läuft der Kernprozess, kommen Messung und Pitmaster-Werte über seine
Schnittstelle (subscribe); jede neue Messung löst eine Benachrichtigung aus.
Ist er nicht erreichbar (nicht gestartet, oder comp läuft allein), werden die
Übergabedateien gelesen und ihre Änderungszeit jede Sekunde geprüft.
Änderungen der Konfiguration werden immer über die Änderungszeit erkannt.

Die Werte haben das Format, das die Displays bisher aus den Dateien gelesen haben.
"""
import codecs
import logging
import os
import threading
import time

from ..core.client import CoreClient, CoreError

logger = logging.getLogger('WLANthermo.display')

TEMPS = 'temps'
CONFIG = 'config'


def pit_name(instance):
    return 'pit' if instance == 0 else 'pit{}'.format(instance + 1)


def file_timestamp(text):
    return time.mktime(time.strptime(text, '%d.%m.%y %H:%M:%S'))


def display_value(temperature):
    """Wert auf eine Stelle gerundet als Text; wie aus der Übergabedatei (dort 2 Stellen)."""
    return str(round(float('%.2f' % temperature), 1))


def temps_from_measurement(measurement, channel_count):
    temps = {'timestamp': float(int(measurement['time']))}
    values = measurement['temperatures']
    statuses = measurement['statuses']
    for channel in range(channel_count):
        value = values[channel] if channel < len(values) else None
        temps[channel] = {'alert': statuses[channel] if channel < len(statuses) else 'er',
                          'value': display_value(value) if value is not None else None}
    return temps


def temps_from_file(path, channel_count):
    if not os.path.isfile(path):
        return None
    with codecs.open(path, 'r', 'utf_8') as f:
        temps_raw = f.read().split(';')
    temps = {'timestamp': file_timestamp(temps_raw[0])}
    for count in range(channel_count):
        try:
            alert = temps_raw[count + channel_count + 1]
        except IndexError:
            alert = 'er'
        try:
            value = None if temps_raw[count + 1] == '' else str(round(float(temps_raw[count + 1]), 1))
        except (IndexError, ValueError):
            value = None
        temps[count] = {'alert': alert, 'value': value}
    return temps


def pitmaster_from_state(state):
    return {'timestamp': float(int(state['time'])), 'set': float(state['setpoint']), 'now': state['current'],
            'new': float(state['output']), 'msg': state['message']}


def pitmaster_from_file(path):
    if not os.path.isfile(path):
        return None
    with codecs.open(path, 'r', 'utf_8') as f:
        pitmaster_raw = f.read().split(';', 4)
    # Manchmal steht nichts in der Datei, dann so tun als ob nichts da ist
    if pitmaster_raw[0] == '':
        return None
    return {'timestamp': file_timestamp(pitmaster_raw[0]), 'set': float(pitmaster_raw[1]),
            'now': None if pitmaster_raw[2] == '' else float(pitmaster_raw[2]),
            'new': float(pitmaster_raw[3].rstrip('%')), 'msg': pitmaster_raw[4]}


class DisplayData:
    """Werte und Änderungen für ein Display.

    on_change(name) wird bei jeder Änderung aufgerufen: 'temps', 'pit', 'pit2', 'config'.
    """

    RETRY = 5   # s bis zum nächsten Verbindungsversuch zum Kernprozess

    def __init__(self, on_change, current_temp_file, pit_files, config_file, client=None, poll=1.0):
        self.on_change = on_change
        self.current_temp_file = current_temp_file
        self.pit_files = list(pit_files)
        self.config_file = config_file
        self.client = client if client is not None else CoreClient()
        self.poll = poll
        self.connected = False
        self.measurement = None
        self.pits = {}
        self._mtimes = {}
        self._stop = threading.Event()
        self._thread = None

    # Werte ------------------------------------------------------------
    def temps(self, channel_count):
        """{'timestamp': ..., Kanal: {'alert': ..., 'value': ...}} oder None."""
        if self.connected:
            if self.measurement is None:
                return None
            return temps_from_measurement(self.measurement, channel_count)
        return temps_from_file(self.current_temp_file, channel_count)

    def pitmaster(self, instance):
        """{'timestamp', 'set', 'now', 'new', 'msg'} oder None, wenn der Pitmaster nicht läuft."""
        if self.connected:
            state = self.pits.get(instance)
            return pitmaster_from_state(state) if state is not None else None
        if instance >= len(self.pit_files):
            return None
        return pitmaster_from_file(self.pit_files[instance])

    # Änderungen -------------------------------------------------------
    def start(self):
        self._check_mtime(CONFIG, self.config_file, notify=False)
        self._thread = threading.Thread(target=self._run, name='display-data', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _check_mtime(self, name, path, notify=True):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = None
        if self._mtimes.get(name, mtime) != mtime and notify:
            self._mtimes[name] = mtime
            self.on_change(name)
        self._mtimes[name] = mtime

    def _handle(self, changes):
        for topic, value in changes.items():
            if topic == 'measurement':
                self.measurement = value
                self.on_change(TEMPS)
            elif topic.startswith('pit/'):
                instance = int(topic.split('/')[1])
                if value is None:
                    self.pits.pop(instance, None)
                else:
                    self.pits[instance] = value
                self.on_change(pit_name(instance))

    def _subscribe(self):
        """Folgt den Änderungen des Kernprozesses, bis die Verbindung endet."""
        for changes in self.client.subscribe(topics=['measurement', 'pit/'], timeout=self.RETRY * 6):
            if not self.connected:
                logger.info('Connected to wlanthermo-core')
                self.connected = True
                self.measurement = None
                self.pits = {}
            self._handle(changes)
            self._check_mtime(CONFIG, self.config_file)
            if self._stop.is_set():
                return

    def _poll_files(self, duration):
        """Ohne Kernprozess: Änderungszeit der Dateien prüfen."""
        end = time.monotonic() + duration
        while not self._stop.is_set() and time.monotonic() < end:
            self._check_mtime(TEMPS, self.current_temp_file)
            for instance, path in enumerate(self.pit_files):
                self._check_mtime(pit_name(instance), path)
            self._check_mtime(CONFIG, self.config_file)
            self._stop.wait(self.poll)

    def _run(self):
        while not self._stop.is_set():
            try:
                self._subscribe()
            except (CoreError, OSError, ValueError) as e:
                if self.connected:
                    logger.warning('Connection to wlanthermo-core lost: {}'.format(e))
                    self.on_change(TEMPS)
            if self.connected:
                # Ende des Abonnements ohne Fehler (Zeitüberschreitung): neu verbinden
                self.connected = False
                continue
            self._poll_files(self.RETRY)
