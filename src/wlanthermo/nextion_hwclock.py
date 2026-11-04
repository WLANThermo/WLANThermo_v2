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

import logging
import os
import sys
import time
from subprocess import PIPE, Popen

from wlanthermo.display import Display

# Konfigurationsdatei einlesen
config = {'timeout': '30',
          'serialdevice': '/dev/serial0',
          'serialspeed': '115200'}

RTC_KEYS = ('rtc0', 'rtc1', 'rtc2', 'rtc3', 'rtc4', 'rtc5')


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def ntp_synchronized():
    with Popen(["/usr/bin/timedatectl", "status"], stdout=PIPE, universal_newlines=True) as ntpstat:
        for line in ntpstat.stdout:
            if 'NTP synchronized: yes' in line:
                return True
    return False


logging.basicConfig(level=logging.WARNING, format='%(name)s: %(message)s')

if len(sys.argv) < 2:
    sys.exit('Argument needed: start or stop')
if sys.argv[1].lower() not in ('start', 'stop'):
    sys.exit('Valid arguments: start or stop')
mode = sys.argv[1].lower()

# Ueberpruefe ob der Dienst schon laeuft
pidfilename = '/var/run/nextion_hwclock.pid'
if os.access(pidfilename, os.F_OK):
    with open(pidfilename, 'r') as pidfile:
        old_pid = int(pidfile.readline())
    if check_pid(old_pid):
        print("%s already exists, Process is running, exiting" % pidfilename)
        sys.exit()
with open(pidfilename, 'w') as pidfile:
    pidfile.write(str(os.getpid()))

display = Display()
# Nicht warten, wenn ein anderer Prozess das Display benutzt
nextion = display.start(config['serialdevice'], config['serialspeed'], blocking=False)
if not nextion:
    print('Error in NEXTION init')

ntp = ntp_synchronized()
print('NTP is synchronised' if ntp else 'NTP is NOT synchronised')

if nextion and not ntp and mode == 'start':
    print('Getting time from NEXTION RTC')

    values = display.getvalues(RTC_KEYS)
    if len(values) < len(RTC_KEYS):
        print('No RTC installed?!')
    else:
        try:
            rtc_time = time.mktime(tuple(values[k] for k in RTC_KEYS) + (0, 1, -1))
        except (OverflowError, ValueError):
            print('No RTC installed?!')
        else:
            if rtc_time > os.path.getmtime(__file__):
                print('Setting system time:')
                os.system('date -s "{}-{}-{} {}:{}:{}"'.format(*(values[k] for k in RTC_KEYS)))
            else:
                print('Invalid RTC time')
elif nextion and ntp:
    localtime = time.localtime()
    print('Setting NEXTION RTC from clock')
    display.sendvalues(dict(zip(RTC_KEYS, localtime[:6])))

display.stop()
os.unlink(pidfilename)
