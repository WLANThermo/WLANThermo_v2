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
import codecs
from bitstring import BitArray
import pigpio
from struct import pack, unpack
import json
import statistics
import platform
from wlanthermo.alarm import AlarmMonitor, NotificationSchedule, ChannelStatus, safe_format
from wlanthermo.notify import build_notifiers
from wlanthermo.sensors import KTypeSensor, load_sensors, median_filter, resistance_from_adc
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

def open_softspi(cs, baud):
    # Ist der Bus noch von einem vorherigen Lauf offen, kann er weiter benutzt werden
    try:
        pi.bb_spi_open(cs, MISO, MOSI, SCLK, baud, 0)
    except pigpio.error as e:
        if e.value != pigpio.error_text(pigpio.PI_GPIO_IN_USE):
            raise


def close_softspi(cs):
    try:
        pi.bb_spi_close(cs)
    except pigpio.error as e:
        logger.warning('Could not close SPI on CS {}: {}'.format(cs, e))


def get_channel_mcp(channel):
    if channel > 7:
        raise ValueError()
    command = pack('>Hx', (0x18 + channel) << 6)
    return unpack('>xH', pi.bb_spi_xfer(CS, command)[1])[0] & 0x0FFF


def get_channel_max31855(channel):
    if channel > 1:
        raise ValueError()
    data = BitArray(pi.bb_spi_xfer(8 - channel, b"\x00\x00")[1])
    if data[15]:
        return None
    else:
        return data[0:14].int / 4.0


def dateiname():
    # Zeitstring fuer eindeutige Dateinamen erzeugen
    # fn = YYYYMMDD_HHMMSS
    fn = time.strftime('%Y%m%d_%H%M%S')
    return fn


def create_logfile(filename, log_kanal, separator):
    # Falls der Symlink noch da ist, loeschen
    try:
        os.remove('/var/log/WLAN_Thermo/TEMPLOG.csv')
    except FileNotFoundError:
        pass

    # Symlink TEMPLOG.csv auf die gerade benutzte eindeutige Log-Datei legen.
    try:
        os.symlink(filename, '/var/log/WLAN_Thermo/TEMPLOG.csv')
    except OSError as e:
        logger.error('Could not create symlink to {file}: {err}'.format(file=filename, err=e))

    kopfzeile = []
    kopfzeile.append(_('Date_Time'))
    for kanal, logged in enumerate(log_kanal):
        if logged:
            kopfzeile.append('Kanal ' + str(kanal))
            
    kopfzeile.append(_('Controller output value'))
    kopfzeile.append(_('Controller set value'))
    kopfzeile.append(_('Controller 2 output value'))
    kopfzeile.append(_('Controller 2 set value'))
    
    try:
        with codecs.open(filename, 'w', 'utf_8') as fw: #Datei anlegen
            fw.write(separator.join(kopfzeile) + '\n') # Kopfzeile der CSV-Datei schreiben
            fw.flush()
            os.fsync(fw.fileno())
    except OSError as e:
        logger.error('Could not create log file {file}: {err}'.format(file=filename, err=e))

def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))

def read_maverick():
    try:
        with codecs.open('/var/www/tmp/maverick.json', 'r', 'utf_8') as maverick_json:
            values = json.load(maverick_json)
    except ValueError:
        logger.error('Maverick file is no valid JSON')
        return None
    except IOError:
        logger.info('Maverick file could not be read')
        return None

    age = time.time() - values['time']
    if age > 30:
        logger.debug('Maverick values too old, {} sec'.format(age))
        return None

    return values

# Variablendefinition und GPIO Pin-Definition
ADC_Channel = 0  # Analog/Digital-Channel
#GPIO START
SCLK        = 18 # Serial-Clock
MOSI        = 24 # Master-Out-Slave-In
MISO        = 23 # Master-In-Slave-Out
CS          = 25 # Chip-Select
CS_MAX1 = 8 # MAX31855 IC1
CS_MAX2 = 7 # MAX31855 IC2
BEEPER      = 17 # Piepser
PWM         = 4
IO          = 2


