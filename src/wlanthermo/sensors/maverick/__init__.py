"""Funkthermometer Maverick ET-732/ET-733 mit zwei Fühlern.

Der Empfänger (receiver.py, eigener Dienst wlanthermo-maverick) dekodiert die
Funktelegramme und schreibt die Werte nach maverick.json. MaverickProbe liest
von dort die Temperatur eines der beiden Fühler.
"""
import codecs
import json
import logging
import time

from ..base import TemperatureSensor

logger = logging.getLogger('WLANthermo.sensors')

MAVERICK_FILE = '/var/www/tmp/maverick.json'
# Ältere Werte werden verworfen
MAX_AGE = 30


def read_maverick(path=MAVERICK_FILE, max_age=MAX_AGE):
    """Inhalt von maverick.json, None wenn nicht lesbar oder zu alt."""
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


class MaverickFile:
    """Die zuletzt gelesenen Werte des Empfängers; update() einmal je Messzyklus."""

    def __init__(self, path=MAVERICK_FILE):
        self.path = path
        self.values = None

    def update(self):
        self.values = read_maverick(self.path)


class MaverickProbe(TemperatureSensor):
    """Fühler 1 oder 2 des Funkthermometers."""

    def __init__(self, source, number):
        self.source = source    # MaverickFile
        self.number = number
        self.name = 'Maverick {}'.format(number)

    def read(self):
        if self.source.values is None:
            return None
        value = self.source.values['temperature_' + str(self.number)]
        return None if value == '' else value
