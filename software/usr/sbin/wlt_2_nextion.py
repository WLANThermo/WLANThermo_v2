#!/usr/bin/python
# coding=utf-8

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
import logging
import pyinotify
import serial
import subprocess
import threading
import re
import signal
import Queue
import traceback
from struct import unpack
import gettext
import termios
import fcntl
import random
import string
import codecs

gettext.install('wlt_2_nextion', localedir='/usr/share/WLANThermo/locale/', unicode=True)

NX_lf = '\xff\xff\xff'
NX_channel = 0
NX_page = 0
NX_enhanced = False

version = '0.24'

temps = dict()
channels = dict()
pitmaster = dict()
pitconf = dict()

# Events werden vom Display asynchron gesendet
NX_eventq = Queue.Queue()
# Returns werden auf Anforderung zurückgegeben
NX_returnq = Queue.Queue()

# Lock für das schreiben in die Konfig
configfile_lock = threading.Lock()

# Neue Temperaturen
temps_event = threading.Event()
# Neue Kanalkonfiguration (= geändertes Konfigfile)
channels_event = threading.Event()
# Neue Pitmasterevents
pitmaster_event = threading.Event()
# Neue Pitmasterevents
pitmaster2_event = threading.Event()
# Neue Pitmasterkonfiguration (= geändertes Konfigfile)
pitconf_event = threading.Event()
# Neue Pitmasterkonfiguration (= geändertes Konfigfile)
pitconf2_event = threading.Event()
# Neue Localekonfiguration (= geändertes Konfigfile)
config_event = threading.Event()
# Event für ein Aufwachen aus dem Sleep-Mode (= geändertes Konfigfile)
NX_wake_event = threading.Event()
# Stop des Prozesses wurde angefordert
stop_event = threading.Event()

# Konfigurationsdatei einlesen
configdefaults = {'dim' : '90',
'timeout': '30',
'serialdevice': '/dev/serial0',
'serialspeed': '115200'}

configfile = '/var/www/conf/WLANThermo.conf'
Config = ConfigParser.SafeConfigParser(configdefaults)

# Wir laufen als root, auch andere müssen die Config schreiben!
os.umask (0)

for i in range(0,5):
    while True:
        try:
            Config.readfp(codecs.open(configfile, 'r', 'utf_8'))
        except IndexError:
            # Auf Event warten geht hier noch nicht, da wir die anderen Pfade aus der Config brauchen
            # Logging geht auch noch nicht, da wir das Logfile brauchen, als an StdErr
            sys.stderr.write(_(u'Waiting for configuration file'))
            time.sleep(1)
            continue
        break

# Logging initialisieren
LOGFILE = Config.get('daemon_logging', 'log_file')
logger = logging.getLogger('WLANthermoNEXTION')

#Define Logging Level by changing >logger.setLevel(logging.LEVEL_YOU_WANT)< available: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = Config.get('daemon_logging', 'level_DISPLAY')
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
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logging.captureWarnings(True)

# Pfad fuer die Übergabedateien auslesen
curPath, curFile = os.path.split(Config.get('filepath','current_temp'))
pitPath, pitFile = os.path.split(Config.get('filepath','pitmaster'))
pit2Path, pit2File = os.path.split(Config.get('filepath','pitmaster2'))
confPath, confFile = os.path.split(configfile)

# Wenn das display Verzeichniss im Ram Drive nicht exisitiert erstelle es
if not os.path.exists(curPath):
    os.makedirs(curPath)


class FileEvent(pyinotify.ProcessEvent):
    def process_IN_CLOSE_WRITE(self, event):
        global temps, channels, pitmaster, pitconf, Config, configfile
        global temps_event, channels_event, pitmaster_event, pitconf_event, logger
        logger.debug("IN_CLOSE_WRITE: %s " % os.path.join(event.path, event.name))
        if event.path == curPath and event.name == curFile:
            logger.debug(_(u'New temperature values available'))
            temps_event.set()
        elif event.path == confPath and event.name == confFile:
            logger.debug(_(u'New configuration data available'))
            channels_event.set()
            pitconf_event.set()
            config_event.set()
        elif event.path == pitPath and event.name == pitFile:
            logger.debug(_(u'New pitmaster data available'))
            pitmaster_event.set()
        elif event.path == pit2Path and event.name == pit2File:
            logger.debug(_(u'New pitmaster data available'))
            pitmaster2_event.set()
    
    def process_IN_MOVED_TO(self, event):
        global temps, channels, pitmaster, pitconf, Config, configfile
        global temps_event, channels_event, pitmaster_event, pitconf_event, logger
        logger.debug("IN_MOVED_TO: %s " % os.path.join(event.path, event.name))
        if event.path == curPath and event.name == curFile:
            logger.debug(_(u'New temperature values available'))
            temps_event.set()
        elif event.path == confPath and event.name == confFile:
            logger.debug(_(u'New configuration data available'))
            channels_event.set()
            pitconf_event.set()
            pitconf2_event.set()
            config_event.set()
        elif event.path == pitPath and event.name == pitFile:
            logger.debug(_(u'New pitmaster data available'))
            pitmaster_event.set()
        elif event.path == pit2Path and event.name == pit2File:
            logger.debug(_(u'New pitmaster 2 data available'))
            pitmaster2_event.set()

def NX_reader():
    global logger, ser, NX_returns, NX_events, stop_event, NX_wake_event
    logger.info('Reader thread has been started')
    # Timeout setzen, damit der Thread gestoppt werden kann
    ser.timeout = 0.1
    # Dauerschleife, bricht ab wenn ein stop_event vorlieg
    while not stop_event.is_set():
        is_return = False
        endcount = 0
        bytecount = 0
        message = {'raw' : '', 'iserr' : False, 'errmsg' : '', 'data' : {}, 'type': ''}
        
        while (endcount != 3):
            try:
                byte = ser.read()
            except termios.error, e:
                logger.error(_(u'termios.error in NX_reader: {}').format(e[1]))
            if byte != '':
                # Kein Timeout
                bytecount += 1
                message['raw'] += byte[0]
                if (byte[0] == '\xff'):
                    endcount += 1
                else:
                    endcount = 0
            else:
                # Timeout, sollen wir stoppen?
                if stop_event.is_set():
                    break
        if stop_event.is_set():
            break
        # errmsg taken from ITEAD website, not translated
        elif (message['raw'][0] == '\x00'):
            message['type'] = 'inv_instr'
            message['iserr'] = True
            message['errmsg'] = 'Invalid instruction'
            is_return = True
        elif (message['raw'][0] == '\x01'):
            message['type'] = 'ok'
            message['errmsg'] = 'Successful execution of instruction'
            is_return = True
        elif (message['raw'][0] == '\x03'):
            message['type'] = 'inv_pageid'
            message['iserr'] = True
            message['errmsg'] = 'Page ID invalid'
            is_return = True
        elif (message['raw'][0] == '\x04'):
            message['type'] = 'inv_pictid'
            message['iserr'] = True
            message['errmsg'] = 'Picture ID invalid'
            is_return = True
        elif (message['raw'][0] == '\x05'):
            message['type'] = 'inv_fontid'
            message['iserr'] = True
            message['errmsg'] = 'Font ID invalid'
            is_return = True
        elif (message['raw'][0] == '\x11'):
            message['type'] = 'inv_baudrate'
            message['iserr'] = True
            message['errmsg'] = 'Baud rate setting invalid'
            is_return = True
        elif (message['raw'][0] == '\x12'):
            message['type'] = 'inv_curve'
            message['iserr'] = True
            message['errmsg'] = 'Curve control ID number or channel number is invalid'
            is_return = True
        elif (message['raw'][0] == '\x1a'):
            message['type'] = 'inv_varname'
            message['iserr'] = True
            message['errmsg'] = 'Variable name invalid '
            is_return = True
        elif (message['raw'][0] == '\x1B'):
            message['type'] = 'inv_varop'
            message['iserr'] = True
            message['errmsg'] = 'Variable operation invalid'
            is_return = True
        elif (message['raw'][0] == '\x65'):
            message['type'] = 'touch_event'
            message['errmsg'] = 'Touch event return data'
            message['data'] = {'page': unpack('B', message['raw'][1])[0], 'button': unpack('B', message['raw'][2])[0], 'event':['release', 'press'][unpack('B', message['raw'][3])[0]]}
        elif (message['raw'][0] == '\x66'):
            message['type'] = 'current_page'
            message['errmsg'] = 'Current page ID number return'
            message['data'] = {'page': unpack('B',message['raw'][1])[0]}
        elif (message['raw'][0] == '\x67'):
            message['type'] = 'touch_coord'
            message['errmsg'] = 'Touch coordinate data returns'
            message['data'] = {'x': unpack('>h', message['raw'][1:3])[0],'y': unpack('>h', message['raw'][3:5])[0], 'event':['release', 'press'][unpack('B', message['raw'][5])[0]]}
        elif (message['raw'][0] == '\x68'):
            message['type'] = 'touch_coord_sleep'
            message['errmsg'] = 'Touch Event in sleep mode'
            message['data'] = {'x': unpack('>h', message['raw'][1:3])[0] ,'y': unpack('>h', message['raw'][3:5])[0], 'event':['release', 'press'][unpack('B', message['raw'][5])[0]]}
        elif (message['raw'][0] == '\x70'):
            message['type'] = 'data_string'
            message['errmsg'] = 'String variable data returns'
            message['data'] = unpack((str(bytecount - 4)) + 's', message['raw'][1:-3])[0]
            is_return = True
        elif (message['raw'][0] == '\x71'):
            message['type'] = 'data_int'
            message['errmsg'] = 'Numeric variable data returns'
            message['data'] = unpack('<i', message['raw'][1:5])[0]
            is_return = True
        elif (message['raw'][0] == '\x86'):
            message['type'] = 'sleep'
            message['errmsg'] = 'Device automatically enters into sleep mode'
            NX_wake_event.clear()
        elif (message['raw'][0] == '\x87'):
            message['type'] = 'wakeup'
            message['errmsg'] = 'Device automatically wake up'
            # Device ist aufgewacht...
            NX_wake_event.set()
        elif (message['raw'][0] == '\x88'):
            message['type'] = 'startup'
            message['errmsg'] = 'System successful start up'
        elif (message['raw'][0] == '\x89'):
            message['type'] = 'sdupgrade'
            message['errmsg'] = 'Start SD card upgrade'
        # Selbst definierte Kommandos
        elif (message['raw'][0] == '\x40'):
            message['type'] = 'read_cmd'
            message['errmsg'] = 'Request to read from Display'
            message['data'] = {'area': unpack('B', message['raw'][1])[0], 'id': unpack('B', message['raw'][2])[0]}
        elif (message['raw'][0] == '\x41'):
            message['type'] = 'custom_cmd'
            message['errmsg'] = 'Execute Special Command'
            message['data'] = {'area': unpack('B', message['raw'][1])[0], 'id': unpack('B', message['raw'][2])[0], 'action': unpack('B', message['raw'][3])[0]}
            logger.debug('Area: ' + str(message['data']['area']) + ' ID: ' + str(message['data']['id']) + ' Action: ' + str(message['data']['action']))
        
        logger.debug(_(u'Received message of type {type} from the Display').format(type=message['type']))
        
        if (is_return):
            NX_returnq.put(message)
        else:
            NX_eventq.put(message)
            
    logger.info(_(u'Reader thread has been stopped'))
    return True


