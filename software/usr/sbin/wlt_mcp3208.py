#!/usr/bin/python3
# coding=utf-8

# Copyright (c) 2013, 2014, 2015 Armin Thinnes
# Copyright (c) 2015, 2016 Björn Schrader
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
import ConfigParser
import os
import time
import math
import string
import logging
import RPi.GPIO as GPIO
import urllib
import urllib2
import psutil
import signal
import traceback
import gettext
import codecs
import subprocess

gettext.install('wlt_2_comp', localedir='/usr/share/WLANThermo/locale/', unicode=True)

class WltConfig:
    def __init__(self):
        defaults = {'pit_control_out': 'True'}

        Config = ConfigParser.ConfigParser(defaults)

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

        # Hardwareversion einlesen
        version = Config.get('Hardware', 'version')

        # Log Dateinamen aus der config lesen
        current_temp = Config.get('filepath', 'current_temp')

    # Kanalvariablen-Initialisierung
    sensortyp = [0 for i in xrange(8)]
    log_kanal = [0 for i in xrange(8)]
    temp_min = [0 for i in xrange(8)]
    temp_max = [0 for i in xrange(8)]
    messwiderstand = [0 for i in xrange(8)]
    kanal_name = [0 for i in xrange(8)]

    # read log_kanal only once because of log file format
    for kanal in xrange(8):
        log_kanal[kanal] = Config.getboolean('Logging', 'CH' + str(kanal))

    log_pitmaster = Config.getboolean('Logging', 'pit_control_out')

    pit_tempfile = Config.get('filepath', 'pitmaster')

    # Soundoption einlesen
    sound_on = Config.getboolean('Sound', 'Beeper_enabled')
    sound_on_start = Config.getboolean('Sound', 'beeper_on_start')

    # Einlesen der Software-Version
    command = 'cat /var/www/header.php | grep \'] = "V\' | cut -c31-38'

    build = os.popen(command).read()

    # Einlesen der Logging-Option
    newfile = Config.getboolean('Logging', 'write_new_log_on_restart')

    Temperatur_string = ['999.9', '999.9', '999.9', '999.9', '999.9', '999.9', '999.9', '999.9']
    Temperatur_alarm = ['er', 'er', 'er', 'er', 'er', 'er', 'er', 'er']
    Displaytemp = ['999.9', '999.9', '999.9', '999.9', '999.9', '999.9', '999.9', '999.9']

    new_config_mtime = os.path.getmtime('/var/www/conf/WLANThermo.conf')
    if new_config_mtime > config_mtime:
        logger.debug(_(u'reading configuration again...'))
        while True:
            try:
                new_config.readfp(codecs.open('/var/www/conf/WLANThermo.conf', 'r', 'utf_8'))
            except IndexError:
                time.sleep(1)
                continue
            break
        config_mtime = new_config_mtime

    pit_on = new_config.getboolean('ToDo', 'pit_on')

    for kanal in xrange(8):
        try:
            temp_max[kanal] = new_config.getfloat('temp_max', 'temp_max' + str(kanal))
        except ValueError:
            logger.error(_(u'Error reading upper limit on channel ') + str(kanal))
            temp_max[kanal] = 200

        try:
            temp_min[kanal] = new_config.getfloat('temp_min', 'temp_min' + str(kanal))
        except ValueError:
            logger.error(_(u'Error reading lower limit on channel ') + str(kanal))
            temp_max[kanal] = -20

        try:
            messwiderstand[kanal] = new_config.getfloat('Messen', 'Messwiderstand' + str(kanal))
        except ValueError:
            logger.error(_(u'Error reading measurement resistor on channel ') + str(kanal))
            messwiderstand[kanal] = 47

        sensortyp[kanal] = new_config.get('Sensoren', 'CH' + str(kanal))
        kanal_name[kanal] = new_config.get('ch_name', 'ch_name' + str(kanal))

    # Soundoption einlesen
    sound_on = new_config.getboolean('Sound', 'Beeper_enabled')

    # Einlesen, ueber wieviele Messungen integriert wird
    iterations = new_config.getint('Messen', 'Iterations')

    # delay zwischen jeweils 8 Messungen einlesen
    delay = new_config.getfloat('Messen', 'Delay')

    # Allgemeine Alarmeinstellungen
    alarm_high_template = new_config.get('Alert', 'alarm_high_template')
    alarm_low_template = new_config.get('Alert', 'alarm_low_template')
    status_template = new_config.get('Alert', 'status_template')
    message_template = new_config.get('Alert', 'message_template')

    try:
        status_interval = new_config.getint('Alert', 'status_interval')
    except ValueError:
        logger.error(_(u'Error reading status interval from config'))
        status_interval = 0

    try:
        alarm_interval = new_config.getint('Alert', 'alarm_interval')
    except ValueError:
        logger.error(_(u'Error reading alarm interval from config'))
        alarm_interval = 0

    # Einlesen welche Alarmierungsart aktiv ist
    Email_alert = new_config.getboolean('Email', 'email_alert')
    WhatsApp_alert = new_config.getboolean('WhatsApp', 'whatsapp_alert')
    Push_alert = new_config.getboolean('Push', 'push_on')
    Telegram_alert = new_config.getboolean('Telegram', 'telegram_alert')
    App_alert = new_config.getboolean('App', 'app_alert')

    temp_unit = new_config.get('locale', 'temp_unit')

    new_config = ConfigParser.SafeConfigParser()
    Temperatur = [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10]

    alarm_state = [None, None, None, None, None, None, None, None]
    test_alarm = False
    config_mtime = 0
    alarm_time = 0

