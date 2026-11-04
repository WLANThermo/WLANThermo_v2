"""Lesen von WLANThermo.conf und sensor.conf, gemeinsam für alle Dienste."""
import codecs
import configparser
import logging
import os
import time

logger = logging.getLogger('WLANthermo.config')

CONFIG_FILE = '/var/www/conf/WLANThermo.conf'
SENSOR_FILE = '/var/www/conf/sensor.conf'


def make_parser():
    # Ohne Interpolation: '%' kommt in URLs und Passwörtern vor
    return configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))


def read_config_file(config, filename):
    """Liest die Datei in den Parser, bei Fehlern wird es jede Sekunde erneut versucht.

    Die Datei kann gerade vom Webinterface neu geschrieben werden.
    """
    while True:
        try:
            with codecs.open(filename, 'r', 'utf_8') as configfile:
                config.read_file(configfile)
        except (OSError, configparser.Error) as e:
            logger.warning('Could not read {}, retrying: {}'.format(filename, e))
            time.sleep(1)
            continue
        break


class ConfigWatcher:
    """Liest die Konfiguration neu, sobald sich die Datei geändert hat.

    Ist die geänderte Datei fehlerhaft, bleiben die bisherigen Einstellungen
    gültig und es wird im nächsten Zyklus erneut versucht. Beim ersten Lesen
    gibt es keine bisherigen Einstellungen, dann wird der Fehler weitergegeben.
    """

    def __init__(self, path, parse):
        self.path = path
        self.parse = parse    # ConfigParser -> Settings
        self.mtime = None
        self.settings = None

    def current(self):
        mtime = os.path.getmtime(self.path)
        if mtime != self.mtime:
            logger.info('Reading configuration again...')
            config = make_parser()
            read_config_file(config, self.path)
            try:
                self.settings = self.parse(config)
            except (configparser.Error, ValueError) as e:
                if self.settings is None:
                    raise
                logger.error('Invalid configuration, keeping previous settings: {}'.format(e))
            else:
                self.mtime = mtime
        return self.settings
