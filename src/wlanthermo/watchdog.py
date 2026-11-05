#!/usr/bin/python3
# coding=utf-8

# Copyright (c) 2013, 2014, 2015 Joe16
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
import codecs
import os
import subprocess
import configparser
import time
import sys
import logging
import RPi.GPIO as GPIO
import signal
import traceback
import gettext

from wlanthermo.config import update_config
import random
import string

# s zwischen den Prüfungen der Konfiguration bzw. des Display-Prozesses
CONFIG_POLL_INTERVAL = 1
DISPLAY_CHECK_INTERVAL = 10

# Werte von [Display] lcd_type (vom Webinterface gesetzt) -> Modul im Paket wlanthermo
DISPLAY_MODULES = {
    'wlt_2_nextion.py': 'wlanthermo.display.nextion_ui',
    'wlt_2_lcd_204.py': 'wlanthermo.display.lcd_204',
}

HIGH = True  # HIGH-Pegel
LOW  = False # LOW-Pegel

cf = '/var/www/conf/WLANThermo.conf'
pidfilename = '/var/run/wlt_2_watchdog.pid'

def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_random_filename(filename):
    return filename + '_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))


def reboot_pi():
    logger.info(_('rebooting'))
    
    Config.set('ToDo', 'raspi_reboot', 'False')
    update_config({'ToDo': {'raspi_reboot': 'False'}}, cf)
    
    # Setze Flag
    try:
        open('/var/www/tmp/reboot.flag', 'w').close()
    except OSError:
        pass
    
    #Stoppe die Dienste
    handle_service('WLANThermo', 'stop')
    #Schreibe aufs LCD
    tmp_filename = get_random_filename('/var/www/tmp/display/wd')
    while True:
        try:
            fw = open(tmp_filename, 'w', encoding='utf-8')
            fw.write(_('---- ATTENTION!  ----;---- WLANThermo ----;  is now rebooting  ;see you later...'))
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
    retcode = subprocess.call(bashCommand.split())  # Python 3: Popen-Objekt ließe sich nicht mit 0 vergleichen
    if retcode < 0:
        logger.info(_('Terminated by signal'))
    else:
        logger.info(_('Child returned: ') + str(retcode))


def halt_pi():
    logger.info(_('Shutting down the Raspberry'))
    #Stoppe die Dienste
    handle_service('WLANThermo', 'stop')
    #Schreibe aufs LCD
    tmp_filename = get_random_filename('/var/www/tmp/display/wd')
    while True:
        try:
            fw = open(tmp_filename, 'w', encoding='utf-8')
            fw.write(_('---- ATTENTION!  ----;---- WLANThermo ----;is now shutting down;Bye-bye!'))
            fw.flush()
            os.fsync(fw.fileno())
            fw.close()
            os.rename(tmp_filename, '/var/www/tmp/display/wd')
        except IndexError:
            time.sleep(1)
            continue
        break
    bashCommand = 'sudo poweroff'
    retcode = subprocess.call(bashCommand.split())  # Python 3: Popen-Objekt ließe sich nicht mit 0 vergleichen
    if retcode < 0:
        logger.info(_('Terminated by signal'))
    else:
        logger.info(_('Child returned: ') + str(retcode))


def halt_v3_pi():
    logger.info(_('Shutting down the Raspberry, Power Off (v3)'))
    # Stoppe die Dienste
    handle_service('WLANThermo', 'stop')
    # Schreibe aufs LCD
    tmp_filename = get_random_filename('/var/www/tmp/display/wd')
    while True:
        try:
            fw = open(tmp_filename, 'w', encoding='utf-8')
            fw.write(_('---- ATTENTION!  ----;---- WLANThermo ----;is now shutting down;Bye-bye!'))
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
    retcode = subprocess.call(bashCommand.split())  # Python 3: Popen-Objekt ließe sich nicht mit 0 vergleichen
    if retcode < 0:
        logger.info(_('Terminated by signal'))
    else:
        logger.info(_('Child returned: ') + str(retcode))


def shutdown_button(gpio):
    logger.info(_('Shutting down! (Button pressed)'))
    halt_pi()


