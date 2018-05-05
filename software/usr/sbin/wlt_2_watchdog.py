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
import codecs
import os
import pyinotify
import subprocess
import ConfigParser
import time
import sys
import logging
import RPi.GPIO as GPIO
import signal
import traceback
import gettext
import random
import string

gettext.install('wlt_2_watchdog', localedir='/usr/share/WLANThermo/locale/', unicode=True)

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

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
            Config.readfp(codecs.open(cf, 'r', 'utf_8'))
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

logger.info(_(u'WLANThermoWD started'))

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
        print(_(u'%s already exists, Process is running, exiting') % pidfilename)
        logger.error(_(u'%s already exists, Process is running, exiting') % pidfilename)
        sys.exit()
    else:
        logger.info(_(u'%s already exists, Process is NOT running, resuming operation') % pidfilename)
        pidfile.seek(0)
        open(pidfilename, 'w').write(pid)
    
else:
    logger.debug(_(u'%s written') % pidfilename)
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


def reboot_pi():
    logger.info(_(u'rebooting'))
    
    Config.set('ToDo', 'raspi_reboot', 'False')
    config_write(cf, Config)
    
    # Setze Flag
    try:
        open('/var/www/tmp/reboot.flag', 'w').close()
    except OSError:
        pass
    
    #Stoppe die Dienste
    handle_service('WLANThermo', 'stop')
    handle_service('WLANThermoPIT', 'stop')
    #Schreibe aufs LCD
    tmp_filename = get_random_filename('/var/www/tmp/display/wd')
    while True:
        try:
            fw = open(tmp_filename,'w')
            fw.write(_(u'---- ATTENTION!  ----;---- WLANThermo ----;  is now rebooting  ;see you later...'))
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename(tmp_filename, '/var/www/tmp/display/wd')
        except IndexError:
            time.sleep(0.1)
            continue
        break
        
    time.sleep(2)
    bashCommand = 'sudo reboot'
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info(_(u'Terminated by signal'))
    else:
        logger.info(_(u'Child returned: ') + str(retcode))


def halt_pi():
    logger.info(_(u'Shutting down the Raspberry'))
    #Stoppe die Dienste
    handle_service('WLANThermo', 'stop')
    handle_service('WLANThermoPIT', 'stop')
    #Schreibe aufs LCD
    tmp_filename = get_random_filename('/var/www/tmp/display/wd')
    while True:
        try:
            fw = open(tmp_filename, 'w')
            fw.write(_(u'---- ATTENTION!  ----;---- WLANThermo ----;is now shutting down;Bye-bye!'))
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename(tmp_filename, '/var/www/tmp/display/wd')
        except IndexError:
            time.sleep(1)
            continue
        break
    bashCommand = 'sudo poweroff'
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info(_(u'Terminated by signal'))
    else:
        logger.info(_(u'Child returned: ') + str(retcode))


def halt_v3_pi():
    logger.info(_(u'Shutting down the Raspberry, Power Off (v3)'))
    # Stoppe die Dienste
    handle_service('WLANThermo', 'stop')
    handle_service('WLANThermoPIT', 'stop')
    # Schreibe aufs LCD
    tmp_filename = get_random_filename('/var/www/tmp/display/wd')
    while True:
        try:
            fw = open(tmp_filename, 'w')
            fw.write(_(u'---- ATTENTION!  ----;---- WLANThermo ----;is now shutting down;Bye-bye!'))
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename(tmp_filename, '/var/www/tmp/display/wd')
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
    bashCommand = 'sudo poweroff'
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info(_(u'Terminated by signal'))
    else:
        logger.info(_(u'Child returned: ') + str(retcode))


def shutdown_button(gpio):
    logger.info(_(u'Shutting down! (Button pressed)'))
    halt_pi()


