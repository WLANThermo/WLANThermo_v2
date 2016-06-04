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
import psutil
import signal

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

logger.info('WLANThermo started')

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
        print("%s existiert, Prozess läuft bereits, beende Skript" % pidfilename)
        logger.error("%s existiert, Prozess läuft bereits, beende Skript" % pidfilename)
        sys.exit()
    else:
        logger.info("%s existiert, Prozess läuft nicht, setze Ausführung fort" % pidfilename)
        pidfile.seek(0)
        open(pidfilename, 'w').write(pid)
    
else:
    logger.debug("%s geschrieben" % pidfilename)
    open(pidfilename, 'w').write(pid)


# Funktionsdefinition
def alarm_email(SERVER,USER,PASSWORT,STARTTLS,FROM,TO,SUBJECT,MESSAGE):
    logger.info('Send mail!')
    
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
        

        m = text(MESSAGE)

        m['Subject'] = SUBJECT
        m['From'] = FROM
        m['To'] = TO


        s.sendmail(FROM,TO, m.as_string())
        s.quit()
        logger.debug('Alarmmail gesendet!')
    except SMTPException as error:
        sendefehler = "Error: unable to send email :  {err}".format(err=error)
        logger.error(sendefehler)
    except:
        sendefehler = "Error: unable to resolve host (no internet connection?) :  {err}"
        logger.error(sendefehler)

def readAnalogData(adcChannel, SCLKPin, MOSIPin, MISOPin, CSPin):
    # Pegel vorbereiten
    GPIO.output(CSPin,   HIGH)    
    GPIO.output(CSPin,   LOW)
    GPIO.output(SCLKPin, LOW)
        
    sendcmd = adcChannel
    sendcmd |= 0b00011000 # Entspricht 0x18 (1:Startbit, 1:Single/ended)
    
    # Senden der Bitkombination (Es finden nur 5 Bits Beruecksichtigung)
    for i in range(5):
        if (sendcmd & 0x10): # (Bit an Position 4 pruefen. Zaehlung beginnt bei 0)
            GPIO.output(MOSIPin, HIGH)
        else:
            GPIO.output(MOSIPin, LOW)
        # Negative Flanke des Clocksignals generieren    
        GPIO.output(SCLKPin, HIGH)
        GPIO.output(SCLKPin, LOW)
        sendcmd <<= 1 # Bitfolge eine Position nach links schieben
    time.sleep(0.0001)    # 0.00001 erzeugte bei mir Raspi 2 Pest 90us
    #for p in range(19):
    #    GPIO.output(SCLKPin,LOW)            
    # Empfangen der Daten des ADC
    adcvalue = 0 # Ruecksetzen des gelesenen Wertes
    for i in range(13):
        GPIO.output(SCLKPin, HIGH)
        GPIO.output(SCLKPin, LOW)
        # print GPIO.input(MISOPin)
        adcvalue <<= 1 # 1 Postition nach links schieben
        if(GPIO.input(MISOPin)):
            adcvalue |= 0x01
    #time.sleep(0.1)
    GPIO.output(CSPin,   HIGH)     # Ausleseaktion beenden
    return adcvalue

def temperatur_sensor (Rt, typ): #Ermittelt die Temperatur
    name = Config_Sensor.get(typ,'name')
    
    if (name != 'PT100') and (name != 'PT1000'):
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
    



    return T

def dateiname(): #Zeitstring fuer eindeutige Dateinamen erzeugen

    zeit = time.localtime()
    # fn = string.zfill(zeit[2],2)+string.zfill(zeit[1],2)+str(zeit[0])+string.zfill(zeit[3],2)+string.zfill(zeit[4],2)+string.zfill(zeit[5],2)
    fn = str(zeit[0]) + string.zfill(zeit[1],2) + string.zfill(zeit[2],2) + "_" + string.zfill(zeit[3],2)+string.zfill(zeit[4],2)+string.zfill(zeit[5],2)
    return fn


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


