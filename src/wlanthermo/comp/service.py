#!/usr/bin/python3
# coding=utf-8

# Copyright (c) 2013, 2014, 2015 Armin Thinnes
# Copyright (c) 2015 - 2018 Björn Schrader
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Hauptdienst: misst die Temperaturen, wertet die Grenzwerte aus, alarmiert und protokolliert.

Ein Messzyklus (Comp.cycle) läuft alle [Messen] delay Sekunden.
"""
import gettext
import logging
import os
import platform
import signal
import sys
import time
import traceback

import psutil

import wlanthermo
from .alarm import AlarmMonitor, ChannelStatus, NotificationSchedule, safe_format
from .channels import AdcInput, MaverickInput, ThermocoupleInput
from .datafiles import CurrentTempFile, PitmasterReader, TemperatureLog, read_maverick
from .hardware import Board
from .notify import build_notifiers
from .sensors import load_sensors
from .settings import (CONFIG_FILE, SENSOR_FILE, ConfigWatcher, make_parser,
                       parse_settings, parse_startup_settings, read_config_file)

PIDFILE = '/var/run/wlt_2_comp.pid'
# Vom Webinterface angelegt: Alarme quittieren bzw. Testnachricht senden
ACK_FILE = '/var/www/alert.ack'
TEST_FILE = '/var/www/alert.test'

logger = logging.getLogger('WLANthermo')


class Shutdown(Exception):
    """Wird vom SIGTERM-Handler ausgelöst, um die Messschleife sauber zu beenden."""


def handle_sigterm(signum, frame):
    raise Shutdown()


def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))


def to_fahrenheit(celsius):
    return celsius * 1.8 + 32 if celsius is not None else None


def temp_unit_values(temp_unit):
    # _() mit festem Text, damit xgettext die Texte findet
    if temp_unit == 'celsius':
        return {'temp_unit': '°C', 'temp_unit_long': _('degrees Celsius')}
    if temp_unit == 'fahrenheit':
        return {'temp_unit': '°F', 'temp_unit_long': _('degrees Fahrenheit')}
    return {}


def build_message(settings, temperatures, evaluation, pits, hostname):
    """Nachricht aus den Vorlagen in [Alert]: Alarme und Status aller Kanäle, Pitmaster-Werte."""
    alert = settings.alert
    unit_values = temp_unit_values(settings.temp_unit)
    alarme = []
    statusse = []
    for kanal, (channel, temperature, status) in enumerate(
            zip(settings.channels, temperatures, evaluation.statuses)):
        values = {
            'kanal': kanal,
            'name': channel.name,
            # Python 2 gab Floats mit 12 Stellen aus, Python 3 mit allen (74.21000000000001)
            'temperatur': round(temperature, 2) if temperature is not None else None,
            'temp_max': channel.temp_max,
            'temp_min': channel.temp_min,
            'lf': '\n',
        }
        values.update(unit_values)
        if status == ChannelStatus.HI:
            alarme.append(safe_format(alert.high_template, values))
        elif status == ChannelStatus.LO:
            alarme.append(safe_format(alert.low_template, values))
        elif status == ChannelStatus.OK:
            statusse.append(safe_format(alert.status_template, values))

    message_values = {'alarme': ''.join(alarme), 'statusse': ''.join(statusse), 'lf': '\n', 'hostname': hostname}
    for prefix, pit in zip(('pit', 'pit2'), pits):
        message_values[prefix + '_new'] = pit.new if pit is not None else '-'
        message_values[prefix + '_set'] = pit.set if pit is not None else '-'
    return safe_format(alert.message_template, message_values)


class Comp:
    def __init__(self, startup, sensors, board):
        self.startup = startup
        self.board = board
        self.config = ConfigWatcher(
            CONFIG_FILE, lambda config: parse_settings(config, sensors, startup.channel_count))
        self.alarms = AlarmMonitor(startup.channel_count)
        self.schedule = NotificationSchedule()
        self.test_alarm = False

        self.adc_input = AdcInput(board.adc, startup.version)
        self.maverick_input = MaverickInput()
        self.thermocouple_input = None
        if startup.version == 'miniV2':
            self.thermocouple_input = ThermocoupleInput(board.thermocouples, startup.max31855)

        self.current_temp_file = None
        self.temperature_log = None
        self.pit_readers = [PitmasterReader(path) for path in startup.pit_files]

    def start(self):
        if self.startup.beeper_on_start:
            self.board.beeper.beep(1, on=1)
        self.current_temp_file = CurrentTempFile(self.startup.current_temp_file)
        self.temperature_log = TemperatureLog(self.startup.log_channels, self.startup.separator, [
            _('Controller output value'), _('Controller set value'),
            _('Controller 2 output value'), _('Controller 2 set value')])
        self.temperature_log.open(new_file=self.startup.new_log_on_restart)

    def run(self):
        self.start()
        while True:
            self.cycle()

    def cycle(self):
        time_start = time.time()
        self.log_system_load()
        maverick = self.read_maverick()
        settings = self.config.current()
        self.check_web_requests()

        temperatures = self.measure(settings, maverick)
        evaluation = self.alarms.evaluate(temperatures,
                                          [channel.temp_min for channel in settings.channels],
                                          [channel.temp_max for channel in settings.channels])
        # Werte der Pitmaster, None wenn abgeschaltet oder nicht verfügbar
        pits = [reader.read() if on else None for reader, on in zip(self.pit_readers, settings.pit_on)]
        message = build_message(settings, temperatures, evaluation, pits, platform.node())

        # Summer bei jedem nicht quittierten Alarm
        if evaluation.active and settings.beeper:
            logger.debug('BEEPER!!!')
            self.board.beeper.beep(3)

        self.notify(settings, evaluation, message)
        self.write_outputs(temperatures, evaluation, pits)
        self.wait(time_start, settings.delay)

    def log_system_load(self):
        cpu_usage = psutil.cpu_percent(interval=1, percpu=True)
        ram_free = psutil.virtual_memory().free // 2 ** 20
        logger.debug('CPU: {} RAM free: {}'.format(cpu_usage, ram_free))

    def read_maverick(self):
        if not self.startup.maverick:
            logger.info('Maverick is disabled')
            return None
        logger.info('Reading from Maverick receiver...')
        return read_maverick()

    def check_web_requests(self):
        if os.path.isfile(ACK_FILE):
            logger.info('alert.ack vorhanden')
            self.alarms.acknowledge()
            os.unlink(ACK_FILE)
        if os.path.isfile(TEST_FILE):
            logger.info('alert.test exists')
            self.test_alarm = True
            os.unlink(TEST_FILE)

    def measure(self, settings, maverick):
        """Temperaturen aller Kanäle in der eingestellten Einheit, None ohne Wert."""
        logger.debug('Measuring {} channels'.format(self.startup.channel_count))
        temperatures = (self.adc_input.read(settings.channels[:8], settings.iterations)
                        + self.maverick_input.read(maverick))
        if self.thermocouple_input is not None:
            temperatures += self.thermocouple_input.read()
        if settings.temp_unit == 'fahrenheit':
            temperatures = [to_fahrenheit(t) for t in temperatures]
        return temperatures

    def notify(self, settings, evaluation, message):
        # Bei neuem Alarm oder Test sofort, sonst Alarm erneut bzw. periodisch den Status senden
        repeat, status, send = self.schedule.check(
            evaluation, self.test_alarm, settings.alert.alarm_interval, settings.alert.status_interval, time.time())
        if not send:
            return
        if evaluation.new:
            logger.debug('new alert, sending messages')
        if self.test_alarm:
            logger.debug('test alert, sending messages')
            self.test_alarm = False
            message = _('test message\n') + message
        if repeat:
            logger.info('repeated alert, sending messages')
        if status:
            logger.info('sending status')
        for notifier in build_notifiers(settings):
            notifier.send(message, urgent=evaluation.active)

    def write_outputs(self, temperatures, evaluation, pits):
        timestamp = time.strftime('%d.%m.%y %H:%M:%S')
        self.current_temp_file.write(
            timestamp,
            ['%.2f' % t if t is not None else '' for t in temperatures],
            evaluation.statuses,
            wlanthermo.VERSION,
            self.temperature_log.name)
        line = self.temperature_log.line(timestamp, temperatures, pits)
        self.temperature_log.append(line)
        logger.debug(line)

    @staticmethod
    def wait(time_start, delay):
        time_remaining = time_start + delay - time.time()
        if time_remaining < 0:
            logger.warning('measuring loop running longer than {delay}s, remaining time {time_remaining}s'.format(
                delay=delay, time_remaining=time_remaining))
        else:
            logger.debug('measuring loop remaining time {time_remaining}s of {delay}s'.format(
                delay=delay, time_remaining=time_remaining))
            time.sleep(time_remaining)


def setup_logging(startup):
    if startup.log_level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        logger.setLevel(startup.log_level)
    handler = logging.FileHandler(startup.log_file)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


def process_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def claim_pidfile():
    """Beendet das Programm, wenn der Dienst schon läuft, sonst wird die eigene PID eingetragen."""
    try:
        with open(PIDFILE) as f:
            old_pid = int(f.readline())
    except FileNotFoundError:
        old_pid = None
    except ValueError:
        logger.warning('{} is invalid, ignoring it'.format(PIDFILE))
        old_pid = None
    if old_pid is not None:
        if process_running(old_pid):
            print(_('%s already exists, Process is running, exiting') % PIDFILE)
            logger.error('%s already exists, Process is running, exiting' % PIDFILE)
            sys.exit()
        logger.info('%s already exists, Process is NOT running, resuming operation' % PIDFILE)
    else:
        logger.debug('%s written' % PIDFILE)
    with open(PIDFILE, 'w') as f:
        f.write(str(os.getpid()))


def main():
    gettext.install('wlt_2_comp', localedir='/usr/share/WLANThermo/locale/')

    # Wir laufen als root, auch andere müssen die Config schreiben!
    os.umask(0)

    config = make_parser()
    read_config_file(config, CONFIG_FILE)
    startup = parse_startup_settings(config)
    sensor_config = make_parser()
    read_config_file(sensor_config, SENSOR_FILE)

    setup_logging(startup)
    logger.info('WLANThermo started')
    sensors = load_sensors(sensor_config)

    claim_pidfile()
    sys.excepthook = log_uncaught_exceptions
    # systemd beendet den Dienst mit SIGTERM, dann ebenfalls aufräumen
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        with Board() as board:
            Comp(startup, sensors, board).run()
    except (KeyboardInterrupt, Shutdown):
        logger.info('WLANThermo stopped!')
    finally:
        # Auch nach einem unerwarteten Fehler aufräumen, die Hardware schließt Board
        try:
            os.unlink(PIDFILE)
        except OSError:
            pass
        logging.shutdown()


if __name__ == '__main__':
    main()