def NX_waitok():
    endcount = 0
    bytecount = 0
    ok = False
    byte = ''

    while endcount != 3:
        try:
            byte = ser.read()
        except termios.error, e:
            logger.error(_(u'termios.error in NX_waitok: {}').format(e[1]))
        
        if byte == '':
            logger.info(_(u'Serial Communication Timeout!'))
            break
        bytecount += 1
        if (byte[0] == '\xff'):
            endcount += 1
        elif (byte[0] == '\x01' and bytecount == 1):
            endcount = 0
            ok = True
        else:
            endcount = 0
            
    if ok == True:
        return True
    else:
        return False


def set_hwclock():
    localtime = time.localtime()
    return NX_sendvalues({'rtc0':localtime[0], 'rtc1':localtime[1], 'rtc2':localtime[2], 'rtc3':localtime[3], 'rtc4':localtime[4], 'rtc5':localtime[5]})


def check_ntp():
    ntp = False
    ntpstat = subprocess.Popen("/usr/bin/ntpstat", stdout=subprocess.PIPE, universal_newlines=True)
    stdoutdata, stderrdata = ntpstat.communicate()
    for line in stdoutdata.splitlines():
        if 'synchronised to NTP server' in line:
            return True
    return False


def NX_init(port, baudrate):
    global ser, NX_lf, NX_reader_thread
    try:
        ser.port = port
        ser.baudrate = baudrate
        ser.timeout = 0.2
        ser.open()
        logger.debug(_(u'Locking serial port'))
        fcntl.flock(ser.fileno(), fcntl.LOCK_EX)
        logger.debug(_(u'Clear serial buffer'))
        # Buffer des Displays leeren
        # - Ungültigen Befehl senden
        # - Aufwachbefehl senden
        ser.write('nop' + NX_lf)
        ser.write('sleep=0' + NX_lf)
        # - Warten
        ser.flush()
        time.sleep(0.2)
        # - Empfangene Zeichen löschen
        ser.flushInput()
        # Immer eine Rückmeldung erhalten
        ser.write('ref 0' + NX_lf)
        ser.flush()
    except termios.error, e:
        logger.error(_(u'termios.error in NX_init: {}').format(e[1]))
        
    return NX_waitok()


def NX_sendvalues(values):
    global ser, NX_lf, NX_returnq, NX_wake_event
    
    systemvars = ['rtc0', 'rtc1', 'rtc2', 'rtc3', 'rtc4', 'rtc5', 'rtc6', 'dim', 'dims']
    # NX_sendcmd('sleep=0')
    error = False
    for rawkey, value in values.iteritems():
        # Länge wird im Key mit codiert "key:länge"
        keys = rawkey.split(':')
        key = keys[0]
        if len(keys) == 2:
            length = int(keys[1])
        else:
            length = None
        # Sendet die Daten zum Display und wartet auf eine Rückmeldung
        logger.debug(_(u'Sending {key} to the display: {value}').format(key=key, value=str(value).decode('iso-8859-1')))
        try:
            if key[-3:] == 'txt':
                try:
                    value = str(float(value))
                    if '.' in value:
                        value = value.rstrip('0').rstrip('.')
                except ValueError:
                    value = str(value)
                ser.write(str(key) + '="' + value[:length] + '"\xff\xff\xff')
            elif key[-3:]  == 'val' or key in systemvars:
                ser.write(str(key) + '=' + str(value) + '\xff\xff\xff')
            else:
                logger.warning(_(u'Unknown type of variable'))
            ser.flush()
        except termios.error, e:
            logger.error(_(u'termios.error in NX_sendvalues: {}').format(e[1]))
            
        try:
            ret = NX_returnq.get(timeout=1)
        except Queue.Empty:
            logger.warning(_(u'Timeout - display possibly in sleep mode'))
            error = True
            break
        else:
            NX_returnq.task_done()
            if ret['iserr']:
                logger.warning(_(u'Received error message {} from the display').format(ret['type']))
                error = True
            else:
                logger.debug(_(u'Received message {} from the display').format(ret['type']))
    
    if error:
        return False
    return True


def NX_getvalues(ids):
    global ser, NX_lf, NX_returnq
    error = False
    returnvalues = dict()
    try:
        while True:
            ret = NX_returnq.get(False)
            logger.info(_(u'Received unexpected message {} from the display (out of the display program)').format(ret['type']))
    except Queue.Empty:
        for value_id in ids:
        # Sendet die Daten zum Display und wartet auf eine Rückmeldung
            logger.debug(_(u'Get {} from the display').format(str(value_id)))
            try:
                ser.write('get ' + str(value_id) + '\xff\xff\xff')
                ser.flush()
            except termios.error, e:
                logger.error(_(u'termios.error in NX_getvalues: {}').format(e[1]))
                
            try:
                ret = NX_returnq.get(0.5)
                NX_returnq.task_done()
                if ret['iserr']:
                    logger.warning(_(u'Received error message {} from the display').format(ret['type']))
                    error = True
                else:
                    # Gehen wir von einem "OK" aus, was sonst?
                    logger.debug(_(u'Received message {} from the display').format(ret['type']))
                    # OK, dann Daten abholen
                    if ret['type'] == 'data_string':
                        logger.debug(_(u'Got string {} from the display').format(ret['data']).decode('iso-8859-1'))
                    elif ret['type'] == 'data_int':
                        logger.debug(_(u'Got integer {} from the display').format(ret['data']))
                    else:
                        logger.info(_(u'Received unexpected message {} from the display').format(ret['type']))
                        
                if not error:
                    returnvalues[value_id] = ret['data']
                    error = True
            except Queue.Empty:
                logger.warning(_(u'Received no answer from the display'))
                error = True
    return returnvalues