def read_config():
    global cf
    logger.debug(_('Read Config...'))
    try:
        # Konfigurationsdatei einlesen
        #Config = ConfigParser.ConfigParser()
        while True:
            try:
                Config.read_file(codecs.open(cf, 'r', 'utf_8'))
            except IndexError:
                time.sleep(1)
                continue
            break

        if (Config.getboolean('ToDo', 'restart_thermo')):
            logger.info(_('Restart WLANThermo process!'))
            handle_service('WLANThermo', 'restart')
            time.sleep(3)
            logger.info(_('Changing restart_thermo to False again!'))
            
            Config.set('ToDo', 'restart_thermo', 'False')
            update_config({'ToDo': {'restart_thermo': 'False'}}, cf)
        
        if (Config.getboolean('ToDo', 'raspi_shutdown')):
            Config.set('ToDo', 'raspi_shutdown', 'False')
            update_config({'ToDo': {'raspi_shutdown': 'False'}}, cf)
            if Config.get('Hardware', 'version') in ['v3']:
                halt_v3_pi()
            else:
                halt_pi()
        
        check_display()
        
        if (Config.getboolean('ToDo', 'raspi_reboot')):
            reboot_pi()
        
        if (Config.getboolean('ToDo', 'backup')):
            logger.info(_('Create backup!'))
            Config.set('ToDo', 'backup', 'False')
            update_config({'ToDo': {'backup': 'False'}}, cf)
            ret = os.popen("/usr/sbin/wlt_2_backup.sh").read()
            logger.debug(ret)
        
        if (Config.getboolean('ToDo', 'check_update')):
            logger.info(_('Check for software updates...'))
            Config.set('ToDo', 'check_update', 'False')
            update_config({'ToDo': {'check_update': 'False'}}, cf)
            ret = os.popen("/bin/systemctl --no-block start WLANThermoUPDATECHECK.service")
            logger.debug(ret)

        if (Config.getboolean('ToDo', 'start_system_update')):
            logger.info(_('Update system software!'))
            Config.set('ToDo', 'start_system_update', 'False')
            update_config({'ToDo': {'start_system_update': 'False'}}, cf)
            # Start update, hold back package wlanthermo
            ret = os.popen("/usr/bin/systemd-run /usr/bin/wlt_2_update_system.sh").read()
            logger.debug(ret)
            
        if (Config.getboolean('ToDo', 'start_full_update')):
            logger.info(_('Update full software!'))
            Config.set('ToDo', 'start_full_update', 'False')
            update_config({'ToDo': {'start_full_update': 'False'}}, cf)
            ret = os.popen("/usr/bin/systemd-run /usr/bin/wlt_2_update_system.sh --full").read()
            logger.debug(ret)
            
        if (Config.getboolean('ToDo', 'create_new_log')):
            
            logger.info(_('Create new log!'))
            Config.set('ToDo', 'create_new_log', 'False')
            Config.set('Logging', 'write_new_log_on_restart', 'True')
            update_config({'ToDo': {'create_new_log': 'False'}, 'Logging': {'write_new_log_on_restart': 'True'}}, cf)
            
            time.sleep(2)
            handle_service('WLANThermo', 'restart')
            time.sleep(10)
            
            Config.set('Logging', 'write_new_log_on_restart', 'False')
            update_config({'Logging': {'write_new_log_on_restart': 'False'}}, cf)
            
            logger.info(_('Finished creation of new logfile'))

            
    except:
        logger.info(_('Unexpected error: ') +str(sys.exc_info()[0]))
        raise

def handle_service(sService, sWhat):
    bashCommand = 'sudo systemctl ' + sWhat + ' ' + sService + '.service'
    logger.debug(_('Handle service: ') + bashCommand)
    retcode = subprocess.call(bashCommand.split())  # Python 3: Popen-Objekt ließe sich nicht mit 0 vergleichen
    if retcode < 0:
        logger.info(_('Terminated by signal'))
    else:
        logger.info(_('Child returned: ') + str(retcode))


def check_file(f):
    if not os.path.isfile(f):
        while True:
            try:
                fw1 = open(f, 'w', encoding='utf-8')
                fw1.write('-')
                fw1.flush()
                os.fsync(fw1.fileno())
                fw1.close()
            except IndexError:
                time.sleep(1)
                continue
            break


