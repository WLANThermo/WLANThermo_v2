#!/usr/bin/python
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

gettext.install('wlt_2_comp', localedir='/usr/share/WLANThermo/locale/', unicode=True)

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

HIGH = True  # HIGH-Pegel
LOW  = False # LOW-Pegel

# Konfigurationsdatei einlesen
defaults = {'pit_control_out':'True'}
Config = ConfigParser.ConfigParser(defaults)

# Wir laufen als root, auch andere müssen die Config schreiben!
os.umask (0)

while True:
    try:
        Config.read('/var/www/conf/WLANThermo.conf')
    except IndexError:
        time.sleep(1)
        continue
    break


Config_Sensor = ConfigParser.ConfigParser()
while True:
    try:
        Config_Sensor.read('/var/www/conf/sensor.conf')
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

logger.info(_(u'WLANThermo started'))

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
        logger.error(_(u'%s already exists, Process is running, exiting') % pidfilename)
        sys.exit()
    else:
        logger.info(_(u'%s already exists, Process is NOT running, resuming operation') % pidfilename)
        pidfile.seek(0)
        open(pidfilename, 'w').write(pid)
    
else:
    logger.debug(_(u"%s written") % pidfilename)
    open(pidfilename, 'w').write(pid)


separator = Config.get('Logging','Separator')

# Funktionsdefinition

##
## Formatierung von Strings auch wenn ein key nicht existiert.
##
def safe_format(template, args):
    for i in xrange(100):
        try:
            message = template.format(**args)
            break
        except KeyError as e:
            key = str(e).strip('\'')
            template = template.replace('{' + key + '}', '!!!' + key + '!!!')
    return message

def alarm_email(SERVER,USER,PASSWORT,STARTTLS,FROM,TO,SUBJECT,MESSAGE):
    logger.info(_(u'Send mail!'))
    
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
        logger.debug(_(u'Alert Email has been sent!'))
    except SMTPException as error:
        sendefehler = _(u'Error: unable to send email: {err}').format(err=error)
        logger.error(sendefehler)
    except:
        #TODO err undefined!
        sendefehler = _(u'Error: unable to resolve host (no internet connection?) :  {err}')
        logger.error(sendefehler)

def readAnalogData(adcChannel, SCLKPin, MOSIPin, MISOPin, CSPin):
    # Pegel vorbereiten
    GPIO.output(CSPin,   HIGH)    
    GPIO.output(CSPin,   LOW)
    GPIO.output(SCLKPin, LOW)
        
    sendcmd = adcChannel
    sendcmd |= 0b00011000 # Entspricht 0x18 (1:Startbit, 1:Single/ended)
    
    # Senden der Bitkombination (Es finden nur 5 Bits Beruecksichtigung)
    for i in xrange(5):
        if (sendcmd & 0x10): # (Bit an Position 4 pruefen. Zaehlung beginnt bei 0)
            GPIO.output(MOSIPin, HIGH)
        else:
            GPIO.output(MOSIPin, LOW)
        # Negative Flanke des Clocksignals generieren    
        GPIO.output(SCLKPin, HIGH)
        GPIO.output(SCLKPin, LOW)
        sendcmd <<= 1 # Bitfolge eine Position nach links schieben
    time.sleep(0.0001)    # 0.00001 erzeugte bei mir Raspi 2 Pest 90us
    
    # Empfangen der Daten des ADC
    adcvalue = 0 # Ruecksetzen des gelesenen Wertes
        
    for i in xrange(13):
        GPIO.output(SCLKPin, HIGH)
        GPIO.output(SCLKPin, LOW)
        # print GPIO.input(MISOPin)
        adcvalue <<= 1 # 1 Postition nach links schieben
        if(GPIO.input(MISOPin)):
            adcvalue |= 0x01
    #time.sleep(0.1)
    GPIO.output(CSPin,   HIGH)     # Ausleseaktion beenden
    return adcvalue

