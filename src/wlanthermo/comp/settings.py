"""Einstellungen von wlanthermo-comp aus WLANThermo.conf.

StartupSettings werden einmal beim Start gelesen (Hardware, Dateipfade,
Aufbau der Log-Datei). Settings werden bei jeder Änderung der Datei neu
gelesen, siehe ConfigWatcher.
"""
import codecs
import configparser
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger('WLANthermo.settings')

CONFIG_FILE = '/var/www/conf/WLANThermo.conf'
SENSOR_FILE = '/var/www/conf/sensor.conf'

# Ersatzwerte, wenn ein Wert in der Konfiguration nicht lesbar ist
DEFAULT_TEMP_MAX = 200
DEFAULT_TEMP_MIN = -20
DEFAULT_RESISTOR = 47


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


def channel_count_for(version):
    return 12 if version == 'miniV2' else 10


@dataclass
class StartupSettings:
    version: str
    max31855: bool
    maverick: bool
    current_temp_file: str
    pit_files: List[str]
    log_channels: List[bool]
    beeper_on_start: bool
    new_log_on_restart: bool
    separator: str
    log_file: str
    log_level: str

    @property
    def channel_count(self):
        return len(self.log_channels)


def parse_startup_settings(config):
    version = config.get('Hardware', 'version')
    return StartupSettings(
        version=version,
        max31855=config.getboolean('Hardware', 'max31855'),
        maverick=config.getboolean('ToDo', 'maverick_enabled'),
        current_temp_file=config.get('filepath', 'current_temp'),
        pit_files=[config.get('filepath', 'pitmaster'), config.get('filepath', 'pitmaster2')],
        # Nur einmal lesen, die Spalten der Log-Datei stehen beim Anlegen fest
        log_channels=[config.getboolean('Logging', 'CH' + str(kanal))
                      for kanal in range(channel_count_for(version))],
        beeper_on_start=config.getboolean('Sound', 'beeper_on_start'),
        new_log_on_restart=config.getboolean('Logging', 'write_new_log_on_restart'),
        separator=config.get('Logging', 'Separator'),
        log_file=config.get('daemon_logging', 'log_file'),
        log_level=config.get('daemon_logging', 'level_compy'),
    )


@dataclass
class ChannelSettings:
    name: str
    sensor_type: str          # Abschnitt in sensor.conf
    sensor: Optional[object]  # None, wenn der Typ in sensor.conf fehlt
    temp_min: float
    temp_max: float
    resistor: float           # Messwiderstand in kOhm


@dataclass
class AlertSettings:
    high_template: str
    low_template: str
    status_template: str
    message_template: str
    status_interval: int      # 0 = aus
    alarm_interval: int       # 0 = aus


@dataclass
class EmailSettings:
    server: str
    auth: bool
    username: str
    password: str
    sender: str
    recipient: str
    subject: str
    starttls: bool


@dataclass
class TelegramSettings:
    chat_id: str
    token: str


@dataclass
class PushSettings:
    url: str
    body: str


@dataclass
class Settings:
    channels: List[ChannelSettings]
    pit_on: List[bool]
    beeper: bool
    iterations: int
    delay: float
    temp_unit: str
    alert: AlertSettings
    # None = Benachrichtigungsart abgeschaltet
    email: Optional[EmailSettings]
    telegram: Optional[TelegramSettings]
    push: Optional[PushSettings]


def _getfloat(config, section, option, default, what):
    try:
        return config.getfloat(section, option)
    except ValueError:
        logger.error('Error reading {}, using {}'.format(what, default))
        return default


def _getint(config, section, option, default, what):
    try:
        return config.getint(section, option)
    except ValueError:
        logger.error('Error reading {} from config'.format(what))
        return default


def parse_channel(config, kanal, sensors):
    k = str(kanal)
    sensor_type = config.get('Sensoren', 'CH' + k)
    sensor = sensors.get(sensor_type)
    if sensor is None:
        logger.error('Unknown sensor type {} on channel {}'.format(sensor_type, kanal))
    return ChannelSettings(
        name=config.get('ch_name', 'ch_name' + k),
        sensor_type=sensor_type,
        sensor=sensor,
        temp_min=_getfloat(config, 'temp_min', 'temp_min' + k, DEFAULT_TEMP_MIN,
                           'lower limit on channel ' + k),
        temp_max=_getfloat(config, 'temp_max', 'temp_max' + k, DEFAULT_TEMP_MAX,
                           'upper limit on channel ' + k),
        resistor=_getfloat(config, 'Messen', 'Messwiderstand' + k, DEFAULT_RESISTOR,
                           'measurement resistor on channel ' + k),
    )


def parse_settings(config, sensors, channel_count):
    """Einstellungen, die sich im Betrieb ändern können."""
    email = None
    if config.getboolean('Email', 'email_alert'):
        email = EmailSettings(
            server=config.get('Email', 'server'),
            auth=config.getboolean('Email', 'auth'),
            username=config.get('Email', 'username'),
            password=config.get('Email', 'password'),
            sender=config.get('Email', 'email_from'),
            recipient=config.get('Email', 'email_to'),
            subject=config.get('Email', 'email_subject'),
            starttls=config.getboolean('Email', 'starttls'),
        )
    telegram = None
    if config.getboolean('Telegram', 'telegram_alert'):
        telegram = TelegramSettings(
            chat_id=config.get('Telegram', 'telegram_chat_id'),
            token=config.get('Telegram', 'telegram_token'),
        )
    push = None
    if config.getboolean('Push', 'push_on'):
        push = PushSettings(url=config.get('Push', 'push_url'), body=config.get('Push', 'push_body'))

    return Settings(
        channels=[parse_channel(config, kanal, sensors) for kanal in range(channel_count)],
        pit_on=[config.getboolean('ToDo', 'pit_on'), config.getboolean('ToDo', 'pit2_on')],
        beeper=config.getboolean('Sound', 'Beeper_enabled'),
        iterations=config.getint('Messen', 'Iterations'),
        delay=config.getfloat('Messen', 'Delay'),
        temp_unit=config.get('locale', 'temp_unit'),
        alert=AlertSettings(
            high_template=config.get('Alert', 'alarm_high_template'),
            low_template=config.get('Alert', 'alarm_low_template'),
            status_template=config.get('Alert', 'status_template'),
            message_template=config.get('Alert', 'message_template'),
            status_interval=_getint(config, 'Alert', 'status_interval', 0, 'status interval'),
            alarm_interval=_getint(config, 'Alert', 'alarm_interval', 0, 'alarm interval'),
        ),
        email=email,
        telegram=telegram,
        push=push,
    )


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