def NX_getvalue(value_id):
    global ser, NX_lf, NX_returnq
    error = False
    # Sendet die Daten zum Display und wartet auf eine Rückmeldung
    logger.debug(_(u'Get {} from the display').format(str(value_id)))
    
    try:
        while True:
            ret = NX_returnq.get(False)
            logger.info(_(u'Received unexpected message {} from the display (out of the display program)').format(ret['type']))
    except Queue.Empty:
        try:
            ser.write('get ' + str(value_id) + '\xff\xff\xff')
            ser.flush()
        except termios.error, e:
            logger.error(_(u'termios.error in NX_getvalues: {}').format(e[1]))
            
        try:
            ret = NX_returnq.get(True, 0.5)
            NX_returnq.task_done()
            if ret['iserr']:
                logger.warning(_(u'Received error message {} from the display').format(ret['type']))
                error = True
            else:
                # OK, dann Daten abholen
                if ret['type'] == 'data_string':
                    logger.debug(_(u'Got string {} from the display').format(ret['data']).decode('iso-8859-1'))
                elif ret['type'] == 'data_int':
                    logger.debug(_(u'Got integer {} from the display').format(ret['data']))
                else:
                    logger.info(_(u'Received unexpected message {} from the display').format(ret['type']))
        except Queue.Empty:
            logger.warning(_(u'Received no answer from the display'))
            error = True
        
    if not error:
        return ret['data']
    else:
        return None


def NX_sendcmd(cmd):
    global ser, NX_returnq
    error = False
    # Sendet die Daten zum Display und wartet auf eine Rückmeldung
    logger.debug(_(u'Send command {} to the display').format(str(cmd)))
    try:
        while True:
            ret = NX_returnq.get(False)
            logger.info(_(u'Received unexpected message {} from the display (out of the display program)').format(ret['type']))
            NX_returnq.task_done()
    except Queue.Empty:
        try:
            ser.write(str(cmd) + '\xff\xff\xff')
            ser.flush()
            ret = NX_returnq.get(True, 0.5)
            NX_returnq.task_done()
            if ret['iserr']:
                logger.warning(_(u'Received error message {} from the display').format(ret['type']))
                error = True
            else:
                logger.debug(_(u'Received message {} from the display'.format(ret['type'])))
        except Queue.Empty:
            logger.warning(_(u'Received no answer from the display'))
            error = True
        except termios.error, e:
            logger.error(_(u'termios.error in NX_sendcmd: {}').format(e[1]))
            error = True
    if error:
        return False
    return True


def NX_switchpage(new_page):
    global ser, NX_returnq, NX_page
    error = False
    logger.debug(_(u'Send page command to ') + str(new_page))
    try:
        while True:
            ret = NX_returnq.get(False)
            logger.info(_(u'Received unexpected message {} from the display (out of the display program)').format(ret['type']))
    except Queue.Empty:
        try:
            ser.write('page ' + str(new_page) + '\xff\xff\xff')
            ser.flush()
            ret = NX_returnq.get(True, 0.5)
            if ret['iserr']:
                logger.error(_(u'Received error message {} from the display').format(ret['type']))
                error = True
            else:
                logger.debug(_(u'Received message {} from the display'.format(ret['type'])))
        except Queue.Empty:
            logger.warning(_(u'Received no answer from the display'))
            error = True
        except termios.error, e:
            logger.error(_(u'termios.error in NX_switchpage: {}').format(e[1]))
            error = True
    if error:
        return False
    NX_page = new_page
    return True


def sensors_getvalues():
    sensors = dict()
    sensorconfig =  ConfigParser.SafeConfigParser()
    sensorconfig.read('/var/www/conf/sensor.conf')
    for section in sensorconfig.sections():
        sensors[sensorconfig.getint(section, 'number')] = dict()
        sensors[sensorconfig.getint(section, 'number')]['name'] = sensorconfig.get(section, 'name')
    return sensors


def temp_getvalues(channel_count):
    global logger, curPath, curFile
    temps = dict()
    if os.path.isfile(curPath + '/' + curFile):
        logger.debug(_(u'Data from WLANThermo is available to show on the display'))
        ft = codecs.open(curPath + '/' + curFile, 'r', 'utf_8').read()
        temps_raw = ft.split(';')
        temps = dict()
        temps['timestamp'] = time.mktime(time.strptime(temps_raw[0],'%d.%m.%y %H:%M:%S'))
        for count in range(channel_count):
            try:
                alert = temps_raw[count + channel_count + 1]
            except IndexError:
                alert = 'er'
            try:
                if temps_raw[count+1] == '':
                    value = None
                else:
                    try:
                        value = str(round(float(temps_raw[count+1]),1))
                    except ValueError:
                        value = None
            except IndexError:
                value = None
            temps[count] = {'alert': alert, 'value': value}
    else:
        return None
    
    return temps


def config_getvalues():
    global configfile, configfile_lock
    options = {}
    with configfile_lock:
        config = ConfigParser.SafeConfigParser()
        config.readfp(codecs.open(configfile, 'r', 'utf_8'))
    
    options['hw_version'] = config.get('Hardware','version')
    options['max31855'] = config.getboolean('Hardware', 'max31855')
    options['maverick_enabled'] = config.getboolean('ToDo','maverick_enabled')
    options['locale'] = config.get('locale','locale')
    options['temp_unit'] = config.get('locale','temp_unit')
    
    return options


def set_tempflag():
    # Flag Datei für WebGUI anlegen
    open('/var/www/tmp/flag', 'w').close()


def channels_setvalues(channel, high= None, low=None, sensor=None):
    global configfile, configfile_lock
    temp_changed = False
    
    try:
        with configfile_lock:
            newconfig = ConfigParser.SafeConfigParser()
            newconfig.readfp(codecs.open(configfile, 'r', 'utf_8'))
            if low is not None:
                newconfig.set('temp_min','temp_min' + str(channel), str(int(low)))
                temp_changed = True
            if high is not None:
                newconfig.set('temp_max','temp_max' + str(channel), str(int(high)))
                temp_changed = True
            if sensor is not None:
                newconfig.set('Sensoren','ch' + str(channel), str(int(sensor)))
            
            config_write(configfile, newconfig)
        
        if temp_changed:
            set_tempflag()
    
    except ValueError:
        logger.error(_(u'Error while setting channel values'))
        return False


def display_getvalues():
    global configfile, configfile_lock
    defaults = {'dim':'90', 'timeout':'30', 'start_page':'main', 'serialdevice':'/dev/serial0', 'serialspeed':'9600'}
    display = {}
    with configfile_lock:
        config = ConfigParser.SafeConfigParser(defaults)
        config.readfp(codecs.open(configfile, 'r', 'utf_8'))
    
    display['dim'] = config.getint('Display','dim')
    display['timeout'] = config.getint('Display','timeout')
    display['start_page'] = config.get('Display','start_page')
    display['serialdevice'] = Config.get('Display', 'serialdevice')
    display['serialspeed'] = Config.getint('Display', 'serialspeed')
    
    return display


def display_setvalues(dim = None, timeout = None):
    global configfile, configfile_lock
    
    try:
        with configfile_lock:
            newconfig = ConfigParser.SafeConfigParser()
            newconfig.readfp(codecs.open(configfile, 'r', 'utf_8'))
            if dim is not None:
                newconfig.set('Display','dim', str(int(dim)))
            if timeout is not None:
                newconfig.set('Display','timeout', str(int(timeout)))
            config_write(configfile, newconfig)
    except ValueError:
        logger.error(_(u'Error while setting display values'))
        return False


def todo_setvalues(create_new_log = None, pi_down = None, pi_reboot = None):
    global configfile, configfile_lock
    with configfile_lock:
        newconfig = ConfigParser.SafeConfigParser()
        newconfig.readfp(codecs.open(configfile, 'r', 'utf_8'))
        if pi_down is not None:
            newconfig.set('ToDo','raspi_shutdown', ['False', 'True'][pi_down])
        if pi_reboot is not None:
            newconfig.set('ToDo','raspi_reboot', ['False', 'True'][pi_reboot])
        if create_new_log is not None:
            newconfig.set('ToDo','create_new_log', ['False', 'True'][create_new_log])
        config_write(configfile, newconfig)


