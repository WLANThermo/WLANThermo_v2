#!/usr/bin/python
# coding=utf-8

# WLANThermo
# wlt_2_pitmaster.py - Sets pit temperature by controlling a fan, servo, heater or likely devices.
#
# Copyright (c) 2013 Joe16
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

import ConfigParser
import os
import time
import logging
import pigpio
import threading
import signal
import traceback
import gettext
import codecs
import sys

gettext.install('wlt_2_pitmaster', localedir='/usr/share/WLANThermo/locale/', unicode=True)

# GPIO START
PIT_PWM = 4  # Pitmaster PWM

# Wir laufen als root, auch andere müssen die Config schreiben!
os.umask(0)

logger = False

def clamp(value, minimum, maximum):
    return max(min(maximum, value), minimum)

# Funktionsdefinition
class BBQpit:
    def __init__(self, logger):
        self.logger = logger
        self.pi = pigpio.pi()
        # self.Pit-Config
        self.pit_type = None
        self.pit_gpio = None
        self.pit_servo_gpio = None

        # public
        self.pit_min = 0
        self.pit_max = 100
        self.pit_inverted = False

        self.pit_servo_min = 1000
        self.pit_servo_max = 2000
        self.pit_servo_inverted = False

        self.pit_startup_min = 25
        self.pit_startup_threshold = 0
        self.pit_startup_time = 0.5

        self.pit_damper_offset = 0
        self.pit_damper_pitch = 1

        self.pit_servo_current_width = 0
        self.pit_servo_deadband = 5  # in 10 µs

        # statistics
        self.pit_servo_wouldbe_width = 0
        self.pit_servo_move_count = 0
        self.pit_servo_nomove_count = 0

        # Steuergröße
        self.pit_out = 0.0

        # Wave-ID
        self.fan_pwm = None

        self.pit_io_pwm_thread = None
        self.pit_io_pwm_on = 0.0
        self.pit_io_pwm_off = 0.0
        self.pit_io_pwm_lock = threading.Lock()
        self.pit_io_pwm_end = threading.Event()

    # Beendet eine Ausgabe
    def stop_pit(self):
        if self.pit_type == 'fan_pwm':
            # 25kHz PC-Lüfter
            self.pi.wave_tx_stop()
            # self.pi.wave_delete(self.fan_pwm) # Gives an Error
            self.pi.write(self.pit_gpio, 0)
        elif self.pit_type == 'fan':
            # Lüftersteuerung v3
            self.pi.set_PWM_dutycycle(self.pit_gpio, 0)
        elif self.pit_type == 'servo':
            # Servosteuerung (oder Lüfter über Fahrtenregler)
            self.pi.set_servo_pulsewidth(self.pit_servo_gpio, 0)
        elif self.pit_type == 'io_pwm':
            # PWM-modulierter Schaltausgang (Schwingungspaketsteuerung)
            self.pit_io_pwm_end.set()
            self.pit_io_pwm_thread.join()
            self.pi.write(self.pit_gpio, 0)
        elif self.pit_type == 'io':
            # Schaltausgang
            self.pi.write(self.pit_gpio, 0)
        elif self.pit_type == 'damper':
            self.pi.set_servo_pulsewidth(self.pit_servo_gpio, 0)
            self.pi.set_PWM_dutycycle(self.pit_gpio, 0)
        self.pit_type = None

    # Startet eine Ausgabe
    def start_pit(self, pit_type, gpio, servo_gpio):
        self.logger.debug(_(u'Starting pit {pit_type} on GPIO {gpio}').format(pit_type=pit_type, gpio=str(gpio)))
        if pit_type == 'fan_pwm':
            # 25kHz PC-Lüfter
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            fan_pwm_pulses = []
            fan_pwm_pulses.append(pigpio.pulse(1 << gpio, 0, 1))
            fan_pwm_pulses.append(pigpio.pulse(0, 1 << gpio, 46))
            self.pi.wave_clear()
            self.pi.wave_add_generic(fan_pwm_pulses)
            self.fan_pwm = self.pi.wave_create()
            self.pi.wave_send_repeat(self.fan_pwm)
            self.pit_gpio = gpio
            self.pit_type = pit_type
        elif pit_type == 'fan':
            # Lüftersteuerung v3
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(gpio, 500)
            if not self.pit_inverted:
                self.pi.set_PWM_dutycycle(gpio, self.pit_min * 2.55)
            else:
                self.pi.set_PWM_dutycycle(gpio, self.pit_max * 2.55)
            self.pit_gpio = gpio
            self.pit_type = pit_type
        elif pit_type == 'servo':
            # Servosteuerung (oder Lüfter über Fahrtenregler)
            self.pi.set_mode(servo_gpio, pigpio.OUTPUT)
            # Reset limiter
            self.pit_servo_current_width = 0
            if not self.pit_servo_inverted:
                self.servo_limiter(self.pi.set_servo_pulsewidth(servo_gpio, self.pit_servo_min))
            else:
                self.servo_limiter(self.pi.set_servo_pulsewidth(servo_gpio, self.pit_servo_max))
            self.pit_servo_gpio = servo_gpio
            self.pit_type = pit_type
        elif pit_type == 'io_pwm':
            # PWM-modulierter Schaltausgang (Schwingungspaketsteuerung)
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            self.pit_io_pwm_end.clear()
            self.pit_io_pwm_thread = threading.Thread(target=self.io_pwm, args=(gpio,))
            self.pit_io_pwm_thread.daemon = True
            # Startwerte mitgeben (nicht 0/0 wg. CPU-Last)
            if not self.pit_inverted:
                self.pit_io_pwm_on = 1
                self.pit_io_pwm_off = 1
            else:
                self.pit_io_pwm_on = 1
                self.pit_io_pwm_off = 1
            self.pit_io_pwm_thread.start()
            self.pit_gpio = gpio
            self.pit_type = pit_type
        elif pit_type == 'io':
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            # Schaltausgang
            if not self.pit_inverted:
                self.pi.write(gpio, 0)
            else:
                self.pi.write(gpio, 1)
            self.pit_gpio = gpio
            self.pit_type = pit_type
        elif pit_type == 'damper' and gpio != servo_gpio:
            # Lüftersteuerung für Damper
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(gpio, 500)
            if not self.pit_inverted:
                self.pi.set_PWM_dutycycle(gpio, self.pit_min * 2.55)
            else:
                self.pi.set_PWM_dutycycle(gpio, self.pit_max * 2.55)

            # Servosteuerung für Damper
            # Reset limiter
            self.pit_servo_current_width = 0

            self.pi.set_mode(servo_gpio, pigpio.OUTPUT)
            if not self.pit_servo_inverted:
                self.servo_limiter(self.pi.set_servo_pulsewidth(servo_gpio, self.pit_servo_min))
            else:
                self.servo_limiter(self.pi.set_servo_pulsewidth(servo_gpio, self.pit_servo_max))
            self.pit_gpio = gpio
            self.pit_servo_gpio = servo_gpio
            self.pit_type = pit_type

    def set_pit(self, control_out):
        self.logger.debug(_(u'Setting pit to {}%').format(control_out))
        if control_out > 100:
            self.logger.info(_(u'Control-out over maximum, limiting to 100%'))
            control_out = 100.0
        elif control_out < 0:
            self.logger.info(_(u'Control-out below minimum, limiting to 0%'))
            control_out = 0.0

        # Startup-Funktion für Lüfteranlauf, startet für 0,5s mit 25%
        if self.pit_type in ['fan_pwm', 'fan', 'servo'] and control_out > 0:
            # Auch bei Servo, falls noch jemand Lüfter an Fahrtenregler betreibt.
            if self.pit_out <= self.pit_startup_threshold and control_out < self.pit_startup_min:
                self.logger.info(_(u'Fan startup, 0,5s 25%'))
                self.set_pit(self.pit_startup_min)
                time.sleep(self.pit_startup_time)
                self.pit_out = self.pit_startup_min

        if self.pit_type == 'fan_pwm':
            # 25kHz PC-Lüfter
            # Puls/ Pause berechnen
            pulselength = 47.0
            if not self.pit_inverted:
                if control_out < 0.1:
                    # Zerocut
                    width = 0
                else:
                    width = int(round(self.pit_min + ((self.pit_max - self.pit_min) * (control_out / 100.0))) / (
                        100 / (pulselength - 1)))
            else:
                width = int(round(self.pit_max - ((self.pit_max - self.pit_min) * (control_out / 100.0))) / (
                    100 / (pulselength - 1)))
            # Ohne Impuls = 100%, daher minimum 1!
            width = width + 1
            pause = pulselength - width
            self.logger.debug(_(u'fan_pwm pulse width ') + str(width))
            # Wellenform generieren
            fan_pwm_pulses = []
            fan_pwm_pulses.append(pigpio.pulse(1 << self.pit_gpio, 0, width))
            fan_pwm_pulses.append(pigpio.pulse(0, 1 << self.pit_gpio, pause))
            self.pi.wave_clear()
            self.pi.wave_add_generic(fan_pwm_pulses)
            wave = self.pi.wave_create()
            # Neue Wellenform aktivieren, alte Löschen
            self.pi.wave_send_repeat(wave)
            self.pi.wave_delete(self.fan_pwm)
            self.fan_pwm = wave
        elif self.pit_type == 'fan':
            # Lüftersteuerung v3
            if not self.pit_inverted:
                if control_out < 0.1:
                    # Zerocut
                    width = 0
                else:
                    width = int(round((self.pit_min + (self.pit_max - self.pit_min) * (control_out / 100.0)) * 2.55))
            else:
                width = int(round((self.pit_max - (self.pit_max - self.pit_min) * (control_out / 100.0)) * 2.55))
            self.pi.set_PWM_dutycycle(self.pit_gpio, width)
            self.logger.debug(_(u'fan PWM {} of 255').format(width))
        elif self.pit_type == 'servo':
            # Servosteuerung (oder Lüfter über Fahrtenregler)
            if not self.pit_inverted:
                width = self.servo_limiter(
                    self.pit_servo_min + ((self.pit_servo_max - self.pit_servo_min) * (control_out / 100.0)))
            else:
                width = self.servo_limiter(
                    self.pit_servo_max - ((self.pit_servo_max - self.pit_servo_min) * (control_out / 100.0)))
            self.pi.set_servo_pulsewidth(self.pit_servo_gpio, width)
            self.logger.debug(_(u'servo impulse width {}µs').format(width))
        elif self.pit_type == 'io_pwm':
            # PWM-modulierter Schaltausgang (Schwingungspaketsteuerung)
            # Zyklusdauer in s
            cycletime = 2
            width = (self.pit_min / 100.0 + ((self.pit_max - self.pit_min) / 100.0 * (control_out / 100.0))) * cycletime
            if not self.pit_inverted:
                on = width
                off = cycletime - width
            else:
                on = cycletime - width
                off = width
            with self.pit_io_pwm_lock:
                self.pit_io_pwm_on = on
                self.pit_io_pwm_off = off
            self.logger.debug(_(u'io_pwm impulse width {on}s of {cycletime}s').format(on=on, cycletime=cycletime))
        elif self.pit_type == 'io':
            # Schaltausgang
            if control_out >= 50:
                # Einschalten
                self.logger.debug(_(u'io switching on!'))
                if not self.pit_inverted:
                    self.pi.write(self.pit_gpio, 1)
                else:
                    self.pi.write(self.pit_gpio, 0)
            else:
                # Ausschalten
                self.logger.debug(_(u'io switching off!'))
                if not self.pit_inverted:
                    self.pi.write(self.pit_gpio, 0)
                else:
                    self.pi.write(self.pit_gpio, 1)

        elif self.pit_type == 'damper':
            # Servosteuerung für Damper
            damper_servo_out = clamp(control_out * self.pit_damper_pitch + self.pit_damper_offset, 0, 100)
            if not self.pit_servo_inverted:
                width = self.servo_limiter(
                    self.pit_servo_min + ((self.pit_servo_max - self.pit_servo_min) * (damper_servo_out / 100.0)))
            else:
                width = self.servo_limiter(
                    self.pit_servo_max - ((self.pit_servo_max - self.pit_servo_min) * (damper_servo_out / 100.0)))

            self.pi.set_servo_pulsewidth(self.pit_servo_gpio, width)

            self.logger.debug(_(u'servo impulse width {}µs, {}').format(width, damper_servo_out))
            # Lüftersteuerung v3
            if not self.pit_inverted:
                if control_out < 0.1:
                    # Zerocut
                    width = 0
                else:
                    width = int(round((self.pit_min + (self.pit_max - self.pit_min) * (control_out / 100.0)) * 2.55))
            else:
                width = int(round((self.pit_max - (self.pit_max - self.pit_min) * (control_out / 100.0)) * 2.55))
            self.pi.set_PWM_dutycycle(self.pit_gpio, width)
            self.logger.debug(_(u'fan PWM {} of 255').format(width))

        self.pit_out = control_out

    def io_pwm(self, gpio):
        self.logger.debug(_(u'io_pwm - starting thread'))
        while not self.pit_io_pwm_end.is_set():
            with self.pit_io_pwm_lock:
                on = self.pit_io_pwm_on
                off = self.pit_io_pwm_off
            if on > 0:
                self.pi.write(gpio, 1)
                time.sleep(on)
            if off > 0:
                self.pi.write(gpio, 0)
                time.sleep(off)
        self.logger.debug(_(u'io_pwm - stopping thread'))

    def servo_limiter(self, width):
        # value gets converted to int anyway
        width = int(width)
        #  self.pit_servo_deadband in %, so calculate time in µs
        pit_servo_deadband = self.pit_servo_deadband * ((self.pit_servo_max - self.pit_servo_min) / 100)
        if width == self.pit_servo_current_width:
            # Nothing would have happened, nothing happens
            pass
        elif width == self.pit_servo_max or width == self.pit_servo_min \
                or abs(self.pit_servo_current_width - width) > pit_servo_deadband:
            self.pit_servo_move_count += 1
            self.pit_servo_current_width = width
        elif width != self.pit_servo_wouldbe_width:
            # Save a servo move, save a servo!
            self.pit_servo_nomove_count += 1

        self.pit_servo_wouldbe_width = width

        self.logger.info(
            _(u'Servo move count: {0}, saved {1}').format(self.pit_servo_move_count, self.pit_servo_nomove_count))
        return self.pit_servo_current_width