def read_config():
    global cf
    logger.debug(_(u'Read Config...'))
    try:
        # Konfigurationsdatei einlesen
        #Config = ConfigParser.ConfigParser()
        while True:
            try:
                Config.readfp(codecs.open(cf, 'r', 'utf_8'))
            except IndexError:
                time.sleep(1)
                continue
            break
        tmp_filename = get_random_filename(cf)
        
        
        if Config.get('Hardware', 'version') in ['miniV2']:
            pitmaster_count = 2
        else:
            pitmaster_count = 1
            
        if (Config.getboolean('ToDo', 'restart_thermo')):
            logger.info(_(u'Restart WLANThermo process!'))
            handle_service('WLANThermo', 'restart')
            time.sleep(3)
            logger.info(_(u'Changing restart_thermo to False again!'))
            
            Config.set('ToDo', 'restart_thermo', 'False')
            config_write(cf, Config)
        
        if (Config.getboolean('ToDo', 'restart_pitmaster')):
            logger.info(_(u'Restart pitmaster!'))
            handle_service('WLANThermoPIT', 'restart')
            time.sleep(3)
            logger.info(_(u'Changing restart_pitmaster to False again!'))

            Config.set('ToDo', 'restart_pitmaster', 'False')
            config_write(cf, Config)
            
        if (Config.getboolean('ToDo', 'restart_pitmaster2')):
            logger.info(_(u'Restart pitmaster 2!'))
            handle_service('WLANThermoPIT2', 'restart')
            time.sleep(3)
            logger.info(_(u'Changing restart_pitmaster2 to False again!'))

            Config.set('ToDo', 'restart_pitmaster2', 'False')
            config_write(cf, Config)
        
        if (Config.getboolean('ToDo', 'raspi_shutdown')):
            Config.set('ToDo', 'raspi_shutdown', 'False')
            config_write(cf, Config)
            if Config.get('Hardware', 'version') in ['v3']:
                halt_v3_pi()
            else:
                halt_pi()
        
        check_display()
        
        if (Config.getboolean('ToDo', 'raspi_reboot')):
            reboot_pi()
        
        if (Config.getboolean('ToDo', 'backup')):
            logger.info(_(u'Create backup!'))
            Config.set('ToDo', 'backup', 'False')
            config_write(cf, Config)
            ret = os.popen("/usr/sbin/wlt_2_backup.sh").read()
            logger.debug(ret)

        if (Config.getboolean('ToDo', 'start_system_update')):
            logger.info(_(u'Update system software!'))
            Config.set('ToDo', 'start_system_update', 'False')
            config_write(cf, Config)
            # Start update, hold back package wlanthermo
            ret = os.popen("/usr/bin/systemd-run /usr/bin/wlt_2_update_system.sh").read()
            logger.debug(ret)
            
        if (Config.getboolean('ToDo', 'start_full_update')):
            logger.info(_(u'Update full software!'))
            Config.set('ToDo', 'start_full_update', 'False')
            config_write(cf, Config)
            ret = os.popen("/usr/bin/systemd-run /usr/bin/wlt_2_update_system.sh --full").read()
            logger.debug(ret)
            
        if (Config.getboolean('ToDo', 'create_new_log')):
            
            logger.info(_(u'Create new log!'))
            Config.set('ToDo', 'create_new_log', 'False')
            Config.set('Logging', 'write_new_log_on_restart', 'True')
            config_write(cf, Config)
            
            time.sleep(2)
            handle_service('WLANThermo', 'restart')
            time.sleep(10)
            
            Config.set('Logging', 'write_new_log_on_restart', 'False')
            config_write(cf, Config)
            
            logger.info(_(u'Finished creation of new logfile'))

        for id in xrange(pitmaster_count):
            logger.info(_(u'Check Pitmaster {}!'.format(id + 1)))
            check_pitmaster(id)
        
        check_maverick()
            
    except:
        logger.info(_(u'Unexpected error: ') +str(sys.exc_info()[0]))
        raise

def handle_service(sService, sWhat):
    bashCommand = 'sudo systemctl ' + sWhat + ' ' + sService + '.service'
    logger.debug(_(u'Handle service: ') + bashCommand)
    retcode = subprocess.Popen(bashCommand.split())
    retcode.wait()
    if retcode < 0:
        logger.info(_(u'Terminated by signal'))
    else:
        logger.info(_(u'Child returned: ') + str(retcode))


def check_file(f):
    if not os.path.isfile(f):
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
    logger.debug(_(u'Checking display...'))
    global display_proc, Config
    if (Config.getboolean('Display', 'lcd_present')):
        startproc = False
        # Display aktiviert
        if display_proc == None:
            # Display-Prozess starten bzw. restarten
            logger.info(_(u'Starting display...'))
            startproc = True
        elif display_proc.poll() != None:
            # Display-Prozess wieder starten
            logger.info(_(u'Starting display again...'))
            startproc = True
        elif (Config.getboolean('ToDo', 'restart_display')):
            # Display soll restartet werden
            # Wenn es nicht lief landen wir in den vorherigen Bedingungen
            logger.info(_(u'Stopping display for restart...'))
            display_proc.terminate()
            display_proc.wait()
            display_proc = None
            startproc = True
        
        if startproc:
            display_proc = subprocess.Popen([sys.executable, '/usr/sbin/' + Config.get('Display', 'lcd_type')], stdin=subprocess.PIPE)
            
        if Config.getboolean('ToDo', 'restart_display'):
            tmp_filename = get_random_filename(cf)
            logger.info(_(u'Changing restart_display to False'))
            Config.set('ToDo', 'restart_display', 'False')
            config_write(cf, Config)
    else:
        # Display deaktiviert
        if display_proc != None:
            # Display-Prozess beenden
            display_proc.terminate()
            display_proc.wait()
            display_proc = None


