#!/usr/bin/python
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

from __future__ import division
import sys
import ConfigParser
import os
import time
import math
import string
import logging
import urllib
import urllib2
import psutil
import signal
import traceback
import gettext
import codecs
import subprocess
from bitstring import BitArray
import pigpio
from struct import pack, unpack
import json
import statistics
import platform
import requests

gettext.install('wlt_2_comp', localedir='/usr/share/WLANThermo/locale/', unicode=True)

# Konfigurationsdatei einlesen
defaults = {'pit_control_out':'True'}
Config = ConfigParser.ConfigParser(defaults)

# Wir laufen als root, auch andere müssen die Config schreiben!
os.umask (0)

while True:
    try:
        Config.readfp(codecs.open('/var/www/conf/WLANThermo.conf', 'r', 'utf_8'))
    except IndexError:
        time.sleep(1)
        continue
    break


Config_Sensor = ConfigParser.ConfigParser()
while True:
    try:
        Config_Sensor.readfp(codecs.open('/var/www/conf/sensor.conf', 'r', 'utf_8'))
    except IndexError:
        time.sleep(1)
        continue
    break
    
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

logger.info(u'WLANThermo started')

#ueberpruefe ob der Dienst schon laeuft
pid = str(os.getpid())
pidfilename = '/var/run/' + os.path.basename(__file__).split('.')[0]+'.pid'

def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

if os.access(pidfilename, os.F_OK):
    pidfile = open(pidfilename, "r")
    pidfile.seek(0)
    old_pid = int(pidfile.readline())
    if check_pid(old_pid):
        print(_(u'%s already exists, Process is running, exiting') % pidfilename)
        logger.error(u'%s already exists, Process is running, exiting' % pidfilename)
        sys.exit()
    else:
        logger.info(u'%s already exists, Process is NOT running, resuming operation' % pidfilename)
        pidfile.seek(0)
        open(pidfilename, 'w').write(pid)
    
else:
    logger.debug(u"%s written" % pidfilename)
    open(pidfilename, 'w').write(pid)


separator = Config.get('Logging','Separator')

# Funktionsdefinition

##
## Formatierung von Strings auch wenn ein key nicht existiert.
##
def safe_format(template, args):
    message = ''
    for i in xrange(100):
        try:
            message = template.format(**args)
            break
        except KeyError as e:
            key_name = str(e).strip('\'')
            logger.error(u'Key "{key_name}" not found in template!'.format(key_name=key_name))
            template = template.replace('{' + key_name + '}', '!!' + key_name + '!!')
    return message

def alarm_email(SERVER,USER,PASSWORT,STARTTLS,FROM,TO,SUBJECT,MESSAGE):
    logger.info(u'Send mail!')
    
    from smtplib import SMTP 
    from smtplib import SMTPException 
    from email.mime.text import MIMEText as text
    if STARTTLS:
        port=587
    else:
        port=25
    try:
        s = SMTP(SERVER,port)
        if STARTTLS:
            s.starttls()
        
        s.login(USER,PASSWORT)
        

        m = text(MESSAGE, 'plain', 'UTF-8')

        m['Subject'] = SUBJECT
        m['From'] = FROM
        m['To'] = TO


        s.sendmail(FROM,TO, m.as_string())
        s.quit()
        logger.debug(u'Alert Email has been sent!')
    except SMTPException as error:
        sendefehler = u'Error: unable to send email: {err}'.format(err=error)
        logger.error(sendefehler)
    except:
        #TODO err undefined!
        sendefehler = u'Error: unable to resolve host (no internet connection?) :  {err}'
        logger.error(sendefehler)
        
                   
def init_softspi_mcp():
    try:
        retval = pi.bb_spi_open(CS, MISO, MOSI, SCLK, 20000, 0)
    except pigpio.error as e:
        if str(e) == "'GPIO already in use'":
            retval = 0
        else:
            raise


def get_channel_mcp(channel):
    if channel > 7:
        raise ValueError()
    command = pack('>Hx', (0x18 + channel) << 6)
    return unpack('>xH', pi.bb_spi_xfer(CS, command)[1])[0] & 0x0FFF


def get_channel_max31855(channel):
    if channel > 1:
        raise ValueError()
    data = BitArray(pi.bb_spi_xfer(8 - channel, '\00\00')[1])
    if data[15]:
        return None
    else:
        return data[0:14].int / 4.0