def temperatur_sensor (Rt, typ, unit): #Ermittelt die Temperatur
    name = Config_Sensor.get(typ,'name')
    
    if not name in ('PT100', 'PT1000'):
        a = Config_Sensor.getfloat(typ,'a')
        b = Config_Sensor.getfloat(typ,'b')
        c = Config_Sensor.getfloat(typ,'c')
        Rn = Config_Sensor.getfloat(typ,'Rn')
        
        try: 
            v = math.log(Rt/Rn)
            T = (1/(a + b*v + c*v*v)) - 273
        except: #bei unsinnigen Werten (z.B. ein- ausstecken des Sensors im Betrieb) Wert 999.9
            T = 999.9
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
            T = 999.9
    
    if T != 999.9:
        if unit == 'celsius':
            return T
        elif unit == 'fahrenheit':
            return T * 1.8 +32

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
    kopfzeile.append(_(u'Datum_Uhrzeit'))
    for kanal in xrange(8):
        if (log_kanal[kanal]):
            kopfzeile.append('Kanal ' + str(kanal))
            
    kopfzeile.append(_(u'Regulator output value'))
    kopfzeile.append(_(u'Regler set value'))
    
    while True:
        try:
            fw = open(filename,'w') #Datei anlegen
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
    index = int(round(laenge * 0.4))
    # Bereich für Mittelwertbildung festlegen area = 1 + ln(laenge)   Basis 2.7
    area_groesse = 1 + int(round(math.log(laenge) ))
    area = sortiert[index-area_groesse:index+area_groesse+1]
    summe = sum(area)
    anzahl = len(area)
    # arithmetisches Mittel
    wert = round(summe/anzahl , 2)
    return wert

def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))

sys.excepthook = log_uncaught_exceptions

# Variablendefinition und GPIO Pin-Definition
ADC_Channel = 0  # Analog/Digital-Channel
#GPIO START
SCLK        = 18 # Serial-Clock
MOSI        = 24 # Master-Out-Slave-In
MISO        = 23 # Master-In-Slave-Out
CS          = 25 # Chip-Select
BEEPER      = 17 # Piepser
PWM         = 4
IO          = 2
#GPIO END

#Hardwareversion einlesen
version = Config.get('Hardware','version')

#Log Dateinamen aus der config lesen
current_temp = Config.get('filepath','current_temp')

# Kanalvariablen-Initialisierung
sensortyp = [0 for i in xrange(8)]
log_kanal = [0 for i in xrange(8)]
temp_min = [0 for i in xrange(8)]
temp_max = [0 for i in xrange(8)]
messwiderstand = [0 for i in xrange(8)]
kanal_name = [0 for i in xrange(8)]

# read log_kanal only once because of log file format
for kanal in xrange(8):
    log_kanal[kanal] = Config.getboolean('Logging','CH' + str(kanal))

log_pitmaster =  Config.getboolean('Logging','pit_control_out')

pit_tempfile = Config.get('filepath','pitmaster')

#Soundoption einlesen
sound_on = Config.getboolean('Sound','Beeper_enabled')
sound_on_start = Config.getboolean('Sound','beeper_on_start')

#Einlesen der Software-Version
command = 'cat /var/www/header.php | grep \'] = "V\' | cut -c31-38'

build = os.popen(command).read()

#Einlesen der Logging-Option
newfile = Config.getboolean('Logging','write_new_log_on_restart')

# Pin-Programmierung (SPI)
GPIO.setup(SCLK, GPIO.OUT)
GPIO.setup(MOSI, GPIO.OUT)
GPIO.setup(MISO, GPIO.IN)
GPIO.setup(CS,   GPIO.OUT)

# Pin-Programmierung (Pitmaster)
GPIO.setup(PWM, GPIO.OUT)
GPIO.setup(IO, GPIO.OUT)

# Pin-Programmierung (Beeper)
GPIO.setup(BEEPER,  GPIO.OUT)

GPIO.output(PWM, LOW)
GPIO.output(IO, LOW)

if sound_on_start:
    GPIO.output(BEEPER, HIGH)
    time.sleep(1)
    GPIO.output(BEEPER, LOW)

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
Temperatur = [0.10,0.10,0.10,0.10,0.10,0.10,0.10,0.10]

alarm_state = [None, None, None, None, None, None, None, None]
test_alarm = False
config_mtime = 0
alarm_time = 0