class WltMcp3208:
    def __init__(self):
        # GPIO START
        self.SCLK = 18  # Serial-Clock
        self.MOSI = 24  # Master-Out-Slave-In
        self.MISO = 23  # Master-In-Slave-Out
        self.CS = 25  # Chip-Select

    def readAnalogData(adcChannel, SCLKPin, MOSIPin, MISOPin, CSPin):
        # Pegel vorbereiten
        GPIO.output(CSPin, HIGH)
        GPIO.output(CSPin, LOW)
        GPIO.output(SCLKPin, LOW)

        sendcmd = adcChannel
        sendcmd |= 0b00011000  # Entspricht 0x18 (1:Startbit, 1:Single/ended)

        # Senden der Bitkombination (Es finden nur 5 Bits Beruecksichtigung)
        for i in xrange(5):
            if (sendcmd & 0x10):  # (Bit an Position 4 pruefen. Zaehlung beginnt bei 0)
                GPIO.output(MOSIPin, HIGH)
            else:
                GPIO.output(MOSIPin, LOW)
            # Negative Flanke des Clocksignals generieren
            GPIO.output(SCLKPin, HIGH)
            GPIO.output(SCLKPin, LOW)
            sendcmd <<= 1  # Bitfolge eine Position nach links schieben
        time.sleep(0.0001)  # 0.00001 erzeugte bei mir Raspi 2 Pest 90us

        # Empfangen der Daten des ADC
        adcvalue = 0  # Ruecksetzen des gelesenen Wertes

        for i in xrange(13):
            GPIO.output(SCLKPin, HIGH)
            GPIO.output(SCLKPin, LOW)
            # print GPIO.input(MISOPin)
            adcvalue <<= 1  # 1 Postition nach links schieben
            if (GPIO.input(MISOPin)):
                adcvalue |= 0x01
        # time.sleep(0.1)
        GPIO.output(CSPin, HIGH)  # Ausleseaktion beenden
        return adcvalue

    def temperatur_sensor(Rt, typ, unit):  # Ermittelt die Temperatur
        name = Config_Sensor.get(typ, 'name')

        if not name in ('PT100', 'PT1000'):
            a = Config_Sensor.getfloat(typ, 'a')
            b = Config_Sensor.getfloat(typ, 'b')
            c = Config_Sensor.getfloat(typ, 'c')
            Rn = Config_Sensor.getfloat(typ, 'Rn')

            try:
                v = math.log(Rt / Rn)
                T = (1 / (a + b * v + c * v * v)) - 273
            except:  # bei unsinnigen Werten (z.B. ein- ausstecken des Sensors im Betrieb) Wert 999.9
                T = 999.9
        else:
            Rkomp = Config_Sensor.getfloat(typ, 'Rkomp')
            Rt = Rt - Rkomp
            if name == 'PT100':
                Rpt = 0.1
            else:
                Rpt = 1
            try:
                T = (-1) * math.sqrt(
                    Rt / (Rpt * -0.0000005775) + (0.0039083 ** 2) / (4 * ((-0.0000005775) ** 2)) - 1 / (
                    -0.0000005775)) - 0.0039083 / (2 * -0.0000005775)
            except:
                T = 999.9

        if T != 999.9:
            if unit == 'celsius':
                return T
            elif unit == 'fahrenheit':
                return T * 1.8 + 32

    def median_filter(raw):
        # Kombinierter Median und Mittelwertfilter
        laenge = len(raw)
        sortiert = sorted(raw)
        # Mitte des Arrays finden
        index = int(round(laenge * 0.4))
        # Bereich für Mittelwertbildung festlegen area = 1 + ln(laenge)   Basis 2.7
        area_groesse = 1 + int(round(math.log(laenge)))
        area = sortiert[index - area_groesse:index + area_groesse + 1]
        summe = sum(area)
        anzahl = len(area)
        # arithmetisches Mittel
        wert = round(summe / anzahl, 2)
        return wert

    def loop(self):
        while True:
            time_start = time.time()
            CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
            ram = psutil.virtual_memory()
            ram_free = ram.free / 2 ** 20
            logger.debug(_(u'CPU: ') + str(CPU_usage) + _(u' RAM free: ') + str(ram_free))

            for kanal in xrange(8):
                sensorname = Config_Sensor.get(sensortyp[kanal], 'Name')
                Temp = 0.0
                WerteArray = []
                for i in xrange(iterations):
                    # Anzahl iterations Werte messen und Durchschnitt bilden
                    if version == 'v1' or sensorname == 'KTYPE':
                        # Nicht invertiert messen
                        Wert = readAnalogData(kanal, SCLK, MOSI, MISO, CS)
                    else:
                        # Spannungsteiler ist nach v1 anders herum aufgebaut
                        Wert = 4095 - readAnalogData(kanal, SCLK, MOSI, MISO, CS)

                    if (Wert > 15) and (Wert < 4080) and (sensorname != 'KTYPE'):
                        # sinnvoller Wertebereich
                        Rtheta = messwiderstand[kanal] * ((4096.0 / Wert) - 1)
                        Tempvar = temperatur_sensor(Rtheta, sensortyp[kanal], temp_unit)
                        if Tempvar <> 999.9:
                            # normale Messung, keine Sensorprobleme
                            WerteArray.append(Tempvar)
                    elif sensorname == 'KTYPE':
                        # AD595 = 10mV/°C
                        if temp_unit == 'celsius':
                            Temperatur[kanal] = Wert * 330 / 4096
                        elif temp_unit == 'fahrenheit':
                            Temperatur[kanal] = (Wert * 330 / 4096) * 1.8 + 32
                    else:
                        Temperatur[kanal] = 999.9

                if (sensorname != 'KTYPE'):
                    gute = len(WerteArray)
                    if (gute > (iterations * 0.6)):
                        # Messwerte nur gültig wenn x% OK sind
                        # Medianfilter anwenden
                        Temperatur[kanal] = median_filter(WerteArray)
                        # else:
                        #    # Behalte alten Wert
                        #    Temperatur[kanal] = Temperatur[kanal]
                    elif (gute <= 0):
                        Temperatur[kanal] = 999.9  # kein sinnvoller Messwert, Errorwert setzen
                if (gute <> iterations) and (gute > 0):
                    warnung = 'Channel:{kanal} could only measure {gute} out of {iterations}!'.format(kanal=kanal,
                                                                                                      gute=gute,
                                                                                                      iterations=iterations)
                    logger.warning(warnung)

            time_remaining = time_start + delay - time.time()
            if time_remaining < 0:
                logger.warning(
                    _(u'measuring loop running longer than {delay}s, remaining time {time_remaining}s').format(
                        delay=delay, time_remaining=time_remaining))
            else:
                logger.debug(_(u'measuring loop remaining time {time_remaining}s of {delay}s').format(delay=delay,
                                                                                                      time_remaining=time_remaining))
                time.sleep(time_remaining)



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

if __name__ == '__main__':
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

    logger.info(_(u'WLANThermo MCP3208 started'))

    #ueberpruefe ob der Dienst schon laeuft
    pid = str(os.getpid())
    pidfilename = '/var/run/' + os.path.basename(__file__).split('.')[0]+'.pid'


    if os.access(pidfilename, os.F_OK):
        pidfile = open(pidfilename, "r")
        pidfile.seek(0)
        old_pid = int(pidfile.readline())
        if check_pid(old_pid):
            print(_(u'%s already exists, Process is running, exiting') % pidfilename)
            logger.error(_(u'%s already exists, Process is running, exiting') % pidfilename)
            sys.exit()
        else:
            logger.info(_(u'%s already exists, Process is NOT running, resuming operation') % pidfilename)
            pidfile.seek(0)
            open(pidfilename, 'w').write(pid)

    else:
        logger.debug(_(u"%s written") % pidfilename)
        open(pidfilename, 'w').write(pid)

    sys.excepthook = log_uncaught_exceptions
    os.umask (0)

try:


except KeyboardInterrupt:
    logger.info(_(u'WLANThermo stopped!'))
    logging.shutdown()
    os.unlink(pidfilename)