def init_softspi_max31855_1():
    try:
        retval = pi.bb_spi_open(CS_MAX1, MISO, MOSI, SCLK, 250000, 0)
    except pigpio.error as e:
        if str(e) == "'GPIO already in use'":
            retval = 0
        else:
            raise
        
    return retval == 0


def init_softspi_max31855_2():
    try:
        retval = pi.bb_spi_open(CS_MAX2, MISO, MOSI, SCLK, 250000, 0)
    except pigpio.error as e:
        if str(e) == "'GPIO already in use'":
            retval = 0
        else:
            raise
            
    return retval == 0


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
    except:
        pass
    
    # Symlink TEMPLOG.csv auf die gerade benutzte eindeutige Log-Datei legen.
    os.symlink(filename, '/var/log/WLAN_Thermo/TEMPLOG.csv')
    
    kopfzeile = []
    kopfzeile.append(_(u'Date_Time'))
    for kanal in xrange(channel_count):
        if (log_kanal[kanal]):
            kopfzeile.append('Kanal ' + str(kanal))
            
    kopfzeile.append(_(u'Controller output value'))
    kopfzeile.append(_(u'Controller set value'))
    kopfzeile.append(_(u'Controller 2 output value'))
    kopfzeile.append(_(u'Controller 2 set value'))
    
    while True:
        try:
            fw = codecs.open(filename, 'w', 'utf_8') #Datei anlegen
            fw.write(separator.join(kopfzeile) + '\n') # Kopfzeile der CSV-Datei schreiben
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
        except IndexError:
            time.sleep(1)
            continue
        break

def median_filter(raw):
    # Kombinierter Median und Mittelwertfilter
    laenge = len(raw)
    sortiert = sorted(raw)
    # Mitte des Arrays finden
    index = int(round(laenge * 0.5))
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
        logger.error(u'Maverick file is no valid JSON')
        return None
    except IOError:
        logger.info(u'Maverick file could not be read')
        return None

    age = time.time() - values['time']
    if age > 30:
        logger.debug('Maverick values too old, {} sec'.format(age))
        return None

    return values
    
    
sys.excepthook = log_uncaught_exceptions

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
#GPIO END

#Hardwareversion einlesen
version = Config.get('Hardware','version')
enable_max31855 = Config.getboolean('Hardware', 'max31855')
enable_maverick = Config.getboolean('ToDo', 'maverick_enabled')

#Log Dateinamen aus der config lesen
current_temp = Config.get('filepath','current_temp')

# Kanalvariablen-Initialisierung
if version == u'miniV2':
    channel_count = 12
else:
    channel_count = 10

sensortyp = [0 for i in xrange(channel_count)]
log_kanal = [0 for i in xrange(channel_count)]
temp_min = [0 for i in xrange(channel_count)]
temp_max = [0 for i in xrange(channel_count)]
messwiderstand = [0 for i in xrange(channel_count)]
kanal_name = [0 for i in xrange(channel_count)]

# read log_kanal only once because of log file format
for kanal in xrange(channel_count):
    log_kanal[kanal] = Config.getboolean('Logging','CH' + str(kanal))

log_pitmaster =  Config.getboolean('Logging','pit_control_out')

pit_tempfile = Config.get('filepath','pitmaster')
pit2_tempfile = Config.get('filepath','pitmaster2')

#Soundoption einlesen
sound_on = Config.getboolean('Sound','Beeper_enabled')
sound_on_start = Config.getboolean('Sound','beeper_on_start')

# Software-Version, wird beim build gesetzt
build = 'XXX_VERSION_XXX'

#Einlesen der Logging-Option
newfile = Config.getboolean('Logging','write_new_log_on_restart')

pi = pigpio.pi()
init_softspi_mcp()
init_softspi_max31855_1()
init_softspi_max31855_2()
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

new_config = ConfigParser.SafeConfigParser()
Temperatur = [None for i in xrange(channel_count)]

alarm_state = [None for i in xrange(channel_count)]
test_alarm = False
config_mtime = 0
alarm_time = 0