def check_display():
    logger.debug(_('Checking display...'))
    global display_proc, Config
    if (Config.getboolean('Display', 'lcd_present')):
        startproc = False
        # Display aktiviert
        if display_proc == None:
            # Display-Prozess starten bzw. restarten
            logger.info(_('Starting display...'))
            startproc = True
        elif display_proc.poll() != None:
            # Display-Prozess wieder starten
            logger.info(_('Starting display again...'))
            startproc = True
        elif (Config.getboolean('ToDo', 'restart_display')):
            # Display soll restartet werden
            # Wenn es nicht lief landen wir in den vorherigen Bedingungen
            logger.info(_('Stopping display for restart...'))
            display_proc.terminate()
            display_proc.wait()
            display_proc = None
            startproc = True
        
        if startproc:
            lcd_type = Config.get('Display', 'lcd_type')
            module = DISPLAY_MODULES.get(lcd_type)
            if module is None:
                logger.error(_('Unknown display type: {}').format(lcd_type))
            else:
                display_proc = subprocess.Popen([sys.executable, '-m', module], stdin=subprocess.PIPE)
            
        if Config.getboolean('ToDo', 'restart_display'):
            logger.info(_('Changing restart_display to False'))
            Config.set('ToDo', 'restart_display', 'False')
            update_config({'ToDo': {'restart_display': 'False'}}, cf)
    else:
        # Display deaktiviert
        if display_proc != None:
            # Display-Prozess beenden
            display_proc.terminate()
            display_proc.wait()
            display_proc = None


def raise_keyboard(signum, frame):
    logger.debug(_('Caught signal: ') + str(signum))
    raise KeyboardInterrupt(_('Received SIGTERM'))


def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))


def main():
    global Config, display_proc, logger
    gettext.install('wlt_2_watchdog', localedir='/usr/share/WLANThermo/locale/')

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    display_proc = None


    # Wir laufen als root, auch andere müssen die Config schreiben!
    os.umask (0)

    Config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
    for i in range(0,5):
        while True:
            try:
                Config.read_file(codecs.open(cf, 'r', 'utf_8'))
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

    logger.info(_('WLANThermoWD started'))

    #ueberpruefe ob der Dienst schon laeuft
    pid = str(os.getpid())

    if os.access(pidfilename, os.F_OK):
        pidfile = open(pidfilename, "r")
        pidfile.seek(0)
        old_pid = int(pidfile.readline())
        if check_pid(old_pid):
            print(_('%s already exists, Process is running, exiting') % pidfilename)
            logger.error(_('%s already exists, Process is running, exiting') % pidfilename)
            sys.exit()
        else:
            logger.info(_('%s already exists, Process is NOT running, resuming operation') % pidfilename)
            pidfile.seek(0)
            open(pidfilename, 'w').write(pid)

    else:
        logger.debug(_('%s written') % pidfilename)
        open(pidfilename, 'w').write(pid)

    sys.excepthook = log_uncaught_exceptions

    signal.signal(15, raise_keyboard)

    GPIO.add_event_detect(27, GPIO.RISING, callback=shutdown_button, bouncetime=1000)

    Config.read_file(codecs.open(cf, 'r', 'utf_8'))
    check_display()

    # Lösche Rebootflag
    try:
        os.unlink('/var/www/tmp/reboot.flag')
    except OSError:
        pass

    # Änderungen der Konfiguration erkennen (bisher inotify). Der Stand beim Start
    # gilt als bekannt, damit alte [ToDo]-Flags nicht ausgeführt werden.
    config_mtime = os.path.getmtime(cf)
    last_display_check = time.monotonic()
    while True:
        try:
            mtime = os.path.getmtime(cf)
            if mtime != config_mtime:
                config_mtime = mtime
                read_config()
                last_display_check = time.monotonic()
            elif time.monotonic() - last_display_check >= DISPLAY_CHECK_INTERVAL:
                # abgestürzten Display-Prozess auch ohne Konfigurationsänderung neu starten
                Config.read_file(codecs.open(cf, 'r', 'utf_8'))
                check_display()
                last_display_check = time.monotonic()
            time.sleep(CONFIG_POLL_INTERVAL)
        except KeyboardInterrupt:
            if (Config.getboolean('Display', 'lcd_present')):
                if display_proc is not None and display_proc.poll() == None:
                    logger.info(_('Stopping Display'))
                    display_proc.terminate()
                    display_proc.wait()
                    display_proc = None
            logger.info(_('WLANThermoWD stopped'))
            logging.shutdown()
            os.unlink(pidfilename)
            break

if __name__ == '__main__':
    main()
