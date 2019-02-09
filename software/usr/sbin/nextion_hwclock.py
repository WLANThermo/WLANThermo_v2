#!/usr/bin/python3
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
import os
import time
import serial
import termios
import fcntl
from subprocess import Popen, PIPE

from struct import unpack

NX_lf = b'\xff\xff\xff'

# Konfigurationsdatei einlesen
config = {'timeout': '30',
'serialdevice': '/dev/serial0',
'serialspeed': '115200'}

def NX_read():
    global ser
    # Timeout setzen, damit der Thread gestoppt werden kann
    ser.timeout = 5
    is_return = False
    endcount = 0
    bytecount = 0
    message = {'raw' : b'', 'iserr' : False, 'errmsg' : '', 'data' : {}, 'type': ''}
    while (endcount != 3):
        byte = ser.read()
        if byte != b'':
            # Kein Timeout
            bytecount += 1
            message['raw'] += byte
            if (byte[0] == 255):
                endcount += 1
            else:
                endcount = 0
        else:
                break
    try:
        # errmsg taken from ITEAD website, not translated
        if (message['raw'][0] == 0x00):
            message['type'] = 'inv_instr'
            message['iserr'] = True
            message['errmsg'] = 'Invalid instruction'
            message['is_return'] = True
        elif (message['raw'][0] == 0x01):
            message['type'] = 'ok'
            message['errmsg'] = 'Successful execution of instruction'
            message['is_return'] = True
        elif (message['raw'][0] == 0x03):
            message['type'] = 'inv_pageid'
            message['iserr'] = True
            message['errmsg'] = 'Page ID invalid'
            message['is_return'] = True
        elif (message['raw'][0] == 0x04):
            message['type'] = 'inv_pictid'
            message['iserr'] = True
            message['errmsg'] = 'Picture ID invalid'
            message['is_return'] = True
        elif (message['raw'][0] == 0x05):
            message['type'] = 'inv_fontid'
            message['iserr'] = True
            message['errmsg'] = 'Font ID invalid'
            message['is_return'] = True
        elif (message['raw'][0] == 0x11):
            message['type'] = 'inv_baudrate'
            message['iserr'] = True
            message['errmsg'] = 'Baud rate setting invalid'
            message['is_return'] = True
        elif (message['raw'][0] == 0x12):
            message['type'] = 'inv_curve'
            message['iserr'] = True
            message['errmsg'] = 'Curve control ID number or channel number is invalid'
            message['is_return'] = True
        elif (message['raw'][0] == 0x1a):
            message['type'] = 'inv_varname'
            message['iserr'] = True
            message['errmsg'] = 'Variable name invalid '
            message['is_return'] = True
        elif (message['raw'][0] == 0x1B):
            message['type'] = 'inv_varop'
            message['iserr'] = True
            message['errmsg'] = 'Variable operation invalid'
            message['is_return'] = True
        elif (message['raw'][0] == 0x70):
            message['type'] = 'data_string'
            message['errmsg'] = 'String variable data returns'
            message['data'] = unpack((str(bytecount - 4)) + 's', message['raw'][1:-3])[0]
            message['is_return'] = True
        elif (message['raw'][0] == 0x71):
            message['type'] = 'data_int'
            message['errmsg'] = 'Numeric variable data returns'
            message['data'] = unpack('<i', message['raw'][1:5])[0]
            message['is_return'] = True
    except IndexError:
        return False
    
    return message


def NX_waitok():
    endcount = 0
    bytecount = 0
    ok = False

    while endcount != 3:
        byte = ser.read()
        if byte == b'':
            break
        
        bytecount += 1
        if (byte[0] == 255):
            endcount += 1
        elif (byte[0] == 1 and bytecount == 1):
            endcount = 0
            ok = True
        else:
            endcount = 0
            
    if ok == True:
        return True
    else:
        return False


