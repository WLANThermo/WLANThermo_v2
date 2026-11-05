"""Lesen und Ändern von WLANThermo.conf und sensor.conf, gemeinsam für alle Dienste."""
import codecs
import configparser
import fcntl
import logging
import os
import threading
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


class ConfigFileLock:
    """Sperre für Änderungen an einer Konfigurationsdatei, über Threads und Prozesse hinweg.

    Wer die Datei ändert, liest sie unter der Sperre neu, ändert sie und schreibt
    sie, bevor er die Sperre freigibt (siehe update_config). Sonst überschreibt
    ein Prozess mit veraltetem Stand die Änderungen der anderen.
    """

    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self.lock_path = path + '.lock'
        self._thread_lock = threading.Lock()
        self._fd = None

    def __enter__(self):
        self._thread_lock.acquire()
        try:
            # nur lesend öffnen: flock braucht kein Schreibrecht, root und www-data teilen die Datei
            self._fd = os.open(self.lock_path, os.O_RDONLY | os.O_CREAT, 0o666)
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        except BaseException:
            self._thread_lock.release()
            raise
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
        finally:
            self._fd = None
            self._thread_lock.release()
        return False


def write_config_file(config, path=CONFIG_FILE):
    """Schreibt die Datei über eine temporäre Datei; die Sperre muss gehalten werden."""
    tmp = '{}_{}_{}'.format(path, os.getpid(), threading.get_ident())
    with codecs.open(tmp, 'w', 'utf_8') as f:
        for section in config.sections():
            f.write('[{}]\n'.format(section))
            for key, value in config.items(section, raw=True):
                f.write('{} = {}\n'.format(key, value))
            f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp, path)


_locks = {}


def config_lock(path=CONFIG_FILE):
    """Die Sperre zu einer Datei (eine je Pfad und Prozess)."""
    lock = _locks.get(path)
    if lock is None:
        lock = _locks.setdefault(path, ConfigFileLock(path))
    return lock


def update_config(changes, path=CONFIG_FILE):
    """Setzt Werte, z.B. {'ToDo': {'backup': 'False'}}, ohne andere Änderungen zu überschreiben.

    Liefert den geschriebenen Stand.
    """
    with config_lock(path):
        config = make_parser()
        read_config_file(config, path)
        for section, values in changes.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in values.items():
                config.set(section, key, str(value))
        write_config_file(config, path)
    return config