# Kanalvariablen-Initialisierung
Sensornummer_typ = ['ACURITE','ACURITE','ACURITE','ACURITE','ACURITE','ACURITE','ACURITE','ACURITE']
Logkanalnummer = [True,True,True,True,True,True,True,True]
temp_min =['0','0','0','0','0','0','0','0']
temp_max =['0','0','0','0','0','0','0','0']
#Hardwareversion einlesen
version = Config.get('Hardware','version')

#Log Dateinamen aus der config lesen
current_temp = Config.get('filepath','current_temp')

#Sensortypen einlesen pro Kanal
Sensornummer_typ[0] =  Config.get('Sensoren','CH0')
Sensornummer_typ[1] =  Config.get('Sensoren','CH1')
Sensornummer_typ[2] =  Config.get('Sensoren','CH2')
Sensornummer_typ[3] =  Config.get('Sensoren','CH3')
Sensornummer_typ[4] =  Config.get('Sensoren','CH4')
Sensornummer_typ[5] =  Config.get('Sensoren','CH5')
Sensornummer_typ[6] =  Config.get('Sensoren','CH6')
Sensornummer_typ[7] =  Config.get('Sensoren','CH7')
#Alarmwerte aus der conf lesen und temperaturen.csv erzeugen

temp_min[0] = Config.get('temp_min','temp_min0')
temp_min[1] = Config.get('temp_min','temp_min1')
temp_min[2] = Config.get('temp_min','temp_min2')
temp_min[3] = Config.get('temp_min','temp_min3')
temp_min[4] = Config.get('temp_min','temp_min4')
temp_min[5] = Config.get('temp_min','temp_min5')
temp_min[6] = Config.get('temp_min','temp_min6')
temp_min[7] = Config.get('temp_min','temp_min7')

temp_max[0] = Config.get('temp_max','temp_max0')
temp_max[1] = Config.get('temp_max','temp_max1')
temp_max[2] = Config.get('temp_max','temp_max2')
temp_max[3] = Config.get('temp_max','temp_max3')
temp_max[4] = Config.get('temp_max','temp_max4')
temp_max[5] = Config.get('temp_max','temp_max5')
temp_max[6] = Config.get('temp_max','temp_max6')
temp_max[7] = Config.get('temp_max','temp_max7')

name ='/var/www/temperaturen.csv'
while True:
    try:
        fw = open(name + '_tmp','w') #Datei anlegen
        for i in range(8):
            fw.write(temp_max[i] + '\n') # Alarm-Max-Werte schreiben
        for i in range(8):
            fw.write(temp_min[i] + '\n') # Alarm-Min-Werte schreiben
        fw.flush()
        os.fsync(fw.fileno())
        fw.close()
        os.rename(name + '_tmp', name)
    except IndexError:
        time.sleep(1)
        continue
    break



#Loggingoptionen einlesen
Logkanalnummer[0] =  Config.getboolean('Logging','CH0')
Logkanalnummer[1] =  Config.getboolean('Logging','CH1')
Logkanalnummer[2] =  Config.getboolean('Logging','CH2')
Logkanalnummer[3] =  Config.getboolean('Logging','CH3')
Logkanalnummer[4] =  Config.getboolean('Logging','CH4')
Logkanalnummer[5] =  Config.getboolean('Logging','CH5')
Logkanalnummer[6] =  Config.getboolean('Logging','CH6')
Logkanalnummer[7] =  Config.getboolean('Logging','CH7')

log_pitmaster =  Config.getboolean('Logging','pit_control_out')

separator = Config.get('Logging','Separator')

pit_tempfile = Config.get('filepath','pitmaster')

#Soundoption einlesen
sound_on = Config.getboolean('Sound','Beeper_enabled')

#Einlesen, ueber wieviele Messungen integriert wird 
iterations = Config.getint('Messen','Iterations')

#delay zwischen jeweils 8 Messungen einlesen 
delay = Config.getfloat('Messen','Delay')

