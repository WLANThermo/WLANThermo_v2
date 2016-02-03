#!/usr/bin/python
# coding=utf-8

# Copyright (c) 2013, 2014, 2015 Joe16
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

import os
import pyinotify
import subprocess
import ConfigParser
import thread
import time
import sys
import logging
import threading
import RPi.GPIO as GPIO
import signal

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Timing Konstanten
E_PULSE = 0.00005
E_DELAY = 0.00005


display_proc = None


HIGH = True  # HIGH-Pegel
LOW  = False # LOW-Pegel

wm = pyinotify.WatchManager()
#mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE
mask = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO

cf = '/var/www/conf/WLANThermo.conf'

# Wir laufen als root, auch andere müssen die Config schreiben!
os.umask (0)

Config = ConfigParser.ConfigParser()
for i in range(0,5):
    while True:
        try:
            Config.read(cf)
        except IndexError:
            time.sleep(1)
            continue
        break

LOGFILE = Config.get('daemon_logging', 'log_file')
logger = logging.getLogger('WLANthermoWD')
#Define Logging Level by changing >logger.setLevel(logging.LEVEL_YOU_WANT)< available: DEBUG, INFO, WARNING, ERROR, CRITICAL
#logger.setLevel(logging.DEBUG)
log_level = Config.get('daemon_logging', 'level_WD')
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

logger.info('WLANThermoWD started')

#ueberpruefe ob der Dienst schon laeuft
pid = str(os.getpid())
pidfilename = '/var/run/'+os.path.basename(__file__).split('.')[0]+'.pid'

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


class fs_wd(pyinotify.ProcessEvent):
    def process_IN_CLOSE_WRITE(self, event):
        if (os.path.join(event.path, event.name) == "/var/www/conf/WLANThermo.conf"):
            #print "IN_CLOSE_WRITE: %s " % os.path.join(event.path, event.name)
            read_config()
    def process_IN_MOVED_TO(self, event):
        if (os.path.join(event.path, event.name) == "/var/www/conf/WLANThermo.conf"):
            #print "IN_MOVED_TO: %s " % os.path.join(event.path, event.name)
            read_config()

def reboot_pi():
    logger.info('reboot PI')
    while True:
        try:
            cfgfile = open(cf + '_tmp','w')
            Config.set('ToDo', 'raspi_reboot', 'False')
            Config.write(cfgfile)
            cfgfile.flush()
            os.fsync(cfgfile.fileno())
            cfgfile.close()
            os.rename(cf + '_tmp', cf)
        except IndexError:
            time.sleep(1)
            continue
        break
    
    #Stoppe die Dienste
    handle_service('/etc/init.d/WLANThermo', 'stop')
    handle_service('/etc/init.d/WLANThermoPIT', 'stop')
    #Schreibe aufs LCD
    while True:
        try:
            fw = open('/var/www/tmp/display/wd' + '_tmp','w')
            fw.write('------ACHTUNG!-------;WLAN-Thermometer;- startet neu -;bis gleich...')
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename('/var/www/tmp/display/wd' + '_tmp', '/var/www/tmp/display/wd')
        except IndexError:
            time.sleep(0.1)
            continue
        break
		
    time.sleep(2)
    bashCommand = 'sudo reboot'
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info('Termin by signal')
    else:
        logger.info('Child returned' + str(retcode))


def halt_pi():
    logger.info('Shutting down the Raspberry')
    #Stoppe die Dienste
    handle_service('/etc/init.d/WLANThermo', 'stop')
    handle_service('/etc/init.d/WLANThermoPIT', 'stop')
    #Schreibe aufs LCD
    while True:
        try:
            fw = open('/var/www/tmp/display/wd' + '_tmp', 'w')
            fw.write('------ACHTUNG!-------;WLAN-Thermometer;- heruntergefahren -;und Tschuess...')
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename('/var/www/tmp/display/wd' + '_tmp', '/var/www/tmp/display/wd')
        except IndexError:
            time.sleep(1)
            continue
        break
    bashCommand = 'sudo halt'
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info('Termin by signal')
    else:
        logger.info('Child returned' + str(retcode))


def halt_v3_pi():
    logger.info('Shutting down the Raspberry, Power Off (v3)')
    # Stoppe die Dienste
    handle_service('/etc/init.d/WLANThermo', 'stop')
    handle_service('/etc/init.d/WLANThermoPIT', 'stop')
    # Schreibe aufs LCD
    while True:
        try:
            fw = open('/var/www/tmp/display/wd' + '_tmp','w')
            fw.write('------ACHTUNG!-------;WLAN-Thermometer;- heruntergefahren -;und Tschuess...')
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename('/var/www/tmp/display/wd' + '_tmp', '/var/www/tmp/display/wd')
        except IndexError:
            time.sleep(1)
            continue
        break
    # Sende Abschaltkommando an den ATtiny
    GPIO.setup(27, GPIO.OUT)
    GPIO.output(27,True)
    time.sleep(1)
    GPIO.output(27,False)
    time.sleep(1)
    GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # Fahre Betriebssystem herunter
    bashCommand = 'sudo halt'
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info('Termin by signal')
    else:
        logger.info('Child returned' + str(retcode))


