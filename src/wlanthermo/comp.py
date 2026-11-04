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
import configparser
import os
import time
import math
import logging
import urllib.request, urllib.error, urllib.parse
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

# Konfigurationsdatei einlesen
defaults = {'pit_control_out':'True'}
pidfilename = '/var/run/wlt_2_comp.pid'

# Zeitlimit in Sekunden für Email, Telegram und Push, damit die Messschleife nicht hängen bleibt
NETWORK_TIMEOUT = 10

# wird in main() eingerichtet, sobald die Konfiguration gelesen ist
logger = None


class Shutdown(Exception):
    """Wird vom SIGTERM-Handler ausgelöst, um die Messschleife sauber zu beenden."""


def handle_sigterm(signum, frame):
    raise Shutdown()


def read_config_file(config, filename):
    # Die Datei kann gerade vom Webinterface neu geschrieben werden, dann erneut versuchen
    while True:
        try:
            with codecs.open(filename, 'r', 'utf_8') as configfile:
                config.read_file(configfile)
        except (OSError, configparser.Error) as e:
            if logger:
                logger.warning('Could not read {}, retrying: {}'.format(filename, e))
            time.sleep(1)
            continue
        break


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

# Funktionsdefinition

##
## Formatierung von Strings auch wenn ein key nicht existiert.
##
def safe_format(template, args):
    message = ''
    for i in range(100):
        try:
            message = template.format(**args)
            break
        except KeyError as e:
            key_name = str(e).strip('\'')
            logger.error('Key "{key_name}" not found in template!'.format(key_name=key_name))
            template = template.replace('{' + key_name + '}', '!!' + key_name + '!!')
    return message

def alarm_email(SERVER,AUTH,USER,PASSWORT,STARTTLS,FROM,TO,SUBJECT,MESSAGE):
    logger.info('Send mail!')

    from smtplib import SMTP
    from smtplib import SMTPException
    from email.mime.text import MIMEText as text
    if STARTTLS:
        port=587
    else:
        port=25
    try:
        s = SMTP(SERVER, port, timeout=NETWORK_TIMEOUT)
        if STARTTLS:
            s.starttls()

        if AUTH:
            s.login(USER,PASSWORT)


        m = text(MESSAGE, 'plain', 'UTF-8')

        m['Subject'] = SUBJECT
        m['From'] = FROM
        m['To'] = TO


        s.sendmail(FROM,TO, m.as_string())
        s.quit()
        logger.debug('Alert Email has been sent!')
    except SMTPException as error:
        sendefehler = 'Error: unable to send email: {err}'.format(err=error)
        logger.error(sendefehler)
    except OSError as error:
        # Namensauflösung, Verbindungsaufbau, Zeitüberschreitung
        sendefehler = 'Error: unable to connect to mail server (no internet connection?): {err}'.format(err=error)
        logger.error(sendefehler)


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


def temperatur_sensor (Rt, typ): #Ermittelt die Temperatur
    name = Config_Sensor.get(typ,'name')
    
    T = None
    
    if not name in ('PT100', 'PT1000'):
        a = Config_Sensor.getfloat(typ,'a')
        b = Config_Sensor.getfloat(typ,'b')
        c = Config_Sensor.getfloat(typ,'c')
        Rn = Config_Sensor.getfloat(typ,'Rn')
        
        try: 
            v = math.log(Rt/Rn)
            T = (1/(a + b*v + c*v*v)) - 273
        except: #bei unsinnigen Werten (z.B. ein- ausstecken des Sensors im Betrieb) Wert 999.9
            pass
    else:
        Rkomp = Config_Sensor.getfloat(typ,'Rkomp')
        Rt = Rt - Rkomp
        if name == 'PT100':
            Rpt=0.1
        else:
            Rpt=1
        try: 
            T = (-1)*math.sqrt( Rt/(Rpt*-0.0000005775) + (0.0039083**2)/(4*((-0.0000005775)**2)) - 1/(-0.0000005775)) - 0.0039083/(2*-0.0000005775)
        except:
            pass
    
    return T