#Einlesen des Reihenwiderstandes zum Fuehler (Hardwareabhaengig!!) 
messwiderstand = [47.00, 47.00, 47.00, 47.00, 47.00, 47.00, 47.00, 47.00]

messwiderstand[0] = Config.getfloat('Messen','Messwiderstand0')
messwiderstand[1] = Config.getfloat('Messen','Messwiderstand1')
messwiderstand[2] = Config.getfloat('Messen','Messwiderstand2')
messwiderstand[3] = Config.getfloat('Messen','Messwiderstand3')
messwiderstand[4] = Config.getfloat('Messen','Messwiderstand4')
messwiderstand[5] = Config.getfloat('Messen','Messwiderstand5')
messwiderstand[6] = Config.getfloat('Messen','Messwiderstand6')
messwiderstand[7] = Config.getfloat('Messen','Messwiderstand7')

#Einlesen Email-Parameter fuer Alarmmeldung
Email_alert = Config.getboolean('Email','email_alert')
Email_server  = Config.get('Email','server')
Email_auth = Config.getboolean('Email','auth')
Email_user = Config.get('Email','username')
Email_password = Config.get('Email','password')
Email_from = Config.get('Email','email_from')
Email_to = Config.get('Email','email_to')
Email_subject = Config.get('Email','email_subject')
Email_STARTTLS = Config.getboolean ('Email','starttls')

#Einlesen WhatsApp-Parameter fuer Alarmmeldung
WhatsApp_alert = Config.getboolean('WhatsApp','whatsapp_alert')
WhatsApp_number = Config.get('WhatsApp','whatsapp_number')

#Einlesen der Software-Version
command = 'cat /var/www/header.php | grep \'] = "V\' | cut -c31-38'

build = os.popen(command).read()

#Einlesen Displayeinstellungen
LCD = Config.getboolean('Display','lcd_present')

#Einlesen der Push Nachrichten Einstellungen
PUSH = Config.getboolean('Push', 'push_on')
PUSH_URL = Config.get('Push', 'push_url')
#

#Einlesen der Logging-Option
newfile = Config.getboolean('Logging','write_new_log_on_restart')


# Pin-Programmierung
GPIO.setup(SCLK, GPIO.OUT)
GPIO.setup(MOSI, GPIO.OUT)
GPIO.setup(MISO, GPIO.IN)
GPIO.setup(CS,   GPIO.OUT)
GPIO.setup(PWM, GPIO.OUT)
GPIO.setup(IO, GPIO.OUT)
GPIO.output(PWM, LOW)
GPIO.output(IO, LOW)

if sound_on:
    GPIO.setup(BEEPER,  GPIO.OUT)
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
    
    # Falls der Symlink noch da ist, loeschen
    try:
        os.remove('/var/log/WLAN_Thermo/TEMPLOG.csv')
    except:
        pass

    os.symlink(name, '/var/log/WLAN_Thermo/TEMPLOG.csv') #Symlink TEMPLOG.csv auf die gerade zu benutzte eindeutige Log-Datei legen.
    kopfzeile='Datum_Uhrzeit' 
    for kanal in range(8):
        if (Logkanalnummer[kanal]):
            kopfzeile = kopfzeile + separator +  'Kanal ' + str(kanal)
            
    if log_pitmaster:
        kopfzeile + separator +  'Reglerausgang'
    
    kopfzeile = kopfzeile +'\n'
    
    while True:
        try:
            fw = open(name,'w') #Datei anlegen
            fw.write(kopfzeile) # Kopfzeile der CSV-Datei schreiben
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
        except IndexError:
            time.sleep(1)
            continue
        break