def read_config():
    global cf
    logger.debug('Read Config..')
    try:
        # Konfigurationsdatei einlesen
        #Config = ConfigParser.ConfigParser()
        while True:
            try:
                Config.read(cf)
            except IndexError:
                time.sleep(1)
                continue
            break
        if (Config.getboolean('ToDo', 'restart_thermo')):
            logger.info('Restart Thermo Process...')
            handle_service('service WLANThermo', 'restart')
            time.sleep(3)
            logger.info('Aendere config wieder auf False')
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'restart_thermo', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break

        if (Config.getboolean('ToDo', 'restart_pitmaster')):
            logger.info('Restart Pitmaster')
            handle_service('service WLANThermoPIT', 'restart')
            time.sleep(3)
            logger.info('Aendere config wieder auf False')
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'restart_pitmaster', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
        
        if (Config.getboolean('ToDo', 'raspi_shutdown')):
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'raspi_shutdown', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
            if Config.get('Hardware', 'version') in ['v3']:
                halt_v3_pi()
            else:
                halt_pi()
        
        check_display()
        
        if (Config.getboolean('ToDo', 'raspi_reboot')):
            reboot_pi()
        
        if (Config.getboolean('ToDo', 'backup')):
            logger.info('create backup!')
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'backup', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
            ret = os.popen("/usr/sbin/wlt_2_backup.sh").read()
            logger.debug(ret)
        if (Config.getboolean('ToDo', 'update_gui')):
            logger.info('create backup!')
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'update_gui', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
            ret = os.popen("/usr/sbin/wlt_2_update_gui.sh").read()
            logger.debug(ret)

        if (Config.getboolean('ToDo', 'start_update')):
            logger.info('Update Software!')
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'start_update', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
            ret = os.popen("/usr/sbin/wlt_2_update.sh").read()
            logger.debug(ret)

            
        if (Config.getboolean('ToDo', 'create_new_log')):
            logger.info('create new log')
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'create_new_log', 'False')
                    Config.set('Logging', 'write_new_log_on_restart', 'True')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
            time.sleep(2)
            handle_service('service WLANThermo', 'restart')
            time.sleep(10)
            while True:
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('Logging', 'write_new_log_on_restart', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                except IndexError:
                    time.sleep(1)
                    continue
                break
            logger.info('finished create new log')

        if (Config.getboolean('ToDo', 'pit_on')):
            check_pitmaster() 

    except:
        logger.info('Unexpected error: ' +str(sys.exc_info()[0]))
        raise

def handle_service(sService, sWhat):
    bashCommand = 'sudo ' + sService + ' ' + sWhat #/etc/init.d/WLANThermo restart'
    logger.debug('handle_service: ' + bashCommand)
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info('Termin by signal')
    else:
        logger.info('Child returned' + str(retcode))


def check_file(f):
    if ( not os.path.isfile(f)):
        while True:
            try:
                fw1 = open(f,'w')
                fw1.write('-')
                fw1.flush()
                os.fsync(fw1.fileno())
                fw1.close()
            except IndexError:
                time.sleep(1)
                continue
            break


def check_display():
    logger.debug('Check Display')
    global display_proc, Config
    if (Config.getboolean('Display', 'lcd_present')):
        startproc = False
        # Display aktiviert
        if display_proc == None:
            # Display-Prozess starten bzw. restarten
            logger.info('Starte Display')
            startproc = True
        elif display_proc.poll() != None:
            # Display-Prozess wieder starten
            logger.info('Starte Display wieder')
            startproc = True
        elif (Config.getboolean('ToDo', 'restart_display')):
            # Display soll restartet werden
            # Wenn es nicht lief landen wir in den vorherigen Bedingungen
            logger.info('Beende Display')
            logger.debug('Restart Display')
            display_proc.terminate()
            display_proc.wait()
            display_proc = None
            startproc = True
        
        if startproc:
            display_proc = subprocess.Popen([sys.executable, '/usr/sbin/' + Config.get('Display', 'lcd_type')])
            
        if Config.getboolean('ToDo', 'restart_display'):
            logger.info('Ändere restart_display wieder auf False')
            for i in range(0,5):
                try:
                    cfgfile = open(cf + '_tmp','w')
                    Config.set('ToDo', 'restart_display', 'False')
                    Config.write(cfgfile)
                    cfgfile.flush()
                    os.fsync(cfgfile.fileno())
                    cfgfile.close()
                    os.rename(cf + '_tmp', cf)
                    break
                except IndexError:
                    time.sleep(1)
    else:
        # Display deaktiviert
        if display_proc != None:
            # Display-Prozess beenden
            display_proc.terminate()
            display_proc.wait()
            display_proc = None


def check_pitmaster():
    logger.debug('Check Pitmaster')
    pitmasterPID = os.popen("ps aux|grep wlt_2_pitmaster.py|grep -v grep|awk '{print $2}'").read()
    bashCommandPit = ''
    if (Config.getboolean('ToDo', 'pit_on')):
        if (len(pitmasterPID) < 1):
            logger.info('start pitmaster')
            bashCommandPit = 'sudo service WLANThermoPIT restart'
        else:
            logger.info('pitmaster already running')
    else:
        if (len(pitmasterPID) > 0):
            logger.info('stop pitmaster')
            #obsolet
        else:
            logger.info('pitmaster already stopped')
    if (len(bashCommandPit) > 0):
        retcodeO = subprocess.Popen(bashCommandPit.split())
        retcodeO.wait()
        if retcodeO < 0:
            logger.info('Termin by signal')
        else:
            logger.info('Child returned' + str(retcodeO))

notifier = pyinotify.Notifier(wm, fs_wd())

wdd = wm.add_watch('/var/www/conf', mask) #, rec=True)

#Start thread for shutdown pin
#input_thread = threading.Thread(target = wait_input)
#input_thread.start()

GPIO.add_event_detect(27, GPIO.RISING, callback=halt_pi, bouncetime=1000)


Config.read(cf)
check_display()
check_pitmaster()

while True:
    try:
        Config.read(cf)
        #time.sleep(5) 
        notifier.process_events()
        if notifier.check_events():
            notifier.read_events()
    except KeyboardInterrupt:
        notifier.stop()
        logger.info('WLANThermoWD stopped')
        logging.shutdown()
        os.unlink(pidfilename)
        break
        