def pitmaster_setvalues(id = 0, pit_ch = None, pit_set = None, pit_lid=  None, pit_on = None, pit_pid = None, pit_type = None, pit_inverted = None):
    global configfile, configfile_lock

    if id > 0:
        instance_string = str(id + 1)
    else:
        instance_string = ''

    try:
        with configfile_lock:
            newconfig = ConfigParser.SafeConfigParser()
            newconfig.readfp(codecs.open(configfile, 'r', 'utf_8'))
            if pit_ch is not None:
                newconfig.set('Pitmaster' + instance_string, 'pit_ch', str(int(pit_ch)))
            if pit_inverted is not None:
                newconfig.set('Pitmaster' + instance_string, 'pit_inverted', ['False', 'True'][int(pit_inverted)])
            if pit_set is not None:
                newconfig.set('Pitmaster' + instance_string, 'pit_set', str(float(pit_set)))
            if pit_lid is not None:
                newconfig.set('Pitmaster' + instance_string, 'pit_open_lid_detection', ['False', 'True'][int(pit_lid)])
            if pit_on is not None:
                newconfig.set('ToDo','pit' + instance_string + '_on', ['False', 'True'][int(pit_on)])
            if pit_pid is not None:
                newconfig.set('Pitmaster' + instance_string, 'pit_controller_type', ['False', 'PID'][int(pit_pid)])
            if pit_type is not None:
                newconfig.set('Pitmaster' + instance_string, 'pit_type', ['fan', 'servo', 'io', 'io_pwm', 'fan_pwm', 'damper'][int(pit_type)])
                
            config_write(configfile, newconfig)
    except ValueError:
        logger.error(_(u'Error while setting pitmaster values'))
        return False


def channels_getvalues():
    global logger, configfile, configfile_lock
    logger.debug(_(u'Get channel configuration from config file'))
    channels = {}
    with configfile_lock:
        Config = ConfigParser.SafeConfigParser()
        Config.readfp(codecs.open(configfile, 'r', 'utf_8'))
    for i in range(12):
        channel = {}
        channel['sensor'] = Config.getint('Sensoren', 'ch' + str(i))
        channel['logging'] = Config.getboolean('Logging', 'ch' + str(i))
        channel['web_alert'] = Config.getboolean('web_alert', 'ch' + str(i))
        channel['name'] = Config.get('ch_name', 'ch_name' + str(i))
        channel['show'] = Config.getboolean('ch_show', 'ch' + str(i))
        channel['temp_min'] = Config.getfloat('temp_min', 'temp_min' + str(i))
        channel['temp_max'] = Config.getfloat('temp_max', 'temp_max' + str(i))
        channels[i] = channel
    return channels


def pitmaster_config_getvalues(id = 0):
    global configfile, configfile_lock

    if id > 0:
        instance_string = str(id + 1)
    else:
        instance_string = ''

    pitconf = dict()
    with configfile_lock:
        Config = ConfigParser.SafeConfigParser()
        Config.readfp(codecs.open(configfile, 'r', 'utf_8'))
    pitconf['on'] = Config.getboolean('ToDo','pit' + instance_string + '_on')
    pitconf['type'] = Config.get('Pitmaster' + instance_string,'pit_type')
    pitconf['inverted'] = Config.getboolean('Pitmaster' + instance_string,'pit_inverted')
    pitconf['curve'] = Config.get('Pitmaster' + instance_string,'pit_curve')
    pitconf['set'] = Config.getfloat('Pitmaster' + instance_string,'pit_set')
    pitconf['ch'] = Config.getint('Pitmaster' + instance_string,'pit_ch')
    pitconf['pause'] = Config.getfloat('Pitmaster' + instance_string,'pit_pause')
    pitconf['pwm_min'] = Config.getfloat('Pitmaster' + instance_string,'pit_pwm_min')
    pitconf['pwm_max'] = Config.getfloat('Pitmaster' + instance_string,'pit_pwm_max')
    pitconf['man'] = Config.getfloat('Pitmaster' + instance_string,'pit_man')
    pitconf['Kp'] = Config.getfloat('Pitmaster' + instance_string,'pit_kp')
    pitconf['Kd'] = Config.getfloat('Pitmaster' + instance_string,'pit_kd')
    pitconf['Ki'] = Config.getfloat('Pitmaster' + instance_string,'pit_ki')
    pitconf['Kp_a'] = Config.getfloat('Pitmaster' + instance_string,'pit_kp_a')
    pitconf['Kd_a'] = Config.getfloat('Pitmaster' + instance_string,'pit_kd_a')
    pitconf['Ki_a'] = Config.getfloat('Pitmaster' + instance_string,'pit_ki_a')
    pitconf['switch_a'] = Config.getfloat('Pitmaster' + instance_string,'pit_switch_a')
    pitconf['controller_type'] = Config.get('Pitmaster' + instance_string,'pit_controller_type')
    pitconf['iterm_min'] = Config.getfloat('Pitmaster' + instance_string,'pit_iterm_min')
    pitconf['iterm_max'] = Config.getfloat('Pitmaster' + instance_string,'pit_iterm_max')
    pitconf['open_lid_detection'] = Config.getboolean('Pitmaster' + instance_string,'pit_open_lid_detection')
    pitconf['open_lid_pause'] = Config.getfloat('Pitmaster' + instance_string,'pit_open_lid_pause')
    pitconf['open_lid_falling_border'] = Config.getfloat('Pitmaster' + instance_string,'pit_open_lid_falling_border')
    pitconf['open_lid_rising_border'] = Config.getfloat('Pitmaster' + instance_string,'pit_open_lid_rising_border')
    
    return pitconf
    


def pitmaster_getvalues(id):
    global logger, pitPath, pitFile

    if id == 0:
        filename = pitPath + '/' + pitFile
    elif id == 1:
        filename = pit2Path + '/' + pit2File
    else:
        return None

    if os.path.isfile(filename):
        logger.debug(_(u'Data from the pitmaster is available to show on the display'))
        fp = codecs.open(filename, 'r', 'utf_8').read()
        pitmaster_raw = fp.split(';',4)
        # Es trägt sich zu, das im Lande WLANThermo manchmal nix im Pitmaster File steht
        # Dann einfach munter so tun als ob einfach nix da ist
        #TODO Fix everything
        if pitmaster_raw[0] == '':
            return None
        else:
            timestamp = time.mktime(time.strptime(pitmaster_raw[0],'%d.%m.%y %H:%M:%S'))
        
        if pitmaster_raw[2] == '':
            now = None
        else:
            now = float(pitmaster_raw[2])
            
        pitmaster = {'timestamp': timestamp, 'set': float(pitmaster_raw[1]), 'now': now, 'new': float(pitmaster_raw[3].rstrip('%')),'msg': pitmaster_raw[4]}
        
    else:
        return None
    
    return pitmaster


