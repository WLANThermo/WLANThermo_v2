"""Dateien, über die wlanthermo-comp mit den anderen Diensten und dem Webinterface Daten austauscht.

- CurrentTempFile: aktuelle Werte für Webinterface und Display (eine Zeile, ';'-getrennt)
- TemperatureLog: CSV-Log aller Messzyklen, TEMPLOG.csv zeigt auf die aktuelle Datei
- PitmasterReader: aktuelle Werte eines Pitmasters
- read_maverick(): Werte des Maverick-Empfängers

Schreibfehler werden protokolliert und nicht weitergegeben, die Messung und
die Alarme sollen weiterlaufen.
"""
import codecs
import json
import logging
import os
import time
from collections import namedtuple

logger = logging.getLogger('WLANthermo.datafiles')

LOG_DIR = '/var/log/WLAN_Thermo'
MAVERICK_FILE = '/var/www/tmp/maverick.json'
# Ältere Maverick-Werte werden verworfen
MAVERICK_MAX_AGE = 30


def _write_synced(f, text):
    f.write(text)
    f.flush()
    os.fsync(f.fileno())


class CurrentTempFile:
    def __init__(self, path):
        self.path = path
        directory = os.path.dirname(path)
        # liegt im RAM-Laufwerk und fehlt nach einem Neustart
        if not os.path.exists(directory):
            os.makedirs(directory)

    def write(self, timestamp, temperatures, statuses, version, log_name):
        """temperatures als Text ('' ohne Wert), statuses als ChannelStatus."""
        fields = ([timestamp] + list(temperatures) + [status.value for status in statuses]
                  + [version, log_name])
        tmp = self.path + '_tmp'
        try:
            # über eine temporäre Datei, damit die Leser nie eine halbe Zeile sehen
            with codecs.open(tmp, 'w', 'utf_8') as f:
                _write_synced(f, ';'.join(fields))
            os.rename(tmp, self.path)
        except OSError as e:
            logger.error('Could not write to file {file}: {err}'.format(file=self.path, err=e))


class TemperatureLog:
    """CSV-Log, eine Zeile je Messzyklus.

    Die Spalten (geloggte Kanäle) stehen beim Anlegen der Datei fest.
    """

    def __init__(self, log_channels, separator, header, directory=LOG_DIR):
        self.log_channels = log_channels
        self.separator = separator
        self.header = header          # Spaltennamen nach den Kanälen (Pitmaster)
        self.directory = directory
        self.link = os.path.join(directory, 'TEMPLOG.csv')
        self.path = None

    def open(self, new_file):
        """Neue Datei anlegen oder, wenn gewünscht und vorhanden, an die bisherige anhängen."""
        os.makedirs(self.directory, exist_ok=True)
        # exists() ist auch bei einem kaputten Link False
        if not new_file and os.path.exists(self.link):
            self.path = self.link
        else:
            self.create(os.path.join(self.directory, time.strftime('%Y%m%d_%H%M%S') + '_TEMPLOG.csv'))

    def create(self, path):
        self.path = path
        try:
            os.remove(self.link)
        except FileNotFoundError:
            pass
        try:
            os.symlink(path, self.link)
        except OSError as e:
            logger.error('Could not create symlink to {file}: {err}'.format(file=path, err=e))
        columns = [_('Date_Time')]
        columns += ['Kanal ' + str(kanal) for kanal, logged in enumerate(self.log_channels) if logged]
        columns += self.header
        try:
            with codecs.open(path, 'w', 'utf_8') as f:
                _write_synced(f, self.separator.join(columns) + '\n')
        except OSError as e:
            logger.error('Could not create log file {file}: {err}'.format(file=path, err=e))

    @property
    def name(self):
        """Name der aktuellen Log-Datei ohne Verzeichnis und Endung, z.B. 20181024_183012_TEMPLOG."""
        try:
            path = os.readlink(self.link)
        except OSError:
            # Link fehlt oder ist eine normale Datei
            path = self.path
        return os.path.splitext(os.path.basename(path))[0]

    def line(self, timestamp, temperatures, pits):
        """temperatures: Werte aller Kanäle (None ohne Wert), pits: PitValues oder None je Pitmaster."""
        fields = [timestamp]
        fields += ['' if t is None else str(t)
                   for t, logged in zip(temperatures, self.log_channels) if logged]
        for pit in pits:
            fields += [pit.new, pit.set] if pit is not None else ['', '']
        return self.separator.join(fields)

    def append(self, line):
        try:
            with codecs.open(self.path, 'a', 'utf_8') as f:
                _write_synced(f, line + '\n')
        except OSError as e:
            logger.error('Could not write to file {file}: {err}'.format(file=self.path, err=e))


PitValues = namedtuple('PitValues', 'new set')


class PitmasterReader:
    """Liest die Übergabedatei eines Pitmasters: Zeit;Soll;Ist;Stellwert%;Meldung (siehe pitmaster.py)"""

    def __init__(self, path):
        self.path = path

    def read(self):
        try:
            with codecs.open(self.path, 'r', 'utf_8') as f:
                values = f.readline().split(';')
            return PitValues(new=values[3].rstrip('%'), set=values[1])
        except (OSError, IndexError):
            # IndexError: Datei leer oder gerade unvollständig geschrieben
            return None


def read_maverick(path=MAVERICK_FILE, max_age=MAVERICK_MAX_AGE):
    try:
        with codecs.open(path, 'r', 'utf_8') as f:
            values = json.load(f)
    except ValueError:
        logger.error('Maverick file is no valid JSON')
        return None
    except OSError:
        logger.info('Maverick file could not be read')
        return None

    age = time.time() - values['time']
    if age > max_age:
        logger.debug('Maverick values too old, {} sec'.format(age))
        return None
    return values