def main():
    global logger, pi
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
    current_temp = startup.current_temp_file
    log_kanal = startup.log_channels
    separator = startup.separator

    # Software-Version, wird beim build gesetzt
    build = wlanthermo.VERSION

    pi = pigpio.pi()
    open_softspi(CS, 20000)
    open_softspi(CS_MAX1, 250000)
    open_softspi(CS_MAX2, 250000)
    # Pin-Programmierung (Pitmaster)
    pi.set_mode(PWM, pigpio.OUTPUT)
    pi.set_mode(IO, pigpio.OUTPUT)

    # Pin-Programmierung (Beeper)
    pi.set_mode(BEEPER, pigpio.OUTPUT)

    pi.write(PWM, 0)
    pi.write(IO, 0)

    if startup.beeper_on_start:
        pi.write(BEEPER, 1)
        time.sleep(1)
        pi.write(BEEPER, 0)

    # Pfad fuer die uebergabedateien auslesen und auftrennen in Pfad und Dateinamen
    curPath,curFile = os.path.split(current_temp)

    #Wenn das display Verzeichniss im Ram Drive nicht exisitiert erstelle es
    if not os.path.exists(curPath):
        os.makedirs(curPath)

    #Temperatur-LOG-Verzeichnis anlegen, wenn noch nicht vorhanden und aktuelle Log-Datei generieren
    try:
        os.mkdir('/var/log/WLAN_Thermo')
    except: 
        pass

    name = "/var/log/WLAN_Thermo/"  + dateiname() +'_TEMPLOG.csv' #eindeutigen Namen generieren 
    if startup.new_log_on_restart:# neues File beim Start anlegen
        create_logfile(name, log_kanal, separator)
    else:
        #Kein neues File anlegen
        if os.path.exists('/var/log/WLAN_Thermo/TEMPLOG.csv'):
            # pruefen, ob die Datei schon da ist zum anhaengen, auch False bei Broken Link!
            name = '/var/log/WLAN_Thermo/TEMPLOG.csv'
        else:
            create_logfile(name, log_kanal, separator)

    config_watcher = ConfigWatcher(CONFIG_FILE, lambda config: parse_settings(config, sensors, channel_count))
    Temperatur = [None for i in range(channel_count)]

    alarms = AlarmMonitor(channel_count)
    schedule = NotificationSchedule()
    test_alarm = False

    try:
        while True:
            time_start = time.time()
            CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
            ram = psutil.virtual_memory()
            ram_free = ram.free // 2**20
            logger.debug('CPU: {} RAM free: {}'.format(CPU_usage, ram_free))
            alarme = []
            statusse = []
            pit = {}
            pit2 = {}

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

            samples = [[] for i in range(8)]

            for i in range(settings.iterations):
                for kanal in range(8):
                    if version == 'v1' or isinstance(channels[kanal].sensor, KTypeSensor):
                        # Nicht invertiert messen
                        samples[kanal].append(get_channel_mcp(kanal))
                    else:
                        # Spannungsteiler ist nach v1 anders herum aufgebaut
                        samples[kanal].append(4095 - get_channel_mcp(kanal))

            for kanal in range(channel_count):
                if kanal <= 7:
                    median_value = median_filter(samples[kanal])
                    sensor = channels[kanal].sensor
                    if sensor is not None and (median_value > 15) and (median_value < 4080):
                        if isinstance(sensor, KTypeSensor):
                            Temperatur[kanal] = sensor.temperature_from_adc(median_value)
                        else:
                            Temperatur[kanal] = sensor.temperature(resistance_from_adc(median_value, channels[kanal].resistor))
                            if Temperatur[kanal] is not None:
                                Temperatur[kanal] = round(Temperatur[kanal], 2)
                    else:
                        Temperatur[kanal] = None
                    variance = statistics.pvariance(samples[kanal])
                    if variance > 4:
                        warnung = 'Channel:{kanal} variance: {variance} in {iterations}, median @ {median_value}!'.format(
                            kanal=kanal,
                            variance=variance,
                            iterations=settings.iterations,
                            median_value=median_value)
                        logger.warning(warnung)
                    logger.debug('Channel {}, MCP3128 {}, temperature {}'.format(kanal, kanal, Temperatur[kanal]))
                elif kanal <= 9:
                    if maverick is None:
                        Temperatur[kanal] = None
                        logger.debug('Channel {}, disabled or not available'.format(kanal))
                    else:
                        maverick_value = maverick['temperature_' + str(kanal - 7)]
                        if maverick_value == '':
                            Temperatur[kanal] = None
                        else:
                            Temperatur[kanal] = maverick_value
                        logger.debug('Channel {}, Maverick {}, temperature {}'.format(kanal, kanal - 7, Temperatur[kanal]))
                elif version == 'miniV2':
                    if startup.max31855:
                        Temperatur[kanal] = get_channel_max31855(kanal - 10)
                        logger.debug('Channel {}, MAX31855 {}, temperature {}'.format(kanal, kanal - 10, Temperatur[kanal]))
                    else:
                        Temperatur[kanal] = None
                        logger.debug('Channel {}, disabled'.format(kanal))
                else:
                    logger.error('Channel {} checked without a reason!'.format(kanal))
                    Temperatur[kanal] = None

                if settings.temp_unit == 'fahrenheit' and Temperatur[kanal] is not None:
                    Temperatur[kanal] = Temperatur[kanal] * 1.8 + 32

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

            if settings.pit_on[0]:
                try:
                    with codecs.open(startup.pit_files[0], 'r', 'utf_8') as pitfile:
                        pit_values = pitfile.readline().split(';')
                        pit['new'] = pit_values[3].rstrip('%')
                        pit['set'] = pit_values[1]
                except (OSError, IndexError):
                    # IndexError: Datei leer oder gerade unvollständig geschrieben
                    # Wenn keine aktuellen Werte verfügbar sind, leere Werte schreiben
                    pit = None
            else:
                    pit = None

            if settings.pit_on[1]:
                try:
                    with codecs.open(startup.pit_files[1], 'r', 'utf_8') as pit2file:
                        pit2_values = pit2file.readline().split(';')
                        pit2['new'] = pit2_values[3].rstrip('%')
                        pit2['set'] = pit2_values[1]
                except (OSError, IndexError):
                    # IndexError: Datei leer oder gerade unvollständig geschrieben
                    # Wenn keine aktuellen Werte verfügbar sind, leere Werte schreiben
                    pit2 = None
            else:
                    pit2 = None


            message_values = dict()

            message_values['pit_new'] = pit['new'] if pit is not None else '-'
            message_values['pit_set'] = pit['set'] if pit is not None else '-'
            message_values['pit2_new'] = pit2['new'] if pit2 is not None else '-'
            message_values['pit2_set'] = pit2['set'] if pit2 is not None else '-'

            message_values['alarme'] = ''.join(alarme)
            message_values['statusse'] = ''.join(statusse)
            message_values['lf'] = '\n'
            message_values['hostname'] = platform.node()

            alarm_message = safe_format(alert.message_template, message_values)


            # Beeper bei jedem unquittiertem Alarm
            if alarm_irgendwo:
                if settings.beeper:
                    logger.debug('BEEPER!!!')
                    pi.write(BEEPER, 1)
                    time.sleep(0.2)
                    pi.write(BEEPER, 0)
                    time.sleep(0.2)
                    pi.write(BEEPER, 1)
                    time.sleep(0.2)
                    pi.write(BEEPER, 0)
                    time.sleep(0.2)
                    pi.write(BEEPER, 1)
                    time.sleep(0.2)
                    pi.write(BEEPER, 0)

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

            # Log datei erzeugen
            lcsv = []
            Uhrzeit_lang = time.strftime('%d.%m.%y %H:%M:%S')
            try:
                logdatei = os.readlink('/var/log/WLAN_Thermo/TEMPLOG.csv')
            except OSError:
                # Symlink fehlt oder ist eine normale Datei
                logdatei = name
            # Name der Log-Datei ohne Verzeichnis und Endung, z.B. 20181024_183012_TEMPLOG
            logdatei = os.path.splitext(os.path.basename(logdatei))[0]
            lcsv.append(Uhrzeit_lang)
            for kanal in range(channel_count):
                if Temperatur_string[kanal] is None:
                    lcsv.append('')
                else:
                    lcsv.append(str(Temperatur_string[kanal]))
            for kanal in range(channel_count):
                # 8 Felder mit allen Alarmzuständen
                lcsv.append(evaluation.statuses[kanal].value)
            lcsv.append(build)
            lcsv.append(logdatei)


            # Bei einem Fehler nur protokollieren, die Messung und die Alarme sollen weiterlaufen
            try:
                with codecs.open(current_temp + '_tmp', 'w', 'utf_8') as fcsv:
                    fcsv.write(';'.join(lcsv))
                    fcsv.flush()
                    os.fsync(fcsv.fileno())
                os.rename(current_temp + '_tmp', current_temp)
            except OSError as e:
                logger.error('Could not write to file {file}: {err}'.format(file=current_temp, err=e))

            #Messzyklus protokollieren und nur die Kanaele loggen, die in der Konfigurationsdatei angegeben sind
            log_line = []
            log_line.append(Uhrzeit_lang)

            for kanal in range(channel_count):
                if (log_kanal[kanal]):
                    if Temperatur[kanal] is None:
                        log_line.append('')
                    else:
                        log_line.append(str(Temperatur[kanal]))

            if pit is not None:
                log_line.append(pit['new'])
                log_line.append(pit['set'])
            else:
                log_line.append('')
                log_line.append('')

            if pit2 is not None:
                log_line.append(pit2['new'])
                log_line.append(pit2['set'])
            else:
                log_line.append('')
                log_line.append('')

            try:
                # Generierung des Logfiles
                with codecs.open(name, 'a', 'utf_8') as logfile:
                    logfile.write(separator.join(log_line) + '\n')
                    logfile.flush()
                    os.fsync(logfile.fileno())
            except OSError as e:
                logger.error('Could not write to file {file}: {err}'.format(file=name, err=e))
            # Werte loggen
            logger.debug(separator.join(log_line))

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
        # Auch nach einem unerwarteten Fehler aufräumen
        close_softspi(CS)
        close_softspi(CS_MAX1)
        close_softspi(CS_MAX2)
        pi.stop()
        try:
            os.unlink(pidfilename)
        except OSError:
            pass
        logging.shutdown()


if __name__ == '__main__':
    main()