else:
    #Kein neues File anlegen
    if os.path.exists('/var/log/WLAN_Thermo/TEMPLOG.csv'):
        # pruefen, ob die Datei schon da ist zum anhaengen, auch False bei Broken Link!
        name = '/var/log/WLAN_Thermo/TEMPLOG.csv'
    else:
        # Falls der Symlink noch da ist, loeschen
        try:
            os.remove('/var/log/WLAN_Thermo/TEMPLOG.csv')
        except:
            pass
         
        os.symlink(name, '/var/log/WLAN_Thermo/TEMPLOG.csv')
        kopfzeile='Datum_Uhrzeit'
        
        for kanal in range(8):
            if (Logkanalnummer[kanal]):
                kopfzeile = kopfzeile + separator +  'Kanal ' + str(kanal)
        
        if log_pitmaster:
            kopfzeile + separator +  'Reglerausgang'
        
        kopfzeile = kopfzeile +'\n'
        # Datei noch nicht vorhanden, doch neu anlegen!
        while True:
            try:
                fw = open(name,'w')
                fw.write(kopfzeile) # Kopfzeile der CSV-Datei schreiben
                fw.flush()
                os.fsync(fw.fileno())
                fw.close()
            except IndexError:
                time.sleep(1)
                continue
            break
        


#Alarmstatusspeicher loeschen
Alarm_state_high_previous = 0
Alarm_state_low_previous = 0

Temperatur = [0.10,0.10,0.10,0.10,0.10,0.10,0.10,0.10]

alarm_state = [None, None, None, None, None, None, None, None]