def dateiname():
    # Zeitstring fuer eindeutige Dateinamen erzeugen
    # fn = YYYYMMDD_HHMMSS
    fn = time.strftime('%Y%m%d_%H%M%S')
    return fn


def create_logfile(filename, log_kanal):
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
    for kanal in range(channel_count):
        if (log_kanal[kanal]):
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

def median_filter(raw):
    # Kombinierter Median und Mittelwertfilter
    laenge = len(raw)
    sortiert = sorted(raw)
    # Mitte des Arrays finden
    index = int(math.floor(laenge * 0.5 + 0.5))  # Python 2 rundete .5 auf, Python 3 rundet round() zur geraden Zahl
    # Bereich für Mittelwertbildung festlegen area = 1 + ln(laenge)   Basis 2.7
    area_groesse = 1 + int(round(math.log(laenge) ))
    area = sortiert[index-area_groesse:index+area_groesse+1]
    # arithmetisches Mittel
    return sum(area) / len(area)

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
    global Config_Sensor, channel_count, logger, pi, separator
    gettext.install('wlt_2_comp', localedir='/usr/share/WLANThermo/locale/')
    Config = configparser.ConfigParser(defaults, interpolation=None, strict=False, inline_comment_prefixes=(';',))

    # Wir laufen als root, auch andere müssen die Config schreiben!
    os.umask (0)

    read_config_file(Config, '/var/www/conf/WLANThermo.conf')

    Config_Sensor = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
    read_config_file(Config_Sensor, '/var/www/conf/sensor.conf')

    LOGFILE = Config.get('daemon_logging', 'log_file')
    logger = logging.getLogger('WLANthermo')
    #Define Logging Level by changing >logger.setLevel(logging.LEVEL_YOU_WANT)< available: DEBUG, INFO, WARNING, ERROR, CRITICAL
    #logger.setLevel(logging.DEBUG)
    log_level = Config.get('daemon_logging', 'level_compy')
    if log_level == 'DEBUG':
        logger.setLevel(logging.DEBUG)
    if log_level == 'INFO':
        logger.setLevel(logging.INFO)
    if log_level == 'ERROR':
        logger.setLevel(logging.ERROR)
    if log_level == 'WARNING':
        logger.setLevel(logging.WARNING)
    if log_level == 'CRITICAL':
        logger.setLevel(logging.CRITICAL)
    handler = logging.FileHandler(LOGFILE)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    logger.info('WLANThermo started')

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


    separator = Config.get('Logging','Separator')


    sys.excepthook = log_uncaught_exceptions
    # systemd beendet den Dienst mit SIGTERM, dann ebenfalls aufräumen
    signal.signal(signal.SIGTERM, handle_sigterm)
    #GPIO END

    #Hardwareversion einlesen
    version = Config.get('Hardware','version')
    enable_max31855 = Config.getboolean('Hardware', 'max31855')
    enable_maverick = Config.getboolean('ToDo', 'maverick_enabled')

    #Log Dateinamen aus der config lesen
    current_temp = Config.get('filepath','current_temp')

    # Kanalvariablen-Initialisierung
    if version == 'miniV2':
        channel_count = 12
    else:
        channel_count = 10

    sensortyp = [0 for i in range(channel_count)]
    log_kanal = [0 for i in range(channel_count)]
    temp_min = [0 for i in range(channel_count)]
    temp_max = [0 for i in range(channel_count)]
    messwiderstand = [0 for i in range(channel_count)]
    kanal_name = [0 for i in range(channel_count)]

    # read log_kanal only once because of log file format
    for kanal in range(channel_count):
        log_kanal[kanal] = Config.getboolean('Logging','CH' + str(kanal))

    pit_tempfile = Config.get('filepath','pitmaster')
    pit2_tempfile = Config.get('filepath','pitmaster2')

    #Soundoption einlesen
    sound_on = Config.getboolean('Sound','Beeper_enabled')
    sound_on_start = Config.getboolean('Sound','beeper_on_start')

    # Software-Version, wird beim build gesetzt
    build = wlanthermo.VERSION

    #Einlesen der Logging-Option
    newfile = Config.getboolean('Logging','write_new_log_on_restart')

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

    if sound_on_start:
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
    if (newfile):# neues File beim Start anlegen
        create_logfile(name, log_kanal)
    else:
        #Kein neues File anlegen
        if os.path.exists('/var/log/WLAN_Thermo/TEMPLOG.csv'):
            # pruefen, ob die Datei schon da ist zum anhaengen, auch False bei Broken Link!
            name = '/var/log/WLAN_Thermo/TEMPLOG.csv'
        else:
            create_logfile(name, log_kanal)

    new_config = configparser.ConfigParser(strict=False, inline_comment_prefixes=(';',))
    Temperatur = [None for i in range(channel_count)]

    alarm_state = [None for i in range(channel_count)]
    test_alarm = False
    config_mtime = 0
    alarm_time = 0

    try:
        while True:
            time_start = time.time()
            CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
            ram = psutil.virtual_memory()
            ram_free = ram.free // 2**20
            logger.debug('CPU: {} RAM free: {}'.format(CPU_usage, ram_free))
            alarm_irgendwo = False
            alarm_neu = False
            alarm_repeat = False
            alarme = []
            statusse = []
            pit = {}
            pit2 = {}

            if enable_maverick:
                logger.info('Reading from Maverick receiver...')
                maverick = read_maverick()
            else:
                logger.info('Maverick is disabled')
                maverick = None

            Temperatur_string = [None for i in range(channel_count)]
            Temperatur_alarm = ['er' for i in range(channel_count)]

            new_config_mtime = os.path.getmtime('/var/www/conf/WLANThermo.conf')
            if new_config_mtime != config_mtime:
                logger.info('Reading configuration again...')
                read_config_file(new_config, '/var/www/conf/WLANThermo.conf')
                config_mtime = new_config_mtime

                pit_on = new_config.getboolean('ToDo','pit_on')
                pit2_on = new_config.getboolean('ToDo','pit2_on')

                for kanal in range (channel_count):
                    try:
                        temp_max[kanal] = new_config.getfloat('temp_max','temp_max' + str(kanal))
                    except ValueError:
                        logger.error('Error reading upper limit on channel ' + str(kanal))
                        temp_max[kanal] = 200

                    try:
                        temp_min[kanal] = new_config.getfloat('temp_min','temp_min' + str(kanal))
                    except ValueError:
                        logger.error('Error reading lower limit on channel ' + str(kanal))
                        temp_min[kanal] = -20

                    try:
                        messwiderstand[kanal] = new_config.getfloat('Messen','Messwiderstand' + str(kanal))
                    except ValueError:
                        logger.error('Error reading measurement resistor on channel ' + str(kanal))
                        messwiderstand[kanal] = 47

                    sensortyp[kanal] = new_config.get('Sensoren','CH' + str(kanal))
                    kanal_name[kanal] = new_config.get('ch_name','ch_name' + str(kanal))

                #Soundoption einlesen
                sound_on = new_config.getboolean('Sound','Beeper_enabled')

                #Einlesen, ueber wieviele Messungen integriert wird
                iterations = new_config.getint('Messen','Iterations')

                #delay zwischen jeweils 8 Messungen einlesen
                delay = new_config.getfloat('Messen','Delay')

                # Allgemeine Alarmeinstellungen
                alarm_high_template = new_config.get('Alert', 'alarm_high_template')
                alarm_low_template = new_config.get('Alert', 'alarm_low_template')
                status_template = new_config.get('Alert', 'status_template')
                message_template = new_config.get('Alert', 'message_template')

                try:
                    status_interval = new_config.getint('Alert', 'status_interval')
                except ValueError:
                    logger.error('Error reading status interval from config')
                    status_interval = 0

                try:
                    alarm_interval = new_config.getint('Alert', 'alarm_interval')
                except ValueError:
                    logger.error('Error reading alarm interval from config')
                    alarm_interval = 0

                # Einlesen welche Alarmierungsart aktiv ist
                Email_alert = new_config.getboolean('Email','email_alert')
                Push_alert = new_config.getboolean('Push', 'push_on')
                Telegram_alert = new_config.getboolean('Telegram', 'telegram_alert')

                temp_unit = new_config.get('locale', 'temp_unit')

                sensorname = [Config_Sensor.get(sensortyp[kanal], 'Name') for kanal in range(channel_count)]

            if os.path.isfile('/var/www/alert.ack'):
                logger.info('alert.ack vorhanden')
                for kanal in range (channel_count):
                    if alarm_state[kanal] == 'hi':
                        logger.debug('Acknowledging temperature over upper limit on channel ' + str(kanal))
                        alarm_state[kanal] = 'hi_ack'
                    elif alarm_state[kanal] == 'lo':
                        logger.debug('Acknowledging temperature under lower limit on channel ' + str(kanal))
                        alarm_state[kanal] = 'lo_ack'
                os.unlink('/var/www/alert.ack')

            if os.path.isfile('/var/www/alert.test'):
                logger.info('alert.test exists')
                test_alarm = True
                os.unlink('/var/www/alert.test')

            logger.debug('Measuring {} channels'.format(channel_count))

            samples = [[] for i in range(8)]

            for i in range(iterations):
                for kanal in range(8):
                    if version == 'v1' or sensorname[kanal] == 'KTYPE':
                        # Nicht invertiert messen
                        samples[kanal].append(get_channel_mcp(kanal))
                    else:
                        # Spannungsteiler ist nach v1 anders herum aufgebaut
                        samples[kanal].append(4095 - get_channel_mcp(kanal))

            for kanal in range(channel_count):
                if kanal <= 7:
                    median_value = median_filter(samples[kanal])
                    if (median_value > 15) and (median_value < 4080):
                        if (sensorname[kanal] != 'KTYPE'):
                                Rtheta = messwiderstand[kanal]*((4096.0/median_value) - 1)
                                try:
                                    Temperatur[kanal] = round(temperatur_sensor(Rtheta, sensortyp[kanal]), 2)
                                except TypeError:
                                    Temperatur[kanal] = None
                        else:
                            # AD595 = 10mV/°C
                            Temperatur[kanal] = median_value * 330 / 4096
                    else:
                        Temperatur[kanal] = None
                    variance = statistics.pvariance(samples[kanal])
                    if variance > 4:
                        warnung = 'Channel:{kanal} variance: {variance} in {iterations}, median @ {median_value}!'.format(
                            kanal=kanal,
                            variance=variance,
                            iterations=iterations,
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
                    if enable_max31855:
                        Temperatur[kanal] = get_channel_max31855(kanal - 10)
                        logger.debug('Channel {}, MAX31855 {}, temperature {}'.format(kanal, kanal - 10, Temperatur[kanal]))
                    else:
                        Temperatur[kanal] = None
                        logger.debug('Channel {}, disabled'.format(kanal))
                else:
                    logger.error('Channel {} checked without a reason!'.format(kanal))
                    Temperatur[kanal] = None

                alarm_values = dict()
                if temp_unit == 'celsius':
                    alarm_values['temp_unit'] = '°C'
                    alarm_values['temp_unit_long'] = _('degrees Celsius')
                elif temp_unit == 'fahrenheit':
                    if Temperatur[kanal] is not None:
                        Temperatur[kanal] = Temperatur[kanal] * 1.8 + 32
                    alarm_values['temp_unit'] = '°F'
                    alarm_values['temp_unit_long'] = _('degrees Fahrenheit')
                alarm_values['kanal'] = kanal
                alarm_values['name'] = kanal_name[kanal]
                # Python 2 gab Floats mit 12 Stellen aus, Python 3 mit allen (74.21000000000001)
                alarm_values['temperatur'] = round(Temperatur[kanal], 2) if Temperatur[kanal] is not None else None
                alarm_values['temp_max'] = temp_max[kanal]
                alarm_values['temp_min'] = temp_min[kanal]
                alarm_values['lf'] = '\n'

                if Temperatur[kanal] is not None:    
                    Temperatur_string[kanal] = "%.2f" % Temperatur[kanal]
                    Temperatur_alarm[kanal] = 'ok'

                    if Temperatur[kanal] >= temp_max[kanal]:
                        # Temperatur über Grenzwert
                        if alarm_state[kanal] == 'hi':
                            # Nicht quittierter Alarm
                            alarm_irgendwo = True
                        elif alarm_state[kanal] == 'hi_ack':
                            # Alarm bereits quittiert
                            pass
                        else:
                            # Neuer Alarm
                            alarm_irgendwo = True
                            alarm_neu = True
                            alarm_state[kanal] = 'hi'
                        alarme.append(safe_format(alarm_high_template, alarm_values))
                        Temperatur_alarm[kanal] = 'hi'
                    elif Temperatur[kanal] <= temp_min[kanal]:
                        # Temperatur unter Grenzwert
                        if alarm_state[kanal] == 'lo':
                            # Nicht quittierter Alarm
                            alarm_irgendwo = True
                        elif alarm_state[kanal] == 'lo_ack':
                            # Alarm bereits quittiert
                            pass
                        else:
                            # Neuer Alarm
                            alarm_irgendwo = True
                            alarm_neu = True
                            alarm_state[kanal] = 'lo'
                        alarme.append(safe_format(alarm_low_template, alarm_values))
                        Temperatur_alarm[kanal] = 'lo'
                    else:
                        # Temperatur innerhalb der Grenzwerte
                        statusse.append(safe_format(status_template, alarm_values))
                        alarm_state[kanal] = 'ok'

            if pit_on:
                try:
                    with codecs.open(pit_tempfile, 'r', 'utf_8') as pitfile:
                        pit_values = pitfile.readline().split(';')
                        pit['new'] = pit_values[3].rstrip('%')
                        pit['set'] = pit_values[1]
                except (OSError, IndexError):
                    # IndexError: Datei leer oder gerade unvollständig geschrieben
                    # Wenn keine aktuellen Werte verfügbar sind, leere Werte schreiben
                    pit = None
            else:
                    pit = None

            if pit2_on:
                try:
                    with codecs.open(pit2_tempfile, 'r', 'utf_8') as pit2file:
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

            alarm_message = safe_format(message_template, message_values)


            # Beeper bei jedem unquittiertem Alarm
            if alarm_irgendwo:
                if sound_on:
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
                if alarm_interval > 0 and alarm_time + alarm_interval < time.time():
                    # Alarm erneut senden
                    alarm_repeat = True
                    alarm_time = time.time()

            if status_interval > 0 and alarm_time + status_interval < time.time():
                # Periodisch den Status senden, wenn gewünscht
                send_status = True
            else:
                send_status = False

            # Nachrichten senden
            if alarm_neu or test_alarm or alarm_repeat or send_status:
                alarm_time = time.time()

                if alarm_neu:
                    logger.debug('new alert, sending messages')
                if test_alarm:
                    logger.debug('test alert, sending messages')
                    test_alarm = False
                    alarm_message = _('test message\n') + alarm_message
                if alarm_repeat:
                    logger.info('repeated alert, sending messages')
                if send_status:
                    logger.info('sending status')

                if Email_alert:
                    # Wenn konfiguriert, Email schicken
                    Email_server  = new_config.get('Email','server')
                    Email_auth = new_config.getboolean('Email','auth')
                    Email_user = new_config.get('Email','username')
                    Email_password = new_config.get('Email','password')
                    Email_from = new_config.get('Email','email_from')
                    Email_to = new_config.get('Email','email_to')
                    Email_subject = new_config.get('Email','email_subject')
                    Email_STARTTLS = new_config.getboolean ('Email','starttls')

                    alarm_email(
                        Email_server,
                        Email_auth,
                        Email_user,
                        Email_password,
                        Email_STARTTLS,
                        Email_from,
                        Email_to,
                        Email_subject,
                        alarm_message)

                if Telegram_alert:
                    Telegram_URL = 'https://api.telegram.org/bot{token}/sendMessage'
                    Telegram_chat_id = new_config.get('Telegram', 'telegram_chat_id')
                    Telegram_token = new_config.get('Telegram', 'telegram_token')

                    if not alarm_irgendwo:
                        disable_notification = 'true'
                    else:
                        disable_notification = 'false'

                    body = urllib.parse.urlencode({
                        'text': alarm_message,
                        'chat_id': Telegram_chat_id,
                        'disable_notification': disable_notification})
                    url = Telegram_URL.format(token=Telegram_token)

                    try: 
                        logger.debug('Telegram POST request, URL: {}\nbody: {}'.format(url, body))
                        response = urllib.request.urlopen(url, body.encode('utf-8'), timeout=NETWORK_TIMEOUT)

                        logger.info('Telegram HTTP return code: ' + str(response.getcode()))
                        logger.debug('Telegram URL: ' + response.geturl())
                        logger.debug('Telegram result: ' + response.read(500).decode('utf-8', 'replace'))

                    except urllib.error.HTTPError as e:
                        logger.error('Telegram HTTP error: ' + str(e.code) + ' - ' + e.read(500).decode('utf-8', 'replace'))
                    except urllib.error.URLError as e:
                        logger.error('Telegram URLError: ' + str(e.reason))
                    except OSError as e:
                        # z.B. Zeitüberschreitung beim Lesen der Antwort
                        logger.error('Telegram error: ' + str(e))

                if Push_alert:
                    # Wenn konfiguriert, Alarm per Pushnachricht schicken
                    Push_URL = new_config.get('Push', 'push_url')
                    Push_Body = new_config.get('Push', 'push_body')

                    try:
                        url = Push_URL.format(messagetext=urllib.parse.quote(alarm_message.encode('utf-8')).replace('\n', '<br/>'))
                        body = Push_Body.format(messagetext=urllib.parse.quote(alarm_message.encode('utf-8')).replace('\n', '<br/>'))
                    except KeyError as key:
                        logger.error('Key "{}" is undefined!'.format(key))
                    else:
                        try: 
                            if Push_Body == '':
                                logger.debug('push GET request, URL: ' + url)
                                response = urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT)
                            else:
                                logger.debug('push POST request, URL: ' + url + '\nbody: ' + body)
                                response = urllib.request.urlopen(url, body.encode('utf-8'), timeout=NETWORK_TIMEOUT)

                            logger.info('push HTTP return code: ' + str(response.getcode()))
                            logger.debug('push URL: ' + response.geturl())
                            logger.debug('push result: ' + response.read(500).decode('utf-8', 'replace'))

                        except urllib.error.HTTPError as e:
                            logger.error('Push HTTP error: ' + str(e.code) + ' - ' + e.read(500).decode('utf-8', 'replace'))
                        except urllib.error.URLError as e:
                            logger.error('Push URLError: ' + str(e.reason))
                        except ValueError as e:
                            logger.error('Push ValueError: ' + str(e))
                        except OSError as e:
                            # z.B. Zeitüberschreitung beim Lesen der Antwort
                            logger.error('Push error: ' + str(e))

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
                lcsv.append(Temperatur_alarm[kanal])
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