try:
    while True:
        time_start = time.time()
        CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
        ram = psutil.virtual_memory()
        ram_free = ram.free / 2**20
        logger.debug(_(u'CPU: ') + str(CPU_usage) + _(u' RAM free: ') + str(ram_free))
        alarm_irgendwo = False
        alarm_neu = False
        alarm_repeat = False
        alarme = []
        statusse = []
        
        Temperatur_string = ['999.9','999.9','999.9','999.9','999.9','999.9','999.9','999.9']
        Temperatur_alarm = ['er','er','er','er','er','er','er','er']
        Displaytemp = ['999.9','999.9','999.9','999.9','999.9','999.9','999.9','999.9']

        new_config_mtime = os.path.getmtime('/var/www/conf/WLANThermo.conf')
        if new_config_mtime > config_mtime:
            logger.debug(_(u'reading configuration again...'))
            while True:
                try:
                    new_config.read('/var/www/conf/WLANThermo.conf')
                except IndexError:
                    time.sleep(1)
                    continue
                break
            config_mtime = new_config_mtime
        
        pit_on = new_config.getboolean('ToDo','pit_on')
        
        for kanal in xrange (8):
            try:
                temp_max[kanal] = new_config.getfloat('temp_max','temp_max' + str(kanal))
            except ValueError:
                logger.error(_(u'Error reading upper limit on channel ') + str(kanal))
                temp_max[kanal] = 200
            
            try:
                temp_min[kanal] = new_config.getfloat('temp_min','temp_min' + str(kanal))
            except ValueError:
                logger.error(_(u'Error reading lower limit on channel ') + str(kanal))
                temp_max[kanal] = -20
            
            try:
                messwiderstand[kanal] = new_config.getfloat('Messen','Messwiderstand' + str(kanal))
            except ValueError:
                logger.error(_(u'Error reading measurement resistor on channel ') + str(kanal))
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
            logger.error(_(u'Error reading status interval from config'))
            status_interval = 0
            
        try:
            alarm_interval = new_config.getint('Alert', 'alarm_interval')
        except ValueError:
            logger.error(_(u'Error reading alarm interval from config'))
            alarm_interval = 0

        # Einlesen welche Alarmierungsart aktiv ist
        Email_alert = new_config.getboolean('Email','email_alert')
        WhatsApp_alert = new_config.getboolean('WhatsApp','whatsapp_alert')
        Push_alert = new_config.getboolean('Push', 'push_on')
        Telegram_alert = new_config.getboolean('Telegram', 'telegram_alert')
        App_alert = new_config.getboolean('App', 'app_alert')
        
        temp_unit = new_config.get('locale', 'temp_unit')
        
        if os.path.isfile('/var/www/alert.ack'):
            logger.info('alert.ack vorhanden')
            for kanal in range (8):
                if alarm_state[kanal] == 'hi':
                    logger.debug(_(u'Acknowledging temperature over upper limit on channel ') + str(kanal))
                    alarm_state[kanal] = 'hi_ack'
                elif alarm_state[kanal] == 'lo':
                    logger.debug(_(u'Acknowledging temperature under lower limit on channel ') + str(kanal))
                    alarm_state[kanal] = 'lo_ack'
            os.unlink('/var/www/alert.ack')
        
        if os.path.isfile('/var/www/alert.test'):
            logger.info(_(u'alert.test exists'))
            test_alarm = True
            os.unlink('/var/www/alert.test')
        
        
        for kanal in xrange(8):
            sensorname = Config_Sensor.get(sensortyp[kanal],'Name')
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
                    Rtheta = messwiderstand[kanal]*((4096.0/Wert) - 1)
                    Tempvar = temperatur_sensor(Rtheta, sensortyp[kanal], temp_unit)
                    if Tempvar <> 999.9:
                        # normale Messung, keine Sensorprobleme
                        WerteArray.append(Tempvar)
                elif sensorname == 'KTYPE':
                    # AD595 = 10mV/°C
                    if temp_unit == 'celsius':
                        Temperatur[kanal] = Wert * 330/4096
                    elif temp_unit == 'fahrenheit':
                        Temperatur[kanal] = (Wert * 330/4096) * 1.8 + 32
                else:
                    Temperatur[kanal] = 999.9
                        
            if (sensorname != 'KTYPE'):
                gute = len(WerteArray)
                if (gute > (iterations * 0.6)):
                    # Messwerte nur gültig wenn x% OK sind
                    # Medianfilter anwenden
                    Temperatur[kanal] = median_filter(WerteArray)
                    #else:
                    #    # Behalte alten Wert 
                    #    Temperatur[kanal] = Temperatur[kanal] 
                elif (gute <= 0):
                    Temperatur[kanal] = 999.9               # kein sinnvoller Messwert, Errorwert setzen
            if (gute <> iterations) and (gute > 0):
                warnung = 'Channel:{kanal} could only measure {gute} out of {iterations}!'.format(kanal=kanal, gute=gute, iterations=iterations)
                logger.warning(warnung)
                
            alarm_values = dict()
            if temp_unit == 'celsius':
                alarm_values['temp_unit'] = '°C'
                alarm_values['temp_unit_long'] = _(u'degrees Celsius')
            elif temp_unit == 'fahrenheit':
                alarm_values['temp_unit'] = '°F'
                alarm_values['temp_unit_long'] = _(u'degrees Fahrenheit')
            alarm_values['kanal'] = kanal
            alarm_values['name'] = kanal_name[kanal]
            alarm_values['temperatur'] = Temperatur[kanal]
            alarm_values['temp_max'] = temp_max[kanal]
            alarm_values['temp_min'] = temp_min[kanal]
            alarm_values['lf'] = '\n'
            
            if Temperatur[kanal] <> 999.9:    
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
        
        message_values = dict()
        message_values['alarme'] = ''.join(alarme)
        message_values['statusse'] = ''.join(statusse)
        message_values['lf'] = '\n'
        
        alarm_message = safe_format(message_template, message_values)
            
        
        # Beeper bei jedem unquittiertem Alarm
        if alarm_irgendwo:
            if sound_on:
                logger.debug('BEEPER!!!')
                GPIO.output (BEEPER, HIGH)
                time.sleep(0.2)
                GPIO.output (BEEPER, LOW)
                time.sleep(0.2)
                GPIO.output (BEEPER, HIGH)
                time.sleep(0.2)
                GPIO.output (BEEPER, LOW)
                time.sleep(0.2)
                GPIO.output (BEEPER, HIGH)
                time.sleep(0.2)
                GPIO.output (BEEPER, LOW)
            if alarm_interval > 0 and alarm_time + alarm_interval < time.time():
                # Alarm erneut senden
                alarm_repeat = True
                alarm_time = time.time()
        
        if status_interval > 0 and alarm_time + status_interval < time.time():
            # Periodisch den Status senden, wenn gewünscht
            alarm_repeat = True

        # Nachrichten senden
        if alarm_neu or test_alarm or alarm_repeat:
            alarm_time = time.time()
            
            if alarm_neu:
                logger.debug(_(u'new alert, sending messages'))
            if test_alarm:
                logger.debug(_(u'test alert, sending messages'))
                test_alarm = False
                alarm_message = _(u'test message\n') + alarm_message
            if alarm_repeat:
                logger.info(_(u'repeated alert, sending messages'))
                
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
                
                alarm_email(Email_server,Email_user,Email_password, Email_STARTTLS, Email_from, Email_to, Email_subject, alarm_message)
                
            if WhatsApp_alert:
                # Wenn konfiguriert, Alarm per WhatsApp schicken
                WhatsApp_number = new_config.get('WhatsApp','whatsapp_number')
                cmd="/usr/sbin/sende_whatsapp.sh " + WhatsApp_number + " '" + alarm_message + "'"
                os.system(cmd)
                
            if Telegram_alert:
                Telegram_URL = 'https://api.telegram.org/bot{token}/sendMessage'
                Telegram_Body = 'text={messagetext}&chat_id={chat_id}'
                Telegram_chat_id = new_config.get('Telegram', 'telegram_chat_id')
                Telegram_token = new_config.get('Telegram', 'telegram_token')
                
                alarm_message2 = urllib.quote(alarm_message)
                url = Telegram_URL.format(messagetext=urllib.quote(alarm_message).replace('\n', '<br/>'), chat_id=Telegram_chat_id, token=Telegram_token)
                body = Telegram_Body.format(messagetext=urllib.quote(alarm_message).replace('\n', '<br/>'), chat_id=Telegram_chat_id, token=Telegram_token)
                try: 
                    logger.debug(_(u'Telegram POST request, URL: ') + url + _(u'\nbody: ') + body)
                    response = urllib2.urlopen(url, body)
                    
                    logger.info(_(u'Telegram HTTP return code: ') + str(response.getcode()))
                    logger.debug(_(u'Telegram URL: ') + response.geturl())
                    logger.debug(_(u'Telegram result: ') + response.read(500))

                except urllib2.HTTPError, e:
                    logger.error(u'Telegram HTTP error: ' + str(e.code) + u' - ' + e.read(500))
                except urllib2.URLError, e:
                    logger.error(u'Telegram URLError: ' + str(e.reason))  
                    
            if App_alert:
                # Wenn konfiguriert, Alarm per Appnachricht schicken
                App_inst_id = new_config.get('App', 'app_inst_id')
                App_device = new_config.get('App', 'app_device')
                App_inst_id2 = new_config.get('App', 'app_inst_id2')
                App_device2 = new_config.get('App', 'app_device2')
                App_inst_id3 = new_config.get('App', 'app_inst_id3')
                App_device3 = new_config.get('App', 'app_device3')
                App_sound = new_config.get('App', 'app_device3')
                
                if App_inst_id3 != '':
                    App_URL = 'http://weyerstall.de/WlanthermoPush.php?inst_id={inst_id}&device={device}&inst_id2={inst_id2}&device2={device2}&inst_id3={inst_id3}&device3={device3}&message={messagetext}'
                elif App_inst_id2 != '':
                    App_URL = 'http://weyerstall.de/WlanthermoPush.php?inst_id={inst_id}&device={device}&inst_id2={inst_id2}&device2={device2}&message={messagetext}'
                else:
                    App_URL = 'http://weyerstall.de/WlanthermoPush.php?inst_id={inst_id}&device={device}&message={messagetext}'

                alarm_message2 = urllib.quote(alarm_message)
                url = App_URL.format(messagetext=urllib.quote(alarm_message).replace('\n', '<br/>'), inst_id=App_inst_id, device=App_device, inst_id2=App_inst_id2, device2=App_device2, inst_id3=App_inst_id3, device3=App_device3)
                try: 
                    logger.debug(_(u'App GET request, URL: ') + url)
                    response = urllib2.urlopen(url)
                    
                    logger.info(_(u'App HTTP return code: ') + str(response.getcode()))
                    logger.debug(_(u'App URL: ') + response.geturl())
                    logger.debug(_(u'App result: ') + response.read(500))

                except urllib2.HTTPError, e:
                    logger.error(u'App HTTP error: ' + str(e.code) + u' - ' + e.read(500))
                except urllib2.URLError, e:
                    logger.error(u'App URLError: ' + str(e.reason))
                    
            if Push_alert:
                # Wenn konfiguriert, Alarm per Pushnachricht schicken
                Push_URL = new_config.get('Push', 'push_url')
                Push_Body = new_config.get('Push', 'push_body')
        
                alarm_message2 = urllib.quote(alarm_message)
                
                try:
                    url = Push_URL.format(messagetext=urllib.quote(alarm_message).replace('\n', '<br/>'))
                    body = Push_Body.format(messagetext=urllib.quote(alarm_message).replace('\n', '<br/>'))
                except KeyError, key:
                    logger.error(u'Key "' + str(key) + u'" is undefined!')
                else:
                    try: 
                        if Push_Body == '':
                            logger.debug(_(u'push GET request, URL: ') + url)
                            response = urllib2.urlopen(url)
                        else:
                            logger.debug(_(u'push POST request, URL: ') + url + _(u'\nbody: ') + body)
                            response = urllib2.urlopen(url, body)
                        
                        logger.info(_(u'push HTTP return code: ') + str(response.getcode()))
                        logger.debug(_(u'push URL: ') + response.geturl())
                        logger.debug(_(u'push result: ') + response.read(500))
    
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
        for kanal in xrange(8):
            # 8 Felder mit allen Temperaturen
            lcsv.append(str(Temperatur_string[kanal]))
        for kanal in xrange(8):
            # 8 Felder mit allen Alarmzuständen
            lcsv.append(Temperatur_alarm[kanal])
        lcsv.append(build)
        lcsv.append(logdatei)
        
        
        while True:
            try:
                fcsv = open(current_temp  + '_tmp', 'w')
                fcsv.write(';'.join(lcsv))
                fcsv.flush()
                os.fsync(fcsv.fileno())
                fcsv.close()
                os.rename(current_temp + '_tmp', current_temp)
            except IndexError:
                time.sleep(1)
                logger.debug(_(u'Error: Could not write to file {file}!').format(file=current_temp))
                continue
            break
            
        #Messzyklus protokollieren und nur die Kanaele loggen, die in der Konfigurationsdatei angegeben sind
        log_line = []
        log_line.append(Uhrzeit_lang)
        
        for i in xrange(8):
            if (log_kanal[i]):
                log_line.append(str(Temperatur[i]))
        
        if pit_on:
            try:
                with open(pit_tempfile,'r') as pitfile:
                    pit_values = pitfile.readline().split(';')
                    pit_new = pit_values[3].rstrip('%')
                    pit_set = pit_values[1]
                    log_line.append(pit_new)
                    log_line.append(pit_set)
            except IOError:
                # Wenn keine aktuellen Werte verfügbar sind, leere Werte schreiben
                log_line.append('')
                log_line.append('')
        else:
                log_line.append('')
                log_line.append('')
        
        while True:
            try:
                # Generierung des Logfiles
                logfile = open(name,'a')
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
            logger.warning(_(u'measuring loop running longer than {delay}s, remaining time {time_remaining}s').format(delay=delay, time_remaining=time_remaining))
        else:
            logger.debug(_(u'measuring loop remaining time {time_remaining}s of {delay}s').format(delay=delay, time_remaining=time_remaining))
            time.sleep(time_remaining)

except KeyboardInterrupt:
    logger.info(_(u'WLANThermo stopped!'))
    logging.shutdown()
    os.unlink(pidfilename)