try:
    while True: #Messchleife
        CPU_usage = psutil.cpu_percent(interval=1, percpu=True)
        ram = psutil.virtual_memory()
        ram_free = ram.free / 2**20
        logger.debug('CPU: ' + str(CPU_usage) + ' RAM free: ' + str(ram_free))
        alarm_irgendwo = False
        alarm_neu = False
        Alarm_message = 'Achtung!\n'
        Alarm_high = [999,999,999,999,999,999,999,999]
        Alarm_low = [0,0,0,0,0,0,0,0]
        # Temperatur = [0.10,0.10,0.10,0.10,0.10,0.10,0.10,0.10] ausserhalb der Schleife um im Fehlerfall den Vorgängerwert zu nehmen
        Temperatur_string = ['999.9','999.9','999.9','999.9','999.9','999.9','999.9','999.9']
        Temperatur_alarm = ['er','er','er','er','er','er','er','er']
        Displaytemp = ['999.9','999.9','999.9','999.9','999.9','999.9','999.9','999.9']

        while True:
            try:
                af = open("/var/www/temperaturen.csv") #Datei mit den Alarmwerten einlesen
            except IndexError:
                time.sleep(1)
                continue
            break
        
        for i in range (8):
            Alarm_high[i] = int(af.readline())
        for i in range (8):
            Alarm_low[i] = int(af.readline())
        af.close()
        
        if os.path.isfile('/var/www/alert.ack'):
            logger.info('alert.ack vorhanden')
            for kanal in range (8):
                if alarm_state[kanal] == 'hi':
                    logger.debug('Bestätige Übertemperatur für Kanal ' + str(kanal))
                    alarm_state[kanal] = 'hi_ack'
                elif alarm_state[kanal] == 'lo':
                    logger.debug('Bestätige Untertemperatur für Kanal ' + str(kanal))
                    alarm_state[kanal] = 'lo_ack'
            os.unlink('/var/www/alert.ack')
        
        guteArray = []
        for kanal in range (8): #Maximal 8 Kanaele abfragen
            sensortyp = Sensornummer_typ[kanal]
            sensorname = Config_Sensor.get(sensortyp,'Name')
            Temp = 0.0
            gute = 0
            WerteArray = []
            for i in range (iterations): #Anzahl iterations Werte messen und Durchschnitt bilden
                ADC_Channel = kanal
                if (version=='v1'):
                    Wert = readAnalogData(ADC_Channel, SCLK, MOSI, MISO, CS)
                    
                else:
                    Wert = 4096 - readAnalogData(ADC_Channel, SCLK, MOSI, MISO, CS)
                    
                if (Wert > 60) and (sensorname != 'KTYPE'): #sinnvoller Wertebereich
                    Rtheta = messwiderstand[kanal]*((4096.0/Wert) - 1)
                    Tempvar = temperatur_sensor(Rtheta,sensortyp)
                    if Tempvar <> 999.9: #normale Messung, keine Sensorprobleme
                        gute = gute + 1
                        WerteArray.append(Tempvar)
                   #     Temp = Temp + Tempvar
                   #     Temperatur[kanal] = round(Temp/gute,2)
                   # else:
                   #     if (gute==0):
                   #         Temperatur[kanal]  = 999.9 # Problem waehrend des Messzyklus aufgetreten, Errorwert setzen
                else:
                    if sensorname=='KTYPE':
                        # AD595 = 10mV/°C
                        Temperatur[kanal] = Wert * 330/4096
                    else:
                        Temperatur[kanal] = 999.9 # kein sinnvoller Messwert, Errorwert setzen
            if (sensorname != 'KTYPE'):
                guteArray.append(gute)
                if (gute > (iterations *0.6)):              # Messwerte nur gültig wenn x% OK sind
                    sortiertWerte = sorted(WerteArray)      # sortiert Werte der Größe nach
                    index = int(round(gute * 0.4))          # ca Mitte des sortierten Arrays.( 40% weil es mehr
                                                            # Ausrutscher nach oben gibt )
                    Count = 1 + int(round(math.log(gute) )) # Count = 1 + ln(gute)   Basis 2.7
                    for m in range(Count):                  # mehrere Werte aus der Mitte
                        Temp += sortiertWerte[index-m] + sortiertWerte[index+m]
                    Temperatur[kanal]=round(Temp/(Count * 2.0) , 2)    # arithmetisches Mittel
                    sortiertWerte = []
                    #else:
                    #    # Behalte alten Wert 
                    #    Temperatur[kanal] = Temperatur[kanal] 
                if (gute <= 0):
                    Temperatur[kanal] = 999.9               # kein sinnvoller Messwert, Errorwert setzen
            WerteArray = []
            if (gute <> iterations) and (gute > 0):
                warnung = 'Kanal: ' + str(kanal) + ' konnte nur ' + str(gute) + ' von ' +  str(iterations) + ' messen!!'
                logger.warning(warnung) 
            if Temperatur[kanal] <> 999.9:    
                Temperatur_string[kanal] = "%.1f" % Temperatur[kanal]
                Temperatur_alarm[kanal] = 'ok'
                if Temperatur[kanal] >= Alarm_high[kanal]:
                    if alarm_state[kanal] == 'hi':
                        alarm_irgendwo = True
                    elif alarm_state[kanal] == 'hi_ack':
                        pass
                    else:
                        alarm_irgendwo = True
                        alarm_neu = True
                        alarm_state[kanal] = 'hi'
                    Alarm_message = Alarm_message + 'Kanal ' + str(kanal) + ' hat Uebertemperatur!\n' + str(Temperatur[kanal]) + ' Grad Celsius !!! \n'
                    Temperatur_alarm[kanal] = 'hi'
                    #Temperatur_string[kanal] = chr(1) + "%.1f" % Temperatur[kanal]
                elif Temperatur[kanal] <= Alarm_low[kanal]:
                    if alarm_state[kanal] == 'lo':
                        alarm_irgendwo = True
                    elif alarm_state[kanal] == 'lo_ack':
                        pass
                    else:
                        alarm_irgendwo = True
                        alarm_neu = True
                        alarm_state[kanal] = 'lo'
                    Alarm_message = Alarm_message + 'Kanal ' + str(kanal) + ' hat Untertemperatur!\n' + str(Temperatur[kanal]) + ' Grad Celsius !!! \n'
                    Temperatur_alarm[kanal] = 'lo'
                    #Temperatur_string[kanal] = chr(0) + "%.1f" % Temperatur[kanal]
                else:
                    alarm_state[kanal] = 'ok'
                    
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
                
        # Nachrichten bei neuem Alarm senden
        if alarm_neu:
            logger.debug('Neuer Alarm, versende Nachrichten')
            if Email_alert: #wenn konfiguriert, email schicken
                alarm_email(Email_server,Email_user,Email_password, Email_STARTTLS, Email_from, Email_to, Email_subject, Alarm_message)
            
            if WhatsApp_alert: #wenn konfiguriert, Alarm per WhatsApp schicken
                cmd="/usr/sbin/sende_whatsapp.sh " + WhatsApp_number + " '" + Alarm_message + "'"
                os.system(cmd)
            if PUSH:
                Alarm_message2 = urllib.quote(Alarm_message)
                push_cmd =  PUSH_URL.replace('messagetext', Alarm_message2.replace('\n', '<br/>'))
                push_cmd = 'wget -q -O - ' + push_cmd
                logger.debug(push_cmd)
                os.popen(push_cmd)
        
        #Temperaturen fuer Display anzeige aufbereiten
        if LCD:
            for kanal in range(8):
                Displaytemp[kanal] = Temperatur_string[kanal]
                
        new_config = ConfigParser.SafeConfigParser()
        while True:
            try:
                new_config.read('/var/www/conf/WLANThermo.conf')
            except IndexError:
                time.sleep(1)
                continue
            break
        
        pit_on = new_config.getboolean('ToDo','pit_on')
        
        # Log datei erzeugen
        lt = time.localtime()#  Uhrzeit des Messzyklus
        jahr, monat, tag, stunde, minute, sekunde = lt[0:6]
        Uhrzeit = string.zfill(stunde,2) + ':' + string.zfill(minute,2)+ ':' + string.zfill(sekunde,2)
        Uhrzeit_lang = string.zfill(tag,2) + '.' + string.zfill(monat,2) + '.' + string.zfill((jahr-2000),2) + ' ' + Uhrzeit
        logdatei = os.readlink('/var/log/WLAN_Thermo/TEMPLOG.csv')
        logdatei = logdatei[21:-4]
        lcsv = Uhrzeit_lang 
        t = ""
        for kanal in range(8):# eine Zeile mit allen Temperaturen
            lcsv = lcsv + ";" + str(Temperatur_string[kanal])
        for kanal in range(8):# eine Zeile mit allen alarm Temperaturen
            lcsv = lcsv + ";" + Temperatur_alarm[kanal]
        lcsv = lcsv + ";" + build + ";" + logdatei
        
        
        while True:
            try:
                fcsv = open(current_temp  + '_tmp', 'w')
                fcsv.write(lcsv)
                fcsv.flush()
                os.fsync(fcsv.fileno())
                fcsv.close()
                os.rename(current_temp + '_tmp', current_temp)
            except IndexError:
                time.sleep(1)
                logger.debug("Fehler beim Schreiben in die Datei current.temp!")
                continue
            break
            
        #Messzyklus protokollieren und nur die Kanaele loggen, die in der Konfigurationsdatei angegeben sind
        schreiben = Uhrzeit_lang
        for i in range(8):
           if (Logkanalnummer[i]):
              schreiben = schreiben + separator + str(Temperatur[i])
        
        if log_pitmaster:
            if pit_on:
                try:
                    with open(pit_tempfile,'r') as pitfile:
                        pit_values = pitfile.readline().split(';')
                        pit_new = pit_values[3].rstrip('%')
                        pit_set = pit_values[1]
                        schreiben += separator + pit_new + separator + pit_set
                except IOError:
                    # Wenn keine aktuellen Werte verfügbar sind, leere Werte schreiben
                    schreiben += separator + separator
        
        while True:
            try:
                # Generierung des Logfiles
                logfile = open(name,'a')#logfile oeffnen
                logfile.write(schreiben + '\n')
                logfile.flush()
                os.fsync(logfile.fileno())
                logfile.close()
            except IndexError:
                time.sleep(1)
                continue
            break
        logger.debug(schreiben) # nur relevant wenn nicht als Dienst gestartet. Man sieht die aktuelle Logzeile
        
        time.sleep(delay)

except KeyboardInterrupt:
    logger.info('WLANThermo stopped!')
    logging.shutdown()
    os.unlink(pidfilename)