def check_temp(temp):
    r = 0
    try:
        r = float(temp)
    except ValueError:
        temp = temp[2:]
        r = float(temp)
    return r


def get_steps(steps_str):
    # Generiert aus einem durch Verkettungszeichen ("|") getrennten String
    # von durch Ausrufezeichen getrennten Wertepaaren eine Liste aus Tupeln

    steps = steps_str.split("|")

    retval = []
    for step in steps:
        step_fields = step.split("!")
        try:
            retval.append((float(step_fields[0]), float(step_fields[1])))
        except ValueError:
            logger.error('Illegal step in configuration: ', step_fields[0])
    return retval


def log_uncaught_exceptions(ex_cls, ex, tb):
    global logger
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))


def main(instance):
    global logger

    # Konfigurationsdatei einlesen
    defaults = {'pit_startup_min': '25', 'pit_startup_threshold': '0', 'pit_startup_time': '0.5', 'pit_io_gpio': '2'}
    Config = ConfigParser.SafeConfigParser(defaults)
    for i in range(0, 5):
        while True:
            try:
                Config.read('/var/www/conf/WLANThermo.conf')
            except IndexError:
                time.sleep(1)
                continue
            break

    if instance > 0:
        instance_string = str(instance + 1)
    else:
        instance_string = ''

    LOGFILE = Config.get('daemon_logging', 'log_file')
    logger = logging.getLogger('WLANthermoPIT' + instance_string)
    # Define Logging Level by changing >logger.setLevel(logging.LEVEL_YOU_WANT)< available: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_level = Config.get('daemon_logging', 'level_PIT')
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

    sys.excepthook = log_uncaught_exceptions

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    try:
        pitmaster_hwconfig = {'v1': {0: {'io': 4, 'io_pwm': 4, 'servo': 4, 'fan_pwm': 4}},
                              'v2': {0: {'io': 4, 'io_pwm': 4, 'servo': 4, 'fan_pwm': 4}},
                              'v3': {0: {'io': 4, 'fan': 4, 'io_pwm': 4, 'servo': 4, 'fan_pwm': 4}},
                              'miniV2': {0: {'io': 4, 'fan': 4, 'io_pwm': 4, 'servo': 6, 'fan_pwm': 6},
                                         1: {'io': 5, 'fan': 5, 'io_pwm': 5, 'servo': 12, 'fan_pwm': 12}},
                              'miniplus': {0: {'io': 4, 'fan': 4, 'io_pwm': 4, 'servo': 6, 'fan_pwm': 6}},
                              }[
            Config.get('Hardware', 'version')][instance]
    except KeyError:
        logger.info(u'Instance {} undefined in hardware configuration "{}"').format(instance,
                                                                                    Config.get('Hardware', 'version'))
        return False

    logger.info(_(u'WLANThermoPID started'))

    # GPIO END
    logger.info(_(u'Pitmaster start'))

    # Log Dateinamen aus der config lesen
    current_temp = Config.get('filepath', 'current_temp')
    pitmaster_log = Config.get('filepath', 'pitmaster' + instance_string)

    if Config.get('Hardware', 'version') == u'miniV2':
        channel_count = 12
    else:
        channel_count = 10
    # Pfad aufsplitten
    pitPath, pitFile = os.path.split(pitmaster_log)

    pit_new = 0
    # Wenn das display Verzeichniss im Ram Drive nicht exisitiert erstelle es

    if not os.path.exists(pitPath):
        os.makedirs(pitPath)

    count = 0

    # PID Begin Variablen fuer PID Regelung
    dif = 0
    dif_sum = 0
    dif_last = 0
    ki_alt = 0

    pit_pid_max = 100
    pit_pid_min = 0
    pit_open_lid_detected = False
    pit_open_lid_ref_temp = [0.0, 0.0, 0.0, 0.0, 0.0]
    pit_open_lid_temp = 0
    pit_open_lid_count = 0
    # PID End Variablen fuer PID Regelung

    restart_pit = False
    pit_type = None
    pit_gpio_new = None
    pit_servo_gpio_new = None

    bbqpit = BBQpit(logger)

    config_mtime = 0

    try:
        while True:
            time_start = time.time()
            msg = ""
            # Aktuellen ist wert auslesen
            while True:
                try:
                    tl = codecs.open(current_temp, 'r', 'utf_8')
                except IOError:
                    time.sleep(1)
                    continue
                break
            tline = tl.readline()
            if len(tline) > 5:
                new_config_mtime = os.path.getmtime('/var/www/conf/WLANThermo.conf')
                if new_config_mtime > config_mtime:
                    while True:
                        try:
                            Config.read('/var/www/conf/WLANThermo.conf')
                        except IndexError:
                            time.sleep(1)
                            continue
                        break
                    config_mtime = new_config_mtime

                    logger.debug(_(u'Loading configuration...'))

                    pit_type_new = Config.get('Pitmaster' + instance_string, 'pit_type')

                    if pit_type != pit_type_new:
                        logger.debug(_(u'Setting pit type to: ') + pit_type_new)
                        # GPIO aus der Config
                        pit_servo_gpio_new = pitmaster_hwconfig['servo']
                        if pit_type_new == 'damper':
                            # Damper ist immer fan + servo
                            pit_gpio_new = pitmaster_hwconfig['fan']
                        else:
                            pit_gpio_new = pitmaster_hwconfig[pit_type_new]
                        logger.debug(_(u'Setting pit GPIO to: ') + str(pit_gpio_new))
                        logger.debug(_(u'Setting servo GPIO to: ') + str(pit_servo_gpio_new))
                        restart_pit = True

                    bbqpit.pit_min = Config.getfloat('Pitmaster' + instance_string, 'pit_pwm_min')
                    bbqpit.pit_max = Config.getfloat('Pitmaster' + instance_string, 'pit_pwm_max')
                    bbqpit.pit_servo_min = Config.getfloat('Pitmaster' + instance_string, 'pit_servo_min')
                    bbqpit.pit_servo_max = Config.getfloat('Pitmaster' + instance_string, 'pit_servo_max')

                    bbqpit.pit_startup_min = Config.getfloat('Pitmaster' + instance_string, 'pit_startup_min')
                    bbqpit.pit_startup_threshold = Config.getfloat('Pitmaster' + instance_string,
                                                                   'pit_startup_threshold')
                    bbqpit.pit_startup_time = Config.getfloat('Pitmaster' + instance_string, 'pit_startup_time')

                    pit_inverted_new = Config.getboolean('Pitmaster' + instance_string, 'pit_inverted')
                    pit_servo_inverted_new = Config.getboolean('Pitmaster' + instance_string, 'pit_servo_inverted')
                    pit_damper_offset_new = Config.getfloat('Pitmaster' + instance_string, 'pit_damper_offset')
                    pit_damper_pitch_new = Config.getfloat('Pitmaster' + instance_string, 'pit_damper_pitch')
                    pit_servo_deadband_new = Config.getfloat('Pitmaster' + instance_string, 'pit_servo_deadband')

                    if bbqpit.pit_inverted != pit_inverted_new:
                        bbqpit.pit_inverted = pit_inverted_new

                    if bbqpit.pit_servo_inverted != pit_servo_inverted_new:
                        bbqpit.pit_servo_inverted = pit_servo_inverted_new

                    if bbqpit.pit_damper_offset != pit_damper_offset_new:
                        bbqpit.pit_damper_offset = pit_damper_offset_new

                    if bbqpit.pit_damper_pitch != pit_damper_pitch_new:
                        bbqpit.pit_damper_pitch = pit_damper_pitch_new

                    if bbqpit.pit_servo_deadband != pit_servo_deadband_new:
                        bbqpit.pit_servo_deadband = pit_servo_deadband_new

                    if restart_pit:
                        logger.debug(_(u'Restarting pit...'))
                        pit_type = pit_type_new
                        pit_gpio = pit_gpio_new
                        pit_servo_gpio = pit_servo_gpio_new
                        bbqpit.stop_pit()
                        bbqpit.start_pit(pit_type, pit_gpio, pit_servo_gpio)
                        restart_pit = False

                    pit_steps = get_steps(Config.get('Pitmaster' + instance_string, 'pit_curve'))

                    pit_set = Config.getfloat('Pitmaster' + instance_string, 'pit_set')
                    pit_ch = Config.getint('Pitmaster' + instance_string, 'pit_ch')
                    pit_pause = Config.getfloat('Pitmaster' + instance_string, 'pit_pause')

                    pit_man = Config.getfloat('Pitmaster' + instance_string, 'pit_man')

                    # PID Begin Parameter fuer PID einlesen
                    pit_Kp = Config.getfloat('Pitmaster' + instance_string, 'pit_kp')
                    pit_Kd = Config.getfloat('Pitmaster' + instance_string, 'pit_kd')
                    pit_Ki = Config.getfloat('Pitmaster' + instance_string, 'pit_ki')
                    pit_Kp_a = Config.getfloat('Pitmaster' + instance_string, 'pit_kp_a')
                    pit_Kd_a = Config.getfloat('Pitmaster' + instance_string, 'pit_kd_a')
                    pit_Ki_a = Config.getfloat('Pitmaster' + instance_string, 'pit_ki_a')
                    pit_switch_a = Config.getfloat('Pitmaster' + instance_string, 'pit_switch_a')
                    controller_type = Config.get('Pitmaster' + instance_string, 'pit_controller_type')
                    pit_iterm_min = Config.getfloat('Pitmaster' + instance_string, 'pit_iterm_min')
                    pit_iterm_max = Config.getfloat('Pitmaster' + instance_string, 'pit_iterm_max')
                    pit_open_lid_detection = Config.getboolean('Pitmaster' + instance_string, 'pit_open_lid_detection')
                    pit_open_lid_pause = Config.getfloat('Pitmaster' + instance_string, 'pit_open_lid_pause')
                    pit_open_lid_falling_border = Config.getfloat('Pitmaster' + instance_string,
                                                                  'pit_open_lid_falling_border')
                    pit_open_lid_rising_border = Config.getfloat('Pitmaster' + instance_string,
                                                                 'pit_open_lid_rising_border')
                    pit_ratelimit_rise = Config.getfloat('Pitmaster' + instance_string, 'pit_ratelimit_rise')
                    pit_ratelimit_fall = Config.getfloat('Pitmaster' + instance_string, 'pit_ratelimit_fall')
                    #
                    # PID End Paramter fuer PID einlesen
                    #

                #
                # Aktuelle Temperatur parsen
                #

                temps = tline.split(";")

                if temps[pit_ch + 1 + channel_count] in ('er', 'no'):
                    pit_now = None
                    logger.info(_(u'No signal on channel {}').format(pit_ch))
                    msg += _(u'|no probe connected to channel {}!').format(pit_ch)
                else:
                    try:
                        pit_now = float(check_temp(temps[(pit_ch + 1)]))
                    except ValueError:
                        logger.info(_(u'Error parsing value on channel {}').format(pit_ch))
                        msg += _(u'|no valid value on channel {}!').format(pit_ch)
                        pit_now = None
                #
                # Deckelerkennung
                #

                # Keine Deckelerkennung und kein Fühler für manuelle Einstellung notwendig
                if pit_man > 0:
                    logger.info(_(u'Setting output to {}% manual value').format(str(pit_man)))

                    pit_open_lid_detected = False

                elif pit_now is None:
                    pass

                else:
                    # start open lid detection
                    if pit_open_lid_detection:
                        pit_open_lid_ref_temp[0] = pit_open_lid_ref_temp[1]
                        pit_open_lid_ref_temp[1] = pit_open_lid_ref_temp[2]
                        pit_open_lid_ref_temp[2] = pit_open_lid_ref_temp[3]
                        pit_open_lid_ref_temp[3] = pit_open_lid_ref_temp[4]
                        pit_open_lid_ref_temp[4] = pit_now
                        temp_ref = (pit_open_lid_ref_temp[0] + pit_open_lid_ref_temp[1] + pit_open_lid_ref_temp[2]) / 3

                        # erkennen ob Temperatur wieder eingependelt oder Timeout
                        if pit_open_lid_detected:
                            logger.info(_(u'Open lid detected!'))
                            pit_open_lid_count = pit_open_lid_count - 1
                            if pit_open_lid_count <= 0:
                                logger.info(_(u'Open lid detection: timeout!'))
                                pit_open_lid_detected = False
                                msg += _(u'|timeout open lid detection')
                            elif pit_now > (pit_open_lid_temp * (pit_open_lid_rising_border / 100)):
                                logger.info(_(u'Open lid detection: lid closed again!'))
                                pit_open_lid_detected = False
                                msg += _(u'|lid closed')
                        elif pit_now < (temp_ref * (pit_open_lid_falling_border / 100)):
                            # Wenn Temp innerhalb der letzten beiden Messzyklen den falling Wert unterschreitet
                            logger.info(_(u'Opened lid detected!'))
                            pit_open_lid_detected = True
                            pit_new = 0
                            pit_open_lid_temp = pit_open_lid_ref_temp[
                                0]  # war bsiher pit_now, das ist aber schon zu niedrig
                            msg += _(u'|open lid detected')
                            pit_open_lid_count = pit_open_lid_pause / pit_pause
                    else:
                        # Deckelerkennung nicht aktiv, Status zurücksetzen
                        pit_open_lid_detected = False
                    # end open lid detection
                    msg += _(u'|current: {pit_now}, set: {pit_set}').format(pit_now=pit_now, pit_set=pit_set)
                    calc = 0
                    s = 0

                #
                # Regelschleife
                #

                # Manueller Vorgabe des Ausgangswertes
                if pit_man > 0:
                    pit_new = pit_man

                # Ohne gültigen Eingangswert Ausgang deaktivieren
                elif pit_now is None:
                    logger.error(_(u'Invalid input value!, setting output to 0'))
                    pit_new = 0

                # Suchen und setzen des neuen Reglerwerts Wertekurve
                elif (controller_type == "False") and (not pit_open_lid_detected):  # Bedingung fuer Wertekurve
                    for step, val in pit_steps:
                        if calc == 0:
                            dif = pit_now - pit_set
                            msg += _(u"|dif: ") + str(dif)
                            if (dif <= float(step)):
                                calc = 1
                                msg += _(u"|step: ") + str(step)
                                pit_new = float(val)
                                msg += _(u"|new: ") + str(val)
                            if (pit_now >= pit_set):
                                calc = 1
                                pit_new = 0
                                msg += _(u"|new overshoot: ") + str(pit_new)
                        s = s + 1
                    if calc == 0:
                        msg += _(u"|no matching rule, stop pit!")
                        pit_new = 0
                # PID Begin Block PID Regler Ausgang kann Werte zwischen 0 und 100% annehmen
                elif (controller_type == "PID") and (not pit_open_lid_detected):  # Bedingung fuer PID
                    dif_last = dif
                    dif = pit_set - pit_now
                    # Parameter in Abhaengigkeit der Temp setzen
                    if pit_now > (pit_switch_a / 100 * pit_set):
                        kp = pit_Kp
                        ki = pit_Ki
                        kd = pit_Kd
                    else:
                        kp = pit_Kp_a
                        ki = pit_Ki_a
                        kd = pit_Kd_a
                    # P-Anteil berechnen
                    p_out = kp * dif
                    # D-Anteil berechnen
                    d_input = dif - dif_last
                    d_out = kd * d_input / pit_pause
                    # I-Anteil berechnen
                    # Wenn Ki = 0 nicht berechnen (P/PD-Regler)
                    if ki != 0:
                        # Sprünge im Reglerausgangswert bei Anpassung von Ki vermeiden
                        if ki != ki_alt:
                            dif_sum = (dif_sum * ki_alt) / ki
                            ki_alt = ki
                        # Anti-Windup I-Anteil
                        # Keine Erhöhung I-Anteil wenn Regler bereits an der Grenze ist
                        if not p_out + d_out >= pit_pid_max:
                            dif_sum = dif_sum + float(dif) * pit_pause
                        # Anti-Windup I-Anteil (Limits)
                        if dif_sum * ki > pit_iterm_max:
                            dif_sum = pit_iterm_max / ki
                        elif dif_sum * ki < pit_iterm_min:
                            dif_sum = pit_iterm_min / ki
                        i_out = ki * dif_sum
                    else:
                        # Historie vergessen, da wir nach Ki = 0 von 0 aus anfangen
                        dif_sum = 0
                        i_out = 0
                        ki_alt = 0
                    # PID Berechnung durchfuehren
                    pit_new = p_out + i_out + d_out
                    msg += _(u"|PID values P {p_out}, Iterm {i_out}, d_input {d_input}").format(p_out=p_out,
                                                                                                i_out=i_out,
                                                                                                d_input=d_input)
                    # Stellwert begrenzen
                    if pit_new > pit_pid_max:
                        pit_new = pit_pid_max
                    elif pit_new < pit_pid_min:
                        pit_new = pit_pid_min
                        # PID End Block PID Regler

                pit_change = pit_new - bbqpit.pit_out

                if pit_change > 0 and pit_ratelimit_rise > 0:
                    max_rise = 100 / pit_ratelimit_rise * pit_pause
                    if pit_change > max_rise:
                        pit_new = bbqpit.pit_out + max_rise
                        logger.debug(_(u'Limiting raising rate'))
                elif pit_change < 0 and pit_ratelimit_fall > 0:
                    max_lower = -100 / pit_ratelimit_fall * pit_pause
                    if pit_change < max_lower:
                        pit_new = bbqpit.pit_out + max_lower
                        logger.debug(_(u'Limiting lowering rate'))

                bbqpit.set_pit(pit_new)
                msg += _(u'|New value: ') + str(pit_new)

                # Export das aktuellen Werte in eine Textdatei

                uhrzeit_lang = time.strftime('%d.%m.%y %H:%M:%S')

                if pit_now is None:
                    pit_now_str = ''
                else:
                    pit_now_str = str(pit_now)

                while True:
                    try:
                        with codecs.open(pitPath + '/' + pitFile + '_tmp', 'w', 'utf_8') as fp:
                            # Schreibe mit Trennzeichen ;
                            # Zeit;Soll;Ist;%;msg + pitFile,
                            fp.write(u'{};{};{};{}%;{}'.format(uhrzeit_lang, pit_set, pit_now_str, pit_new, msg))
                            fp.flush()
                            os.fsync(fp.fileno())
                        os.rename(pitPath + '/' + pitFile + '_tmp', pitPath + '/' + pitFile)
                    except IndexError:
                        time.sleep(1)
                        continue
                    break

                if (Config.getboolean('ToDo', 'pit' + instance_string + '_on') == False):
                    if (count > 0):
                        break
                    count = 1

            if len(msg) > 0:
                logger.debug(msg)

            time_remaining = time_start + pit_pause - time.time()
            if time_remaining < 0:
                logger.warning(
                    u'pitmaster loop running longer than {delay}s, remaining time {time_remaining}s'.format(
                        delay=pit_pause,
                        time_remaining=time_remaining))
            else:
                logger.debug(u'pitmaster loop remaining time {time_remaining}s of {delay}s'.format(delay=pit_pause,
                                                                                                   time_remaining=time_remaining))
                time.sleep(time_remaining)

    except KeyboardInterrupt:
        pass
    bbqpit.stop_pit()
    try:
        os.unlink(pitPath + '/' + pitFile)
    except OSError:
        logger.debug(_(u'Error while deleting the pitmaster values'))
    logger.info(_(u'Shutting down WLANThermoPID'))


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


if __name__ == "__main__":
    pid = str(os.getpid())

    if (len(sys.argv) > 1):
        instance = int(sys.argv[1])
    else:
        instance = 0

    pidfilename = '/var/run/' + os.path.basename(__file__).split('.')[0] + '_' + str(instance) + '.pid'

    if os.access(pidfilename, os.F_OK):
        pidfile = open(pidfilename, "r")
        pidfile.seek(0)
        old_pid = int(pidfile.readline())
        if check_pid(old_pid):
            print(_(u"%s already exists, Process is running, exiting") % pidfilename)
            sys.exit()
        else:
            pidfile.seek(0)
            open(pidfilename, 'w').write(pid)

    else:
        open(pidfilename, 'w').write(pid)

    main(instance)

    os.unlink(pidfilename)