try:
    while True:
        time_start = time.time()
        CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
        ram = psutil.virtual_memory()
        ram_free = ram.free // 2**20
        logger.debug(u'CPU: {} RAM free: {}'.format(CPU_usage, ram_free))
        alarm_irgendwo = False
        alarm_neu = False
        alarm_repeat = False
        alarme = []
        statusse = []
        pit = {}
        pit2 = {}
        
        if enable_maverick:
            logger.info(u'Reading from Maverick receiver...')
            maverick = read_maverick()
        else:
            logger.info(u'Maverick is disabled')
            maverick = None
        
        Temperatur_string = [None for i in xrange(channel_count)]
        Temperatur_alarm = ['er' for i in xrange(channel_count)]

        new_config_mtime = os.path.getmtime('/var/www/conf/WLANThermo.conf')
        if new_config_mtime != config_mtime:
            logger.info(u'Reading configuration again...')
            while True:
                try:
                    new_config.readfp(codecs.open('/var/www/conf/WLANThermo.conf', 'r', 'utf_8'))
                except IndexError:
                    time.sleep(1)
                    continue
                break
            config_mtime = new_config_mtime
        
            pit_on = new_config.getboolean('ToDo','pit_on')
            pit2_on = new_config.getboolean('ToDo','pit2_on')

            for kanal in xrange (channel_count):
                try:
                    temp_max[kanal] = new_config.getfloat('temp_max','temp_max' + str(kanal))
                except ValueError:
                    logger.error(u'Error reading upper limit on channel ' + str(kanal))
                    temp_max[kanal] = 200

                try:
                    temp_min[kanal] = new_config.getfloat('temp_min','temp_min' + str(kanal))
                except ValueError:
                    logger.error(u'Error reading lower limit on channel ' + str(kanal))
                    temp_max[kanal] = -20

                try:
                    messwiderstand[kanal] = new_config.getfloat('Messen','Messwiderstand' + str(kanal))
                except ValueError:
                    logger.error(u'Error reading measurement resistor on channel ' + str(kanal))
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
                logger.error(u'Error reading status interval from config')
                status_interval = 0

            try:
                alarm_interval = new_config.getint('Alert', 'alarm_interval')
            except ValueError:
                logger.error(u'Error reading alarm interval from config')
                alarm_interval = 0

            # Einlesen welche Alarmierungsart aktiv ist
            Email_alert = new_config.getboolean('Email','email_alert')
            Push_alert = new_config.getboolean('Push', 'push_on')
            Telegram_alert = new_config.getboolean('Telegram', 'telegram_alert')
            App_alert = new_config.getboolean('App', 'app_alert')

            temp_unit = new_config.get('locale', 'temp_unit')

            sensorname = [Config_Sensor.get(sensortyp[kanal], 'Name') for kanal in xrange(channel_count)]
        
        if os.path.isfile('/var/www/alert.ack'):
            logger.info('alert.ack vorhanden')
            for kanal in range (channel_count):
                if alarm_state[kanal] == 'hi':
                    logger.debug(u'Acknowledging temperature over upper limit on channel ' + str(kanal))
                    alarm_state[kanal] = 'hi_ack'
                elif alarm_state[kanal] == 'lo':
                    logger.debug(u'Acknowledging temperature under lower limit on channel ' + str(kanal))
                    alarm_state[kanal] = 'lo_ack'
            os.unlink('/var/www/alert.ack')
        
        if os.path.isfile('/var/www/alert.test'):
            logger.info(u'alert.test exists')
            test_alarm = True
            os.unlink('/var/www/alert.test')
        
        logger.debug(u'Measuring {} channels'.format(channel_count))

        samples = [[] for i in xrange(8)]

        for i in xrange(iterations):
            for kanal in xrange(8):
                if version == 'v1' or sensorname[kanal] == 'KTYPE':
                    # Nicht invertiert messen
                    samples[kanal].append(get_channel_mcp(kanal))
                else:
                    # Spannungsteiler ist nach v1 anders herum aufgebaut
                    samples[kanal].append(4095 - get_channel_mcp(kanal))

        for kanal in xrange(channel_count):
            Temp = 0.0
            WerteArray = []
            if kanal <= 7:
                median_value = median_filter(samples[kanal])
                if (median_value > 15) and (median_value < 4080):
                    if (sensorname[kanal] != 'KTYPE'):
                            Rtheta = messwiderstand[kanal]*((4096.0/median_value) - 1)
                            try:
                                Temperatur[kanal] = round(temperatur_sensor(Rtheta, sensortyp[kanal]), 2)
                            except exceptions.TypeError:
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
                logger.debug(u'Channel {}, MCP3128 {}, temperature {}'.format(kanal, kanal, Temperatur[kanal]))
            elif kanal <= 9:
                if maverick is None:
                    Temperatur[kanal] = None
                    logger.debug(u'Channel {}, disabled or not available'.format(kanal))
                else:
                    logger.debug(u'Channel {}, Maverick {}, temperature {}'.format(kanal, kanal - 7, Temperatur[kanal]))
                    maverick_value = maverick['temperature_' + str(kanal - 7)]
                    if maverick_value == '':
                        Temperatur[kanal] = None
                    else:
                        Temperatur[kanal] = maverick_value
            elif version == u'miniV2':
                if enable_max31855:
                    Temperatur[kanal] = get_channel_max31855(kanal - 10)
                    logger.debug(u'Channel {}, MAX31855 {}, temperature {}'.format(kanal, kanal - 10, Temperatur[kanal]))
                else:
                    Temperatur[kanal] = None
                    logger.debug(u'Channel {}, disabled'.format(kanal))
            else:
                logger.error(u'Channel {} checked without a reason!'.format(kanal))
                Temperatur[kanal] = None

            alarm_values = dict()
            if temp_unit == 'celsius':
                alarm_values['temp_unit'] = '°C'
                alarm_values['temp_unit_long'] = _(u'degrees Celsius')
            elif temp_unit == 'fahrenheit':
                if Temperatur[kanal] is not None:
                    Temperatur[kanal] = Temperatur[kanal] * 1.8 + 32
                alarm_values['temp_unit'] = '°F'
                alarm_values['temp_unit_long'] = _(u'degrees Fahrenheit')
            alarm_values['kanal'] = kanal
            alarm_values['name'] = kanal_name[kanal]
            alarm_values['temperatur'] = Temperatur[kanal]
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
            except IOError:
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
            except IOError:
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
                logger.debug(u'new alert, sending messages')
            if test_alarm:
                logger.debug(u'test alert, sending messages')
                test_alarm = False
                alarm_message = _(u'test message\n') + alarm_message
            if alarm_repeat:
                logger.info(u'repeated alert, sending messages')
            if send_status:
                logger.info(u'sending status')
                
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

                body = urllib.urlencode({
                    'text': alarm_message.encode('utf-8'),
                    'chat_id': Telegram_chat_id,
                    'disable_notification': disable_notification})
                url = Telegram_URL.format(token=Telegram_token)

                try: 
                    logger.debug(u'Telegram POST request, URL: {}\nbody: {}'.format(url, body))
                    response = urllib2.urlopen(url, body)
                    
                    logger.info(u'Telegram HTTP return code: ' + str(response.getcode()))
                    logger.debug(u'Telegram URL: ' + response.geturl())
                    logger.debug(u'Telegram result: ' + response.read(500))

                except urllib2.HTTPError, e:
                    logger.error(u'Telegram HTTP error: ' + str(e.code) + u' - ' + e.read(500))
                except urllib2.URLError, e:
                    logger.error(u'Telegram URLError: ' + str(e.reason))  

 
            if App_alert:
                logger.debug(u'App_alert')
                api_key='key=AAAA89_rQYw:APA91bEknuZrwPUNveElqW1CgFcICLOh9sIjtume6HPeExxtnJoQExiFIvqU84Xk-MsxI2Ig6w8VvaAsm43QHrowruP5EOvz0IO-HG9PB3mcoiumT2k6CcVryLiL4K450Jx1QKhumkd0'
                app_id = ["","",""]
                app_id[0] = new_config.get('App','app_inst_id')
                app_id[1] = new_config.get('App','app_inst_id2')
                app_id[2] = new_config.get('App','app_inst_id3')
                app_device = ["","",""]
                app_device[0] = new_config.get('App','app_device')
                app_device[1] = new_config.get('App','app_device2')
                app_device[2] = new_config.get('App','app_device3')
                alarm_message = str(alarm_message.encode('utf-8'))

                url = 'https://fcm.googleapis.com/fcm/send'
                myheaders = {'Content-Type': 'application/json', 'Authorization': api_key}

                i=0
                while i < 3:
                    
                    if app_id[i] != "" and app_device[i]=="0" :
                        payload = {'data': {'Alarm':alarm_message}, "android":{"priority":"high"}, 'to':app_id[i]}
                        try:
                            logger.debug(u'App_alert try sending:' )
                            logger.debug(u'App_id:' + app_id[i])
                            data=json.dumps(payload)
                            results = requests.post(url, data, headers=myheaders)
                            print(results.text)
                            logger.debug(u'AppAlert result: ' + str(results.text))
                        except requests.exceptions.RequestException as e:
                            print(e)
                            logger.debug(u'App_alert error')
                    i=i+1
                
                
            if Push_alert:
                # Wenn konfiguriert, Alarm per Pushnachricht schicken
                Push_URL = new_config.get('Push', 'push_url')
                Push_Body = new_config.get('Push', 'push_body')
                
                try:
                    url = Push_URL.format(messagetext=urllib.quote(alarm_message.encode('utf-8')).replace('\n', '<br/>'))
                    body = Push_Body.format(messagetext=urllib.quote(alarm_message.encode('utf-8')).replace('\n', '<br/>'))
                except KeyError, key:
                    logger.error(u'Key "{}" is undefined!'.format(key))
                else:
                    try: 
                        if Push_Body == '':
                            logger.debug(u'push GET request, URL: ' + url)
                            response = urllib2.urlopen(url)
                        else:
                            logger.debug(u'push POST request, URL: ' + url + u'\nbody: ' + body)
                            response = urllib2.urlopen(url, body)
                        
                        logger.info(u'push HTTP return code: ' + str(response.getcode()))
                        logger.debug(u'push URL: ' + response.geturl())
                        logger.debug(u'push result: ' + response.read(500))
    
                    except urllib2.HTTPError, e:
                        logger.error(u'Push HTTP error: ' + str(e.code) + u' - ' + e.read(500))
                    except urllib2.URLError, e:
                        logger.error(u'Push URLError: ' + str(e.reason))
                    except ValueError, e:
                        logger.error(u'Push ValueError: ' + str(e))
        
        # Log datei erzeugen
        lcsv = []
        Uhrzeit_lang = time.strftime('%d.%m.%y %H:%M:%S')
        logdatei = os.readlink('/var/log/WLAN_Thermo/TEMPLOG.csv')
        logdatei = logdatei[21:-4]
        lcsv.append(Uhrzeit_lang)
        t = ""
        for kanal in xrange(channel_count):
            if Temperatur_string[kanal] is None:
                lcsv.append('')
            else:
                lcsv.append(str(Temperatur_string[kanal]))
        for kanal in xrange(channel_count):
            # 8 Felder mit allen Alarmzuständen
            lcsv.append(Temperatur_alarm[kanal])
        lcsv.append(build)
        lcsv.append(logdatei)
        
        
        while True:
            try:
                fcsv = codecs.open(current_temp  + '_tmp', 'w', 'utf_8')
                fcsv.write(';'.join(lcsv))
                fcsv.flush()
                os.fsync(fcsv.fileno())
                fcsv.close()
                os.rename(current_temp + '_tmp', current_temp)
            except IndexError:
                time.sleep(1)
                logger.debug(u'Error: Could not write to file {file}!'.format(file=current_temp))
                continue
            break
            
        #Messzyklus protokollieren und nur die Kanaele loggen, die in der Konfigurationsdatei angegeben sind
        log_line = []
        log_line.append(Uhrzeit_lang)
        
        for kanal in xrange(channel_count):
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
                
        while True:
            try:
                # Generierung des Logfiles
                logfile = codecs.open(name, 'a', 'utf_8')
                logfile.write(separator.join(log_line) + '\n')
                logfile.flush()
                os.fsync(logfile.fileno())
                logfile.close()
            except IndexError:
                time.sleep(1)
                continue
            break
        # Werte loggen
        logger.debug(separator.join(log_line))
        
        time_remaining = time_start + delay - time.time()
        if time_remaining < 0:
            logger.warning(u'measuring loop running longer than {delay}s, remaining time {time_remaining}s'.format(delay=delay, time_remaining=time_remaining))
        else:
            logger.debug(u'measuring loop remaining time {time_remaining}s of {delay}s'.format(delay=delay, time_remaining=time_remaining))
            time.sleep(time_remaining)

except KeyboardInterrupt:
    logger.info(u'WLANThermo stopped!')
    pi.bb_spi_close(25)
    pi.bb_spi_close(8)
    pi.bb_spi_close(7)
    logging.shutdown()
    os.unlink(pidfilename)
    