def lan_getvalues():
    interfacelist = ['eth0', 'eth1', 'wlan0', 'wlan1']
    interfaces = dict()
    for interface in interfacelist:
        retvalue = os.popen("LANG=C ifconfig {} 2>/dev/null | awk '/inet / {{print $2}}'".format(interface).readlines()
        if (len(retvalue)!=0):
            interfaces[interface] = {'name': interface, 'ip': retvalue[0].strip()}
    return interfaces


def wlan_getsignal(interface):
    logger.debug(_(u'Get signal strength for: {}').format(interface))
    retvalue = os.popen("LANG=C iwconfig " + interface + " 2>/dev/null").readlines()
    for line in retvalue:
        if 'Link Quality=' in line:
            quality = re.match('.*Link Quality=(\S*)',line).group(1)
            if '/' in quality:
                (val, div) = quality.split('/')
                quality = int(round(float(val) / float(div) * 100.0))
            return quality
    return None


def wlan_getssids():
    ssidlist = os.popen("iwlist wlan0 scan").readlines()
    ssids = list()
    for line in ssidlist:
        if "ESSID:" in line:
            ssid = re.match('.*ESSID:"(.*)"',line).group(1)
            if not ssid in ssids:
                ssids.append(ssid)
    return ssids


def wlan_reconnect():
    os.system('ifdown wlan0')
    time.sleep(1)
    os.system('ifup wlan0')


def wlan_setpassphrase(ssid, psk):
    logger.debug(_(u'Set WPA Passphrase for: {}').format(ssid))
    fw = file('/etc/wpa_supplicant/wpa_supplicant.conf').readlines()
    ssids = list()
    psks = list()
    ssid_found = False
    tmp_filename = get_random_filename('/etc/wpa_supplicant/wpa_supplicant.conf')
    
    for line in fw:
        if re.search(r'^\s*SSID',line,re.IGNORECASE + re.MULTILINE):
            ssids.append(line.split("=")[1].replace('"','').strip())
        elif re.search(r'^\s*\#psk',line,re.IGNORECASE + re.MULTILINE):
            psks.append(line.split("=")[1].replace('"','').strip())
    wpa_file = open(tmp_filename, 'w')
    wpa_file.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n')
    wpa_file.write('update_config=1\n')
    
    if ssids:
        for i in range(len(ssids)):
            logger.debug(_(u'Writing wpa_supplicant.conf for SSID: {}').format(ssids[i]))
            if ssid == ssids[i]:
                # Wert verändert
                logger.debug(_(u'SSID exists already in the configuration file, change PSK'))
                wpa_passphrase = subprocess.Popen(("/usr/bin/wpa_passphrase", str(ssid), str(psk)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readlines()
                ssid_found = True
            else:
                # neue SSID
                logger.debug(_(u'SSID and PSK taken from old configuration file'))
                wpa_passphrase = subprocess.Popen(("/usr/bin/wpa_passphrase", str(ssids[i]), str(psks[i])), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readlines()
                if wpa_passphrase[0] != "Passphrase must be 8..63 characters":
                    for line in wpa_passphrase:
                        wpa_file.write(line)
                else:
                    logger.warning(_(u'New PSK to short for SSID: {}').format(ssid))
    if not ssid_found:
        # SSID nicht in konfigurierten WLANs, das neue hinzufügen
        logger.debug(_(u'Writing wpa_supplicant.conf for SSID: {}').format(ssid))
        wpa_passphrase = subprocess.Popen(("/usr/bin/wpa_passphrase", str(ssid), str(psk)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readlines()
        if wpa_passphrase[0] != "Passphrase must be 8..63 characters":
            for line in wpa_passphrase:
                wpa_file.write(line)
        else:
            logger.warning(_(u'New PSK to short for SSID: {}').format(ssid))
    wpa_file.flush()
    os.fsync(wpa_file.fileno())
    wpa_file.close()
    os.rename(tmp_filename, '/etc/wpa_supplicant/wpa_supplicant.conf')
    return True


def alert_setack():
    try:
        os.mknod('/var/www/alert.ack')
    except OSError:
        pass


def check_reboot():
    logger.debug(_(u'Check for reboot:'))
    lines = subprocess.Popen(["/bin/systemctl", "list-jobs"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, preexec_fn=preexec_function()).stdout.readlines()
    for line in lines:
        if re.search(r'reboot\.target.*start', line) is not None:
            logger.debug(_(u'Reboot detected'))
            return True
    logger.debug(_(u'Shutdown assumed'))
    return False

def NX_display():
    hwclock_nextupdate = 0
    logger.info(_(u'Display thread has been startet'))
    global NX_page, NX_channel, stop_event, NX_eventq
    global temps_event, channels_event, pitmaster_event, pitmasterconfig_event
    global Config
    
    nextion_versions = ['v2.6', 'v2.5', 'v2.4']
    
    # Version des Displays prüfen
    display_version = str(NX_getvalue('main.version.txt'))
    logger.info(_(u'Software version on the display: {}').format(display_version))
    if str(display_version) == nextion_versions[0]:
        # Version on the display is current version
        logger.info(_(u'Display software is on the current level'))
        if os.path.isfile('/var/www/tmp/nextionupdate'):
            # Update-Flag löschen wenn Version i.O.
            os.unlink('/var/www/tmp/nextionupdate')
    elif str(display_version) in nextion_versions:
        # Version is not current, but working
        logger.info(_(u'Display software update is recommended'))
        open('/var/www/tmp/nextionupdate', 'w').close()
    else:
        # Version is not suitable for this script version
        logger.info(_(u'Display software update is required'))
        NX_sendcmd('page update')
        open('/var/www/tmp/nextionupdate', 'w').close()
        stop_event.wait()
        return False
    
    logger.debug(_(u'Get common options...'))
    
    options = config_getvalues()
    if options['temp_unit'] == 'celsius':
        temp_unit = '\xb0C'
    elif options['temp_unit'] == 'fahrenheit':
        temp_unit = '\xb0F'
    else:
        logger.error('Unknown unit of measurement')
        temp_unit = ''
    
    # language = gettext.translation('wlt_2_nextion', localedir='/usr/share/WLANThermo/locale/', languages=[options['locale'] + '.UTF-8'])
    # language.install()

    pitmaster_count = 1
    pitmaster_damper = False
    channel_count = 8
    hwchannel_count = 10

    if options['hw_version'] == 'miniV2':
        pitmaster_count = 2
        pitmaster_damper = True
    elif options['hw_version'] == 'miniplus':
        pitmaster_damper = True

    if options['hw_version'] == 'miniV2' and options['max31855']:
        channel_count += 2
        hwchannel_count += 2
    if options['maverick_enabled'] == True:
        channel_count += 2

    NX_sendvalues({'boot.text.txt:35':_(u'Loading temperature data')})
    NX_switchpage('boot')
    
    # Werte initialisieren
    temps_event.clear()
    channels_event.clear()
    logger.debug(_(u'Get temperature data...'))
    temps = temp_getvalues(hwchannel_count)
    while temps is None:
        logger.info(_(u'Waiting on temperature data'))
        temps_event.wait(0.1)
        temps = temp_getvalues(hwchannel_count)
    
    NX_sendvalues({'boot.text.txt:35':_(u'Loading configuration')})
    
    logger.debug(_(u'Get display configuration...'))
    display = display_getvalues()
    
    logger.debug(_(u'Get sensor configuration...'))
    sensors = sensors_getvalues()
    
    logger.debug(_(u'Get channel configuration...'))
    channels = channels_getvalues()
    
    logger.debug(_(u'Get pitmaster configuration...'))
    pitconf = pitmaster_config_getvalues(0)

    logger.debug(_(u'Get pitmaster 2 configuration...'))
    pitconf2 = pitmaster_config_getvalues(1)

    NX_sendvalues({'boot.text.txt:35':_(u'Loading LAN configuration')})
    
    logger.debug(_(u'Get LAN configuration...'))
    interfaces = lan_getvalues()
    
    # Leere Liste da der Scan etwas dauert...
    ssids = []
    # Zahl des aktuell gewählen Eintrages
    ssids_i = 0
    pitmaster = None
    if pitconf['on']:
        logger.debug(_(u'Get pitmaster data...'))
        pitmaster = pitmaster_getvalues(0)
    # Kann ein wenig dauern, bis valide Daten geliefert werden, daher nicht mehr warten
    if pitmaster is None:
        pitmaster = {'timestamp': 0, 'set': 0, 'now': 0,'new': 0,'msg': ''}

    pitmaster2 = None
    if pitconf2['on']:
        logger.debug(_(u'Get pitmaster 2 data...'))
        pitmaster2 = pitmaster_getvalues(1)
    # Kann ein wenig dauern, bis valide Daten geliefert werden, daher nicht mehr warten
    if pitmaster2 is None:
        pitmaster2 = {'timestamp': 0, 'set': 0, 'now': 0,'new': 0,'msg': ''}

    values = dict()
    values['main.chmax.val'] = channel_count
    
    for i in range(1, 11):
        try:
            values['main.sensor_name' + str(i) + '.txt:10'] = sensors[i]['name'].encode('latin-1')
        except KeyError:
            logger.error(_(u'Sensor {} not defined!'.format(i)))
            values['main.sensor_name' + str(i) + '.txt:10'] = '- - -'
    for i in range(hwchannel_count):
        if temps[i]['value'] is None:
            values['main.kanal' + str(i) + '.txt:10'] = ''.encode('latin-1')
        else:
            values['main.kanal' + str(i) + '.txt:10'] = temps[i]['value'] + temp_unit
        values['main.alert' + str(i) + '.txt:10'] = temps[i]['alert']
        values['main.al' + str(i) + 'minist.txt:10'] = channels[i]['temp_min']
        values['main.al' + str(i) + 'maxist.txt:10'] = channels[i]['temp_max']
        values['main.sensor_type' + str(i) + '.val'] = channels[i]['sensor']
        values['main.name' + str(i) + '.txt:10'] = channels[i]['name'].encode('latin-1')
    for interface in interfaces:
        values['wlaninfo.' + interfaces[interface]['name'] + '.txt:20'] = interfaces[interface]['ip']

    pit_types = {'fan':0, 'servo':1, 'io':2, 'io_pwm':3, 'fan_pwm':4, 'damper': 5}

    values['main.pitmaster.val'] = pitmaster_count
    values['main.pit_damper.val'] = 1 if pitmaster_damper else 0

    # Pitmaster 1
    values['main.pit_ch.val'] = int(pitconf['ch'])
    values['main.pit_power.val'] = int(round(pitmaster['new']))
    values['main.pit_set.txt:10'] = round(pitconf['set'],1)
    values['main.pit_lid.val'] = int(pitconf['open_lid_detection'])
    values['main.pit_on.val'] = int(pitconf['on'])
    values['main.pit_inverted.val'] = int(pitconf['inverted'])
    values['main.pit_pid.val'] = {'False': 0, 'PID': 1}[pitconf['controller_type']]
    values['main.pit_type.val'] = pit_types[pitconf['type']]
    # Pitmaster 2
    values['main.pit_ch2.val'] = int(pitconf2['ch'])
    values['main.pit_power2.val'] = int(round(pitmaster2['new']))
    values['main.pit_set2.txt:10'] = round(pitconf2['set'],1)
    values['main.pit_lid2.val'] = int(pitconf2['open_lid_detection'])
    values['main.pit_on2.val'] = int(pitconf2['on'])
    values['main.pit_inverted2.val'] = int(pitconf2['inverted'])
    values['main.pit_pid2.val'] = {'False': 0, 'PID': 1}[pitconf2['controller_type']]
    values['main.pit_type2.val'] = pit_types[pitconf2['type']]

    # Displayeinstellungen sollten lokal sein und nur für uns
    # Ansonsten müsste man hier noch mal ran 
    values['main.dim.val'] = int(display['dim'])
    values['main.timeout.val'] = int(display['timeout'])

    NX_sendvalues({'boot.text.txt:35':_(u'Transferring data')})
    NX_sendvalues(values)
    
    # Ruft die Startseite auf, vorher Text zurücksetzen
    NX_sendvalues({'boot.text.txt:35':_(u'Establishing connection')})
    NX_sendcmd('page ' + display['start_page'])
    NX_wake_event.set()
    
    while not stop_event.is_set():
        # idR werden wir bei einem Sleep hier warten
        while not stop_event.is_set() and not NX_wake_event.wait(timeout = 0.05):
            pass
        if not NX_eventq.empty():
            event = NX_eventq.get(False)
            # Touchevents werden hier behandelt
            if event['type'] == 'current_page' :
                NX_page = event['data']['page']
            elif event['type'] == 'startup':
                # Restart des Displays - sterben und auf Wiedergeburt hoffen
                logger.warning(_(u'Received start-up message from the display, exiting.'))
                return False
            elif event['type'] == 'read_cmd':
                if event['data']['area'] == 0:
                    channel = event['data']['id']
                    low = NX_getvalue('main.al'+ str(channel)+'minist.txt')
                    channels_setvalues(channel, low=low)
                elif event['data']['area'] == 1:
                    channel = event['data']['id']
                    high = NX_getvalue('main.al'+ str(channel)+'maxist.txt')
                    channels_setvalues(channel, high=high)
                elif event['data']['area'] == 2:
                    channel = event['data']['id']
                    sensor = NX_getvalue('main.sensor_type'+ str(channel) + '.val')
                    channels_setvalues(channel, sensor=sensor)
                elif event['data']['area'] == 3:
                    if event['data']['id'] == 0:
                        # pit_ch
                        pit_ch = NX_getvalue('main.pit_ch.val')
                        pitmaster_setvalues(pit_ch = pit_ch)
                    elif event['data']['id'] == 1:
                        # pit_set
                        pit_set = NX_getvalue('main.pit_set.txt')
                        pitmaster_setvalues(pit_set = pit_set)
                    elif event['data']['id'] == 2:
                        # pit_lid
                        pit_lid = NX_getvalue('main.pit_lid.val')
                        pitmaster_setvalues(pit_lid = pit_lid)
                    elif event['data']['id'] == 3:
                        # pit_on
                        pit_on = NX_getvalue('main.pit_on.val')
                        pitmaster_setvalues(pit_on = pit_on)
                    elif event['data']['id'] == 4:
                        # pit_pid
                        pit_pid = NX_getvalue('main.pit_pid.val')
                        pitmaster_setvalues(pit_pid = pit_pid)
                    elif event['data']['id'] == 5:
                        # pit_type
                        pit_type = NX_getvalue('main.pit_type.val')
                        pitmaster_setvalues(pit_type = pit_type)
                    elif event['data']['id'] == 6:
                        # pit_inverted
                        pit_inverted = NX_getvalue('main.pit_inverted.val')
                        pitmaster_setvalues(pit_inverted = pit_inverted)
                elif event['data']['area'] == 4:
                    if event['data']['id'] == 0:
                        # dim
                        dim = NX_getvalue('main.dim.val')
                        display_setvalues(dim = dim)
                    elif event['data']['id'] == 1:
                        # timeout
                        timeout = NX_getvalue('main.timeout.val')
                        display_setvalues(timeout = timeout)
                elif event['data']['area'] == 5:
                    if event['data']['id'] == 0:
                        # pi_down
                        # pi_down = NX_getvalue('main.pi_down.val')
                        todo_setvalues(pi_down = 1)
                    elif event['data']['id'] == 1:
                        # pi_reboot
                        # pi_reboot = NX_getvalue('main.pi_reboot.val')
                        todo_setvalues(pi_reboot = 1)
                    elif event['data']['id'] == 4:
                        # main.password.txt = WLAN konfigurieren
                        wlan_setpassphrase(ssids[ssids_i], NX_getvalue('main.password.txt'))
                        wlan_reconnect()
                        # Sleepmode deaktivierne
                        # NX_sendcmd('thsp=0')
                        # 20s auf Verbindung warten
                        i = 0
                        while i in range(45) and not stop_event.is_set():
                            interfaces = lan_getvalues()
                            if 'wlan0' in interfaces:
                                # wlan0 hat eine IP-Adresse
                                NX_sendvalues({'main.result.txt:20': 'IP:' + interfaces['wlan0']['ip']})
                                NX_sendcmd('page result')
                                for interface in interfaces:
                                    values['wlaninfo.' + interfaces[interface]['name'] + '.txt:20'] = interfaces[interface]['ip']
                                NX_sendvalues(values)
                                break
                            elif i == 44:
                                # wlan0 hat nach 20s noch keine IP-Adresse
                                NX_sendvalues({'main.result.txt:20': _(u'failed')})
                                NX_sendcmd('page result')
                                break
                            else:
                                time.sleep(1)
                                i = i + 1
                        # NX_sendcmd('thsp=' + str(Config.getint('Display', 'timeout')))
                    elif event['data']['id'] == 5:
                        values = dict()
                        interfaces = lan_getvalues()
                        for interface in interfaces:
                            values['wlaninfo.' + interfaces[interface]['name'] + '.txt:20'] = interfaces[interface]['ip']
                        signal = wlan_getsignal('wlan0')
                        values['main.signal.val'] = signal
                        NX_sendvalues(values)
                    elif event['data']['id'] == 6:
                        wlan_reconnect()
                elif event['data']['area'] == 7:
                    if event['data']['id'] == 0:
                        # pit_ch
                        pit_ch = NX_getvalue('main.pit_ch2.val')
                        pitmaster_setvalues(id = 1, pit_ch = pit_ch)
                    elif event['data']['id'] == 1:
                        # pit_set
                        pit_set = NX_getvalue('main.pit_set2.txt')
                        pitmaster_setvalues(id = 1, pit_set = pit_set)
                    elif event['data']['id'] == 2:
                        # pit_lid
                        pit_lid = NX_getvalue('main.pit_lid2.val')
                        pitmaster_setvalues(id = 1, pit_lid = pit_lid)
                    elif event['data']['id'] == 3:
                        # pit_on
                        pit_on = NX_getvalue('main.pit_on2.val')
                        pitmaster_setvalues(id = 1, pit_on = pit_on)
                    elif event['data']['id'] == 4:
                        # pit_pid
                        pit_pid = NX_getvalue('main.pit_pid2.val')
                        pitmaster_setvalues(id = 1, pit_pid = pit_pid)
                    elif event['data']['id'] == 5:
                        # pit_type
                        pit_type = NX_getvalue('main.pit_type2.val')
                        pitmaster_setvalues(id = 1, pit_type = pit_type)
                    elif event['data']['id'] == 6:
                        # pit_inverted
                        pit_inverted = NX_getvalue('main.pit_inverted2.val')
                        pitmaster_setvalues(id = 1, pit_inverted = pit_inverted)
            elif event['type'] == 'custom_cmd':
                if event['data']['area'] == 5:
                    if event['data']['id'] == 0:
                        if event['data']['action'] == 0:
                            logger.debug(_(u'Shutting down...'))
                            todo_setvalues(pi_down = 1)
                    elif event['data']['id'] == 1:
                        if event['data']['action'] == 0:
                            logger.debug(_(u'Rebooting...'))
                            todo_setvalues(pi_reboot = 1)
                    elif event['data']['id'] == 3:
                        if event['data']['action'] == 0:
                            # WLAN scannen
                            logger.debug(_(u'Scanning WLANs'))
                            ssids = wlan_getssids()
                            ssids_i = 0
                            logger.debug('SSIDs:' + str(ssids))
                            if not ssids:
                                NX_sendvalues({'main.ssid.txt:35': _(u'No WLAN found')})
                                NX_sendcmd('page setup')
                            else:
                                NX_sendvalues({'main.ssid.txt:35': ssids[ssids_i]})
                                NX_sendcmd('page ssidselect')
                        elif event['data']['action'] == 1:
                            # voherige SSID
                            if ssids_i <= 0:
                                ssids_i = len(ssids)-1
                            else:
                                ssids_i = ssids_i - 1
                            NX_sendvalues({'main.ssid.txt:35': ssids[ssids_i]})
                        elif event['data']['action'] == 2:
                            # nächste SSID
                            if ssids_i >= len(ssids)-1:
                                ssids_i = 0
                            else:
                                ssids_i = ssids_i + 1
                            NX_sendvalues({'main.ssid.txt:35': ssids[ssids_i]})
                    elif event['data']['id'] == 4:
                        if event['data']['action'] == 0:
                            logger.debug(_(u'Create new logfile!'))
                            todo_setvalues(create_new_log = 1)
                elif event['data']['area'] == 6:
                    if event['data']['id'] == 0:
                        if event['data']['action'] == 0:
                            logger.debug(_(u'Alert acknowledged!'))
                            alert_setack()
            NX_eventq.task_done()
        elif temps_event.is_set():
            logger.debug(_(u'Temperature event'))
            values = dict()
            new_temps = temp_getvalues(hwchannel_count)
            if new_temps is not None:
                temps_event.clear()
                if options['temp_unit'] == 'celsius':
                    temp_unit = '\xb0C'
                elif options['temp_unit'] == 'fahrenheit':
                    temp_unit = '\xb0F'
                else:
                    logger.error(_(u'Unknown unit of measurement'))
                    temp_unit = ''
                for i in range(hwchannel_count):
                    try:
                        if temps[i]['value'] != new_temps[i]['value']:
                            if new_temps[i]['value'] is None:
                                values['main.kanal' + str(i) + '.txt:10'] = ''.encode('latin-1')
                            else:
                                values['main.kanal' + str(i) + '.txt:10'] = new_temps[i]['value'] + temp_unit
                        
                        if temps[i]['alert'] != new_temps[i]['alert']:
                            values['main.alert' + str(i) + '.txt:10'] = new_temps[i]['alert']
                    except KeyError:
                        temps[i] = dict()
                        temps[i]['value'] = None
                        temps[i]['alert'] = ''
                
                if NX_sendvalues(values):
                    temps = new_temps
                else:
                    # Im Fehlerfall später wiederholen
                    temps_event.set()
        
        elif pitconf_event.is_set():
            logger.debug(_(u'Pitmaster configuration event'))
            values = dict()
            
            pitconf_event.clear()
            new_pitconf = pitmaster_config_getvalues(0)
            
            if pitconf['set'] != new_pitconf['set']:
                values['main.pit_set.txt:10'] = round(new_pitconf['set'],1)
            if pitconf['ch'] != new_pitconf['ch']:
                values['main.pit_ch.val'] = int(new_pitconf['ch'])
            if pitconf['open_lid_detection'] != new_pitconf['open_lid_detection']:
                values['main.pit_lid.val'] = int(new_pitconf['open_lid_detection'])
            if pitconf['inverted'] != new_pitconf['inverted']:
                values['main.pit_inverted.val'] = int(new_pitconf['inverted'])
            if pitconf['on'] != new_pitconf['on']:
                values['main.pit_on.val'] = int(new_pitconf['on'])
                if not new_pitconf['on']:
                    values['main.pit_power.val'] = 0
                    pitmaster['new'] = 0
            if pitconf['controller_type'] != new_pitconf['controller_type']:
                values['main.pit_pid.val'] = {'False': 0, 'PID': 1}[new_pitconf['controller_type']]
            if pitconf['type'] != new_pitconf['type']:
                values['main.pit_type.val'] = pit_types[new_pitconf['type']]

            if NX_sendvalues(values):
                pitconf = new_pitconf
            else:
                # Im Fehlerfall später wiederholen
                pitconf_event.set()

        elif pitconf2_event.is_set():
            logger.debug(_(u'Pitmaster configuration event'))
            values = dict()

            pitconf2_event.clear()
            new_pitconf = pitmaster_config_getvalues(1)

            if pitconf2['set'] != new_pitconf['set']:
                values['main.pit_set2.txt:10'] = round(new_pitconf['set'], 1)
            if pitconf2['ch'] != new_pitconf['ch']:
                values['main.pit_ch2.val'] = int(new_pitconf['ch'])
            if pitconf2['open_lid_detection'] != new_pitconf['open_lid_detection']:
                values['main.pit_lid2.val'] = int(new_pitconf['open_lid_detection'])
            if pitconf2['inverted'] != new_pitconf['inverted']:
                values['main.pit_inverted2.val'] = int(new_pitconf['inverted'])
            if pitconf2['on'] != new_pitconf['on']:
                values['main.pit_on2.val'] = int(new_pitconf['on'])
                if not new_pitconf['on']:
                    values['main.pit_power.val'] = 0
                    pitmaster2['new'] = 0
            if pitconf2['controller_type'] != new_pitconf['controller_type']:
                values['main.pit_pid2.val'] = {'False': 0, 'PID': 1}[new_pitconf['controller_type']]
            if pitconf2['type'] != new_pitconf['type']:
                values['main.pit_type2.val'] = pit_types[new_pitconf['type']]

            if NX_sendvalues(values):
                pitconf2 = new_pitconf
            else:
                # Im Fehlerfall später wiederholen
                pitconf2_event.set()

        elif pitmaster_event.is_set():
            logger.debug(_(u'Pitmaster data event'))
            values = dict()
            
            pitmaster_event.clear()
            new_pitmaster = pitmaster_getvalues(0)
            
            if new_pitmaster is not None:
                if pitmaster['new'] != new_pitmaster['new']:
                    if pitconf['on']:
                        # Wenn Pitmaster aus, 0-Wert senden.
                        values['main.pit_power.val'] = int(round(float(new_pitmaster['new'])))
                    else:
                        values['main.pit_power.val'] = 0
                    
                    if NX_sendvalues(values):
                        pitmaster = new_pitmaster
                    else:
                        # Im Fehlerfall später wiederholen
                        pitmaster_event.set()

        elif pitmaster2_event.is_set():
            logger.debug(_(u'Pitmaster 2 data event'))
            values = dict()

            pitmaster2_event.clear()
            new_pitmaster = pitmaster_getvalues(1)

            if new_pitmaster is not None:
                if pitmaster2['new'] != new_pitmaster['new']:
                    if pitconf2['on']:
                        # Wenn Pitmaster aus, 0-Wert senden.
                        values['main.pit_power2.val'] = int(round(float(new_pitmaster['new'])))
                    else:
                        values['main.pit_power2.val'] = 0

                    if NX_sendvalues(values):
                        pitmaster2 = new_pitmaster
                    else:
                        # Im Fehlerfall später wiederholen
                        pitmaster2_event.set()

        elif channels_event.is_set():
            logger.debug(_(u'Channels data event'))
            values = dict()
            
            channels_event.clear()
            new_channels = channels_getvalues()
            
            for i in range(12):
                if channels[i]['temp_min'] != new_channels[i]['temp_min']:
                    values['main.al' + str(i) + 'minist.txt:10'] = new_channels[i]['temp_min']
                if channels[i]['temp_max'] != new_channels[i]['temp_max']:
                    values['main.al' + str(i) + 'maxist.txt:10'] = new_channels[i]['temp_max']
                if channels[i]['sensor'] != new_channels[i]['sensor']:
                    values['main.sensor_type' + str(i) + '.val'] = new_channels[i]['sensor']
                if channels[i]['name'] != new_channels[i]['name']:
                    values['main.name' + str(i) + '.txt:10'] = new_channels[i]['name'].encode('latin-1')
            if NX_sendvalues(values):
                channels = new_channels
            else:
                # Im Fehlerfall später wiederholen
                channels_event.set()
        
        elif config_event.is_set():
            logger.debug(_(u'Config event'))
            config_event.clear()
            check_recalibration()
            
            values = dict()
            
            options = config_getvalues()

            new_pitmaster_count = 1
            new_pitmaster_damper = False
            new_channel_count = 8
            new_hwchannel_count = 10
            if options['hw_version'] == 'miniV2':
                new_pitmaster_count = 2
                new_pitmaster_damper = True
            elif options['hw_version'] == 'miniplus':
                new_pitmaster_damper = True

            if options['hw_version'] == 'miniV2' and options['max31855']:
                new_channel_count += 2
                new_hwchannel_count += 2
            if options['maverick_enabled'] == True:
                new_channel_count += 2
                
            if channel_count != new_channel_count:
                values['main.chmax.val'] = new_channel_count
                channel_count = new_channel_count

            if pitmaster_count != new_pitmaster_count:
                values['main.pitmaster.val'] = pitmaster_count
                pitmaster_count = new_pitmaster_count

            if pitmaster_damper != new_pitmaster_damper:
                values['main.pit_damper.val'] = 1 if pitmaster_damper else 0
                pitmaster_damper = new_pitmaster_damper

            if hwchannel_count != new_hwchannel_count:
                hwchannel_count = new_hwchannel_count

            if not NX_sendvalues(values):
                channels_event.set()
            
        elif time.time() > hwclock_nextupdate:
            if check_ntp():
                logger.info(_(u'Setting RTC'))
                set_hwclock()
                # Update time again in 1h
                hwclock_nextupdate = time.time() + 3600
            else:
                # Try every 5min if ntp is not sync´d
                hwclock_nextupdate = time.time() + 300
                
        else:
            time.sleep(0.01)
    logger.info(_(u'Display thread stopped'))
    return True


def get_random_filename(filename):
    return filename + '_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))


def config_write(configfile, config):
    # Schreibt das Configfile
    # Ein Lock sollte im aufrufenden Programm gehalten werden!
    
    tmp_filename = get_random_filename(configfile)
    with codecs.open(tmp_filename, 'w', 'utf_8') as new_ini:
        for section_name in config.sections():
            new_ini.write(u'[{section_name}]\n'.format(section_name=section_name))
            for (key, value) in config.items(section_name):
                new_ini.write(u'{key} = {value}\n'.format(key=key, value=value))
            new_ini.write('\n')
        new_ini.flush()
        os.fsync(new_ini.fileno())
        new_ini.close()
        os.rename(tmp_filename, configfile)


def check_recalibration():
    global configfile, configfile_lock
    
    calibrate_display = False

    with configfile_lock:
        newconfig = ConfigParser.SafeConfigParser()
        newconfig.readfp(codecs.open(configfile, 'r', 'utf_8'))
        if newconfig.getboolean('ToDo', 'calibrate_display') == True:
            logger.info(_(u'Calibrating Display'))
            NX_sendcmd('touch_j')
            newconfig.set('ToDo', 'calibrate_display', 'False')
            calibrate_display = True
            # We don´t get any useful information back from the display
            # So we don´t know when to start again, try again after 30s
            stop_event.set()
            time.sleep(30)
            config_write(configfile, newconfig)

            time.sleep(1)
            newconfig.set('ToDo', 'restart_display', 'True')
            config_write(configfile, newconfig)

def stop_all(signum, frame):
    logger.debug(_(u'Caught signal: ') + str(signum))
    logger.info(_(u'Sende stop signal to all threads'))
    stop_event.set()


def preexec_function():
    os.setpgrp()


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


sys.excepthook = log_uncaught_exceptions

# Auf geht es
logger.info(_(u'Nextion display started, script version: ') + version)

signal.signal(15, stop_all)
signal.signal(2, stop_all)

#Einlesen der Software-Version
for line in codecs.open('/var/www/header.php', 'r', 'utf_8'):
    if 'webGUIversion' in line:
        build = re.match('.*=\s*"(.*)"', line).group(1)
        break

#ueberpruefe ob der Dienst schon laeuft
pid = str(os.getpid())
pidfilename = '/var/run/'+os.path.basename(__file__).split('.')[0]+'.pid'

if os.access(pidfilename, os.F_OK):
    pidfile = open(pidfilename, "r")
    pidfile.seek(0)
    old_pid = int(pidfile.readline())
    if check_pid(old_pid):
        print(_(u"%s already exists, Process is running, exiting") % pidfilename)
        logger.error(_(u"%s already exists, Process is running, exiting") % pidfilename)
        sys.exit()
    else:
        logger.info(_(u"%s already exists, Process is NOT running, resuming operation") % pidfilename)
        pidfile.seek(0)
        open(pidfilename, 'w').write(pid)
    
else:
    logger.debug(_(u"%s written") % pidfilename)
    open(pidfilename, 'w').write(pid)

# Display initialisieren
logger.debug(_(u'Loading display configuration'))
display = display_getvalues()

logger.debug(_(u'Opening serial port: ') + display['serialdevice'])
ser = serial.Serial()

logger.debug(_(u'Initializing display, baud rate: ') + str(display['serialspeed']))

if NX_init(display['serialdevice'], display['serialspeed']):
    logger.debug(_(u'Initialisation OK'))
    
    logger.debug(_(u'Starting reader thread'))
    NX_reader_thread = threading.Thread(target=NX_reader)
    NX_reader_thread.daemon = True
    try:
        NX_reader_thread.start()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        sys.excepthook(*sys.exc_info())
    
    logger.debug(_(u'Starting display thread'))
    NX_display_thread = threading.Thread(target=NX_display)
    NX_display_thread.daemon = True
    try:
        NX_display_thread.start()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        sys.excepthook(*sys.exc_info())
    
    logger.debug(_(u'Starting file watcher'))
    wm = pyinotify.WatchManager()
    mask = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO
    notifier = pyinotify.ThreadedNotifier(wm, FileEvent())
    try:
        notifier.start()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        sys.excepthook(*sys.exc_info())
        
    wdd = wm.add_watch(curPath, mask)
    wdd2 = wm.add_watch(pitPath, mask)
    wdd3 = wm.add_watch(confPath, mask)
    
    while not stop_event.is_set():
        # Hauptschleife
        if not NX_display_thread.is_alive():
            break
        if not NX_reader_thread.is_alive():
            break
        time.sleep(0.5)
    
    if not NX_wake_event.is_set():
        NX_sendcmd('sleep=0')
        time.sleep(0.2)
    
    if check_reboot():
        NX_sendvalues({'boot.text.txt:35': _(u'System is rebooting...')})
    else:
        NX_sendvalues({'boot.text.txt:35': _(u'System is shutting down...')})
        NX_sendvalues({'boot.nextion_down.val': 1})
    
    NX_switchpage('boot')
    
    notifier.stop()
    # Signal zum stoppen geben

    logger.debug(_(u'Waiting for Threads...'))
    # Auf Threads warten
    NX_display_thread.join()
    NX_reader_thread.join()
    
else:
    logger.error(_(u'Can´t establish connection to the Nextion display'))
    # Vielleicht ist die Software noch nicht auf dem Display installiert
    open('/var/www/tmp/nextionupdate', 'w').close()

logger.info(_(u'Display stopped!'))
logging.shutdown()
os.unlink(pidfilename)
