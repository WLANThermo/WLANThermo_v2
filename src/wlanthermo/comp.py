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


import sys
import os
import time
import logging
import psutil
import signal
import traceback
import gettext
import wlanthermo
import platform
from wlanthermo.alarm import AlarmMonitor, NotificationSchedule, ChannelStatus, safe_format
from wlanthermo.channels import AdcInput, MaverickInput, ThermocoupleInput
from wlanthermo.datafiles import CurrentTempFile, PitmasterReader, TemperatureLog, read_maverick
from wlanthermo.hardware import Board
from wlanthermo.notify import build_notifiers
from wlanthermo.sensors import load_sensors
from wlanthermo.settings import (CONFIG_FILE, SENSOR_FILE, ConfigWatcher, make_parser,
                                 parse_settings, parse_startup_settings, read_config_file)

pidfilename = '/var/run/wlt_2_comp.pid'

# wird in main() eingerichtet, sobald die Konfiguration gelesen ist
logger = None


class Shutdown(Exception):
    """Wird vom SIGTERM-Handler ausgelöst, um die Messschleife sauber zu beenden."""


def handle_sigterm(signum, frame):
    raise Shutdown()


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))

def main():
    global logger
    gettext.install('wlt_2_comp', localedir='/usr/share/WLANThermo/locale/')

    # Wir laufen als root, auch andere müssen die Config schreiben!
    os.umask (0)

    Config = make_parser()
    read_config_file(Config, CONFIG_FILE)
    startup = parse_startup_settings(Config)
    channel_count = startup.channel_count

    Config_Sensor = make_parser()
    read_config_file(Config_Sensor, SENSOR_FILE)

    logger = logging.getLogger('WLANthermo')
    if startup.log_level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        logger.setLevel(startup.log_level)
    handler = logging.FileHandler(startup.log_file)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    logger.info('WLANThermo started')

    sensors = load_sensors(Config_Sensor)

    #ueberpruefe ob der Dienst schon laeuft
    pid = str(os.getpid())

    if os.access(pidfilename, os.F_OK):
        pidfile = open(pidfilename, "r")
        pidfile.seek(0)
        old_pid = int(pidfile.readline())
        if check_pid(old_pid):
            print(_('%s already exists, Process is running, exiting') % pidfilename)
            logger.error('%s already exists, Process is running, exiting' % pidfilename)
            sys.exit()
        else:
            logger.info('%s already exists, Process is NOT running, resuming operation' % pidfilename)
            pidfile.seek(0)
            open(pidfilename, 'w').write(pid)

    else:
        logger.debug("%s written" % pidfilename)
        open(pidfilename, 'w').write(pid)


    sys.excepthook = log_uncaught_exceptions
    # systemd beendet den Dienst mit SIGTERM, dann ebenfalls aufräumen
    signal.signal(signal.SIGTERM, handle_sigterm)
    #GPIO END

    version = startup.version

    # Software-Version, wird beim build gesetzt
    build = wlanthermo.VERSION

    config_watcher = ConfigWatcher(CONFIG_FILE, lambda config: parse_settings(config, sensors, channel_count))

    alarms = AlarmMonitor(channel_count)
    schedule = NotificationSchedule()
    test_alarm = False

    try:
      with Board() as board:
        if startup.beeper_on_start:
            board.beeper.beep(1, on=1)

        current_temp_file = CurrentTempFile(startup.current_temp_file)
        pit_readers = [PitmasterReader(path) for path in startup.pit_files]
        temperature_log = TemperatureLog(startup.log_channels, startup.separator, [
            _('Controller output value'), _('Controller set value'),
            _('Controller 2 output value'), _('Controller 2 set value')])
        temperature_log.open(new_file=startup.new_log_on_restart)

        adc_input = AdcInput(board.adc, version)
        maverick_input = MaverickInput()
        thermocouple_input = ThermocoupleInput(board.thermocouples, startup.max31855) if version == 'miniV2' else None

        while True:
            time_start = time.time()
            CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
            ram = psutil.virtual_memory()
            ram_free = ram.free // 2**20
            logger.debug('CPU: {} RAM free: {}'.format(CPU_usage, ram_free))
            alarme = []
            statusse = []

            if startup.maverick:
                logger.info('Reading from Maverick receiver...')
                maverick = read_maverick()
            else:
                logger.info('Maverick is disabled')
                maverick = None

            Temperatur_string = [None for i in range(channel_count)]

            settings = config_watcher.current()
            channels = settings.channels
            alert = settings.alert
            temp_min = [channel.temp_min for channel in channels]
            temp_max = [channel.temp_max for channel in channels]

            if os.path.isfile('/var/www/alert.ack'):
                logger.info('alert.ack vorhanden')
                alarms.acknowledge()
                os.unlink('/var/www/alert.ack')

            if os.path.isfile('/var/www/alert.test'):
                logger.info('alert.test exists')
                test_alarm = True
                os.unlink('/var/www/alert.test')

            logger.debug('Measuring {} channels'.format(channel_count))

            Temperatur = (adc_input.read(channels[:8], settings.iterations)
                          + maverick_input.read(maverick))
            if thermocouple_input is not None:
                Temperatur += thermocouple_input.read()
            if settings.temp_unit == 'fahrenheit':
                Temperatur = [t * 1.8 + 32 if t is not None else None for t in Temperatur]

            evaluation = alarms.evaluate(Temperatur, temp_min, temp_max)
            alarm_irgendwo = evaluation.active

            for kanal in range(channel_count):
                alarm_values = dict()
                if settings.temp_unit == 'celsius':
                    alarm_values['temp_unit'] = '°C'
                    alarm_values['temp_unit_long'] = _('degrees Celsius')
                elif settings.temp_unit == 'fahrenheit':
                    alarm_values['temp_unit'] = '°F'
                    alarm_values['temp_unit_long'] = _('degrees Fahrenheit')
                alarm_values['kanal'] = kanal
                alarm_values['name'] = channels[kanal].name
                # Python 2 gab Floats mit 12 Stellen aus, Python 3 mit allen (74.21000000000001)
                alarm_values['temperatur'] = round(Temperatur[kanal], 2) if Temperatur[kanal] is not None else None
                alarm_values['temp_max'] = temp_max[kanal]
                alarm_values['temp_min'] = temp_min[kanal]
                alarm_values['lf'] = '\n'

                if Temperatur[kanal] is not None:
                    Temperatur_string[kanal] = "%.2f" % Temperatur[kanal]

                status = evaluation.statuses[kanal]
                if status == ChannelStatus.HI:
                    alarme.append(safe_format(alert.high_template, alarm_values))
                elif status == ChannelStatus.LO:
                    alarme.append(safe_format(alert.low_template, alarm_values))
                elif status == ChannelStatus.OK:
                    statusse.append(safe_format(alert.status_template, alarm_values))

            # Werte der Pitmaster, None wenn abgeschaltet oder nicht verfügbar
            pits = [reader.read() if on else None for reader, on in zip(pit_readers, settings.pit_on)]
            pit, pit2 = pits

            message_values = dict()

            message_values['pit_new'] = pit.new if pit is not None else '-'
            message_values['pit_set'] = pit.set if pit is not None else '-'
            message_values['pit2_new'] = pit2.new if pit2 is not None else '-'
            message_values['pit2_set'] = pit2.set if pit2 is not None else '-'

            message_values['alarme'] = ''.join(alarme)
            message_values['statusse'] = ''.join(statusse)
            message_values['lf'] = '\n'
            message_values['hostname'] = platform.node()

            alarm_message = safe_format(alert.message_template, message_values)


            # Beeper bei jedem unquittiertem Alarm
            if alarm_irgendwo:
                if settings.beeper:
                    logger.debug('BEEPER!!!')
                    board.beeper.beep(3)

            # Bei neuem Alarm oder Test sofort, sonst Alarm erneut bzw. periodisch den Status senden
            alarm_repeat, send_status, send = schedule.check(
                evaluation, test_alarm, alert.alarm_interval, alert.status_interval, time.time())

            # Nachrichten senden
            if send:
                if evaluation.new:
                    logger.debug('new alert, sending messages')
                if test_alarm:
                    logger.debug('test alert, sending messages')
                    test_alarm = False
                    alarm_message = _('test message\n') + alarm_message
                if alarm_repeat:
                    logger.info('repeated alert, sending messages')
                if send_status:
                    logger.info('sending status')

                for notifier in build_notifiers(settings):
                    notifier.send(alarm_message, urgent=alarm_irgendwo)

            Uhrzeit_lang = time.strftime('%d.%m.%y %H:%M:%S')
            current_temp_file.write(
                Uhrzeit_lang,
                ['' if t is None else t for t in Temperatur_string],
                evaluation.statuses,
                build,
                temperature_log.name)

            # Messzyklus protokollieren, nur die Kanäle, die in der Konfigurationsdatei angegeben sind
            log_line = temperature_log.line(Uhrzeit_lang, Temperatur, pits)
            temperature_log.append(log_line)
            logger.debug(log_line)

            delay = settings.delay
            time_remaining = time_start + delay - time.time()
            if time_remaining < 0:
                logger.warning('measuring loop running longer than {delay}s, remaining time {time_remaining}s'.format(delay=delay, time_remaining=time_remaining))
            else:
                logger.debug('measuring loop remaining time {time_remaining}s of {delay}s'.format(delay=delay, time_remaining=time_remaining))
                time.sleep(time_remaining)

    except (KeyboardInterrupt, Shutdown):
        logger.info('WLANThermo stopped!')
    finally:
        # Auch nach einem unerwarteten Fehler aufräumen; die Hardware schließt Board
        try:
            os.unlink(pidfilename)
        except OSError:
            pass
        logging.shutdown()


if __name__ == '__main__':
    main()