def check_pitmaster(id):
    if id == 0:
        id_string = ''
    else:
        id_string = str(id + 1)
    logger.debug(_(u'Checking pitmaster {}'.format(id + 1)))
    
    pitmasterStatus = subprocess.call(('/bin/systemctl', 'status',  'WLANThermoPIT{}.service'.format(id + 1)))
    bashCommandPit = tuple()
    if (Config.getboolean('ToDo', 'pit{}_on'.format(id_string))):
        if pitmasterStatus != 0:
            logger.info(_(u'Start pitmaster {}'.format(id + 1)))
            bashCommandPit = ('/usr/bin/systemd-run', '--unit', 'WLANThermoPIT{}.service'.format(id_string), '/usr/sbin/wlt_2_pitmaster.py', str(id))
        else:
            logger.info(_(u'Pitmaster {} already running'.format(id + 1)))
    else:
        if pitmasterStatus == 0:
            logger.info(_(u'Stopping pitmaster {}'.format(id + 1)))
            bashCommandPit = ('/bin/systemctl', 'stop', 'WLANThermoPIT{}.service'.format(id_string))
        else:
            logger.info(_(u'Pitmaster {} already stopped'.format(id + 1)))
    if (len(bashCommandPit) > 0):
        retcodeO = subprocess.call(bashCommandPit)
        if retcodeO < 0:
            logger.info(_(u'Pitmaster {} terminated by signal'.format(id + 1)))
        else:
            logger.info(_(u'Child returned: ') + str(retcodeO))


def check_maverick():
    logger.debug(_(u'Checking Maverick'))
    
    pitmasterStatus = subprocess.call(('/bin/systemctl', 'status',  'WLANThermoMAVERICK.service'))
    bashCommandPit = tuple()
    if (Config.getboolean('ToDo', 'maverick_enabled')):
        if pitmasterStatus != 0:
            logger.info(_(u'Start Maverick'))
            bashCommandPit = ('/usr/bin/systemd-run', '--unit', 'WLANThermoMAVERICK.service', '/usr/bin/maverick.py',  '--json',  '/var/www/tmp/maverick.json' , '--noappend')
        else:
            logger.info(_(u'Maverick already running'))
    else:
        if pitmasterStatus == 0:
            logger.info(_(u'Stopping Maverick'))
            bashCommandPit = ('/bin/systemctl', 'stop', 'WLANThermoMAVERICK.service')
        else:
            logger.info(_(u'Maverick already stopped'))
    if (len(bashCommandPit) > 0):
        retcodeO = subprocess.call(bashCommandPit)
        if retcodeO < 0:
            logger.info(_(u'Maverick terminated by signal'))
        else:
            logger.info(_(u'Child returned: ') + str(retcodeO))


def raise_keyboard(signum, frame):
    logger.debug(_(u'Caught signal: ') + str(signum))
    raise KeyboardInterrupt(_(u'Received SIGTERM'))


def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))

sys.excepthook = log_uncaught_exceptions

signal.signal(15, raise_keyboard)

notifier = pyinotify.Notifier(wm, fs_wd())

wdd = wm.add_watch('/var/www/conf', mask) #, rec=True)

GPIO.add_event_detect(27, GPIO.RISING, callback=shutdown_button, bouncetime=1000)

Config.readfp(codecs.open(cf, 'r', 'utf_8'))
check_display()
check_maverick()

if Config.get('Hardware', 'version') in ['miniV2']:
    pitmaster_count = 2
else:
    pitmaster_count = 1
            
for id in xrange(pitmaster_count):
    check_pitmaster(id)

# Lösche Rebootflag
try:
    os.unlink('/var/www/tmp/reboot.flag')
except OSError:
    pass

while True:
    try:
        Config.readfp(codecs.open(cf, 'r', 'utf_8'))
        notifier.process_events()
        if notifier.check_events():
            notifier.read_events()
    except KeyboardInterrupt:
        notifier.stop()
        if (Config.getboolean('Display', 'lcd_present')):
            if display_proc.poll() == None:
                logger.info(_(u'Stopping Display'))
                display_proc.terminate()
                display_proc.wait()
                display_proc = None
        logger.info(_(u'WLANThermoWD stopped'))
        logging.shutdown()
        os.unlink(pidfilename)
        break