def NX_init(port, baudrate):
    global ser, NX_lf
    ser.port = port
    ser.baudrate = baudrate
    ser.timeout = 0.2
    ser.open()
    
    import fcntl, serial

    try:
        fcntl.flock(ser.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print ('Serial port is busy')
        return False
    # Buffer des Displays leeren
    # - Ungültigen Befehl senden
    # - Aufwachbefehl senden
    ser.write(b'nop' + NX_lf)
    ser.write(b'sleep=0' + NX_lf)
    # - Warten
    ser.flush()
    time.sleep(0.5)
    # - Empfangene Zeichen löschen
    ser.flushInput()
    # Immer eine Rückmeldung erhalten
    ser.write(b'ref 0' + NX_lf)
    ser.flush()
    return NX_waitok()


def NX_sendvalues(values):
    global ser, NX_lf
    # NX_sendcmd('sleep=0')
    error = False
    for rawkey, value in iter(values.items()):
        # Länge wird im Key mit codiert "key:länge"
        keys = rawkey.split(':')
        key = keys[0]
        if len(keys) == 2:
            length = int(keys[1])
        else:
            length = None
        # Sendet die Daten zum Display und wartet auf eine Rückmeldung
        if key[-3:] == 'txt':
            ser.write(str(key).encode('ascii') + b'="' + str(value).encode('ascii')[:length] + b'"\xff\xff\xff')
        else:
            ser.write(str(key).encode('ascii') + b'=' + str(value).encode('ascii') + b'\xff\xff\xff')
        ser.flush()
        while True:
            ret = NX_read()
            if ret == False:
                error = True
                break
            if not ret['is_return']:
                continue
            else:
                if ret['iserr']:
                    error = True
                break
                    
    if error:
        return False
    return True


def NX_getvalues(ids):
    global ser, NX_lf
    error = False
    returnvalues = dict()
    for value_id in ids:
    # Sendet die Daten zum Display und wartet auf eine Rückmeldung
        ser.write(b'get ' + str(value_id).encode('ascii') + b'\xff\xff\xff')
        ser.flush()
        while True:
            ret = NX_read()
            if ret == False:
                break
            else:
                if ret == False:
                    error = True
                    break
                if ret['iserr']:
                    error = True
                else:
                    returnvalues[value_id] = ret['data']
                    break
    return returnvalues

def preexec_function():
    os.setpgrp()


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

#ueberpruefe ob der Dienst schon laeuft
pid = str(os.getpid())
pidfilename = '/var/run/'+os.path.basename(__file__).split('.')[0]+'.pid'

if os.access(pidfilename, os.F_OK):
    pidfile = open(pidfilename, "r")
    pidfile.seek(0)
    old_pid = int(pidfile.readline())
    if check_pid(old_pid):
        print(_("%s already exists, Process is running, exiting") % pidfilename)
        sys.exit()
    else:
        pidfile.seek(0)
        open(pidfilename, 'w').write(pid)
    
else:
    open(pidfilename, 'w').write(pid)

ser = serial.Serial()

if len(sys.argv) < 2:
    sys.exit('Argument needed: start or stop')
else:
    if sys.argv[1].lower() in ('start', 'stop'):
        mode = sys.argv[1].lower()
    else:
        sys.exit('Valid arguments: start or stop')


if NX_init(config['serialdevice'], config['serialspeed']):
    nextion = True
else:
    nextion = False
    print('Error in NEXTION init')
    
ntp = False
with Popen(["/usr/bin/timedatectl", "status"], stdout=PIPE, universal_newlines=True) as ntpstat:
    for line in iter(ntpstat.stdout.readline, ''):
        if 'NTP synchronized: yes' in line:
            ntp = True
    
if ntp:
    print('NTP is synchronised')
else:
    print('NTP is NOT synchronised')

if nextion and not ntp and mode =='start':
    print('Getting time from NEXTION RTC')

    values = NX_getvalues(('rtc0', 'rtc1', 'rtc2', 'rtc3', 'rtc4', 'rtc5'))
    try:
        rtc_time = time.mktime((values['rtc0'], values['rtc1'], values['rtc2'], values['rtc3'], values['rtc4'], values['rtc5'], 0, 1, -1))
    except OverflowError:
        print('No RTC installed?!')
    else:
        if rtc_time > os.path.getmtime(__file__):
            print('Setting system time:')
            os.system('date -s "{}-{}-{} {}:{}:{}"'.format(values['rtc0'], values['rtc1'], values['rtc2'], values['rtc3'], values['rtc4'], values['rtc5']))
        else:
            print('Invalid RTC time')
elif nextion and ntp:
    localtime = time.localtime()
    print('Setting NEXTION RTC from clock')
    NX_sendvalues({'rtc0':localtime[0], 'rtc1':localtime[1], 'rtc2':localtime[2], 'rtc3':localtime[3], 'rtc4':localtime[4], 'rtc5':localtime[5]})
  
os.unlink(pidfilename)
