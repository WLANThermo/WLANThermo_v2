#!/usr/bin/python3
# coding=utf-8

# WLANThermo
# wlanthermo-pitmaster (bisher wlt_2_pitmaster.py) - Sets pit temperature by controlling a fan, servo, heater or likely devices.
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

"""Dienst wlanthermo-pitmaster: regelt die Garraumtemperatur über ein Stellglied.

Ein Zyklus (Pitmaster.cycle) läuft alle pit_pause Sekunden: Isttemperatur aus
der Übergabedatei von wlanthermo-comp lesen, Stellwert berechnen, setzen und in
die Pitmaster-Datei schreiben. Mit dem Argument 1 läuft der zweite Pitmaster.
"""
import codecs
import logging
import os
import signal
import sys
import time
import traceback

import pigpio

from ..config import CONFIG_FILE, ConfigWatcher, make_parser, read_config_file
from ..core.hub import PitState, pit_topic
from ..i18n import PITMASTER, translator
from .actuators import GPIOS, Output, create_actuator
from .controller import CONTROLLERS, OpenLidDetector, limit_rate
from .inputs import FileInput, HubInput
from .settings import parse_pitmaster_settings, section_suffix

_ = translator(PITMASTER)

logger = None


class Shutdown(Exception):
    """Wird vom SIGTERM-Handler ausgelöst (systemctl stop), damit die Ausgänge abgeschaltet werden."""


def handle_sigterm(signum, frame):
    raise Shutdown()


def log_uncaught_exceptions(ex_cls, ex, tb):
    logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('{0}: {1}'.format(ex_cls, ex))


class Pitmaster:
    """Regelzyklus eines Pitmasters.

    input liefert die Isttemperatur (FileInput oder HubInput). Mit hub wird
    jeder Zyklus zusätzlich als PitState veröffentlicht. sleep wartet zwischen
    den Zyklen; im Kernprozess ein Event.wait, damit stop() sofort wirkt.
    """

    def __init__(self, instance, gpios, input, pit_file, pi, log, hub=None, sleep=None):
        self.instance = instance
        self.gpios = gpios
        self.input = input
        self.pit_file = pit_file
        self.logger = log
        self.pi = pi
        self.hub = hub
        self.sleep = sleep if sleep is not None else time.sleep
        self.config = ConfigWatcher(CONFIG_FILE, lambda config: parse_pitmaster_settings(config, instance, log))
        self.settings = None
        self.pit_type = None
        self.output = Output(log)
        self.controllers = {name: cls() for name, cls in CONTROLLERS.items()}
        self.lid = OpenLidDetector(log)
        # zuletzt berechneter Stellwert, bleibt z.B. bei offenem Deckel erhalten
        self.target = 0
        # Pitmaster in der Konfiguration abgeschaltet: noch einen Zyklus, dann Ende
        self.off_seen = False
        self.stopping = False

    def stop(self):
        """Beendet run() nach dem laufenden Zyklus (aus einem anderen Thread)."""
        self.stopping = True

    def run(self):
        try:
            while not self.stopping:
                self.cycle()
        except (KeyboardInterrupt, Shutdown):
            pass
        finally:
            # Ausgänge auch nach einem Fehler abschalten, pigpiod behält sonst den letzten Wert
            self.output.stop()
            if self.hub is not None:
                self.hub.publish(pit_topic(self.instance), None)
        try:
            os.unlink(self.pit_file)
        except OSError:
            self.logger.debug(_('Error while deleting the pitmaster values'))
        self.logger.info(_('Shutting down WLANThermoPID'))

    def cycle(self):
        time_start = time.time()
        msg = ''
        if self.input.available():
            settings = self.config.current()
            if settings is not self.settings:
                self.configure(settings)
            now, msg = self.input.value(settings.channel)
            msg += self.control(now)
            self.write_pit_file(now, msg)
            if self.hub is not None:
                self.hub.publish(pit_topic(self.instance), PitState(
                    instance=self.instance, time=time.time(), setpoint=settings.setpoint,
                    current=now, output=self.target, message=msg))
            if not settings.on:
                # Pitmaster wurde abgeschaltet: nach einem weiteren Zyklus beenden
                if self.off_seen:
                    self.stopping = True
                    return
                self.off_seen = True
        if len(msg) > 0:
            self.logger.debug(msg)
        self.wait(time_start)

    def configure(self, settings):
        self.logger.debug(_('Loading configuration...'))
        self.settings = settings
        if self.output.actuator is not None:
            self.output.actuator.configure(settings.actuator)
        if settings.pit_type != self.pit_type:
            self.logger.debug(_('Setting pit type to: ') + settings.pit_type)
            actuator = create_actuator(settings.pit_type, self.gpios, self.pi, settings.actuator, self.logger)
            self.logger.debug(_('Restarting pit...'))
            self.pit_type = settings.pit_type
            self.output.change(actuator)

    def control(self, now):
        """Stellwert berechnen und setzen; liefert die Meldung."""
        s = self.settings
        msg = ''
        if s.manual > 0:
            # Keine Deckelerkennung und kein Fühler für manuelle Einstellung notwendig
            self.logger.info(_('Setting output to {}% manual value').format(str(s.manual)))
            self.lid.reset()
            self.target = s.manual
        elif now is None:
            # Ohne gültigen Eingangswert Ausgang deaktivieren
            self.logger.error(_('Invalid input value!, setting output to 0'))
            self.target = 0
        else:
            opened, lid_msg = self.lid.update(now, s)
            msg += lid_msg
            if opened:
                self.target = 0
            msg += _('|current: {pit_now}, set: {pit_set}').format(pit_now=now, pit_set=s.setpoint)
            controller = self.controllers.get(s.controller_type)
            if controller is not None and not self.lid.detected:
                self.target, controller_msg = controller.compute(now, s)
                msg += controller_msg
        self.target = limit_rate(self.target, self.output.value, s, self.logger)
        self.output.set(self.target)
        msg += _('|New value: ') + str(self.target)
        return msg

    def write_pit_file(self, now, msg):
        # Zeit;Soll;Ist;Stellwert%;Meldung
        line = '{};{};{};{}%;{}'.format(time.strftime('%d.%m.%y %H:%M:%S'), self.settings.setpoint,
                                        '' if now is None else str(now), self.target, msg)
        tmp = self.pit_file + '_tmp'
        try:
            with codecs.open(tmp, 'w', 'utf_8') as fp:
                fp.write(line)
                fp.flush()
                os.fsync(fp.fileno())
            os.rename(tmp, self.pit_file)
        except OSError as e:
            # protokollieren, die Regelung soll weiterlaufen
            self.logger.error('Could not write to file {}: {}'.format(self.pit_file, e))

    def wait(self, time_start):
        delay = self.settings.pause if self.settings is not None else 1
        time_remaining = time_start + delay - time.time()
        if time_remaining < 0:
            self.logger.warning('pitmaster loop running longer than {delay}s, remaining time {time_remaining}s'.format(
                delay=delay, time_remaining=time_remaining))
        else:
            self.logger.debug('pitmaster loop remaining time {time_remaining}s of {delay}s'.format(
                delay=delay, time_remaining=time_remaining))
            self.sleep(time_remaining)


def setup_logging(config, suffix):
    log = logging.getLogger('WLANthermoPIT' + suffix)
    level = config.get('daemon_logging', 'level_PIT')
    if level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        log.setLevel(level)
    if not log.handlers:   # im Kernprozess wird ein Pitmaster mehrfach gestartet
        handler = logging.FileHandler(config.get('daemon_logging', 'log_file'))
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        log.addHandler(handler)
    return log


def create_pitmaster(instance, hub=None, max_age=None, sleep=None):
    """Pitmaster nach der Konfiguration, None wenn die Hardware diese Instanz nicht hat.

    Ohne hub liest er die Übergabedatei von comp, mit hub den DataHub.
    """
    global logger
    config = make_parser()
    read_config_file(config, CONFIG_FILE)
    suffix = section_suffix(instance)
    logger = setup_logging(config, suffix)

    version = config.get('Hardware', 'version')
    try:
        gpios = GPIOS[version][instance]
    except KeyError:
        logger.error('Instance {} undefined in hardware configuration "{}"'.format(instance, version))
        return None

    logger.info(_('WLANThermoPID started'))
    logger.info(_('Pitmaster start'))

    pit_file = config.get('filepath', 'pitmaster' + suffix)
    # liegt im RAM-Laufwerk und fehlt nach einem Neustart
    if not os.path.exists(os.path.dirname(pit_file)):
        os.makedirs(os.path.dirname(pit_file))
    if hub is None:
        input = FileInput(config.get('filepath', 'current_temp'), 12 if version == 'miniV2' else 10, logger)
    else:
        input = HubInput(hub, max_age, logger)
    return Pitmaster(instance, gpios, input, pit_file, pigpio.pi(), logger, hub=hub, sleep=sleep)


def run(instance):
    sys.excepthook = log_uncaught_exceptions
    pitmaster = create_pitmaster(instance)
    if pitmaster is None:
        return False
    pitmaster.run()


def process_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main():
    # Wir laufen als root, auch andere müssen die Config schreiben!
    os.umask(0)

    instance = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    pidfilename = '/var/run/wlt_2_pitmaster_' + str(instance) + '.pid'
    # systemctl stop (Watchdog) sendet SIGTERM
    signal.signal(signal.SIGTERM, handle_sigterm)

    if os.access(pidfilename, os.F_OK):
        with open(pidfilename) as pidfile:
            old_pid = int(pidfile.readline())
        if process_running(old_pid):
            print(_("%s already exists, Process is running, exiting") % pidfilename)
            sys.exit()
    with open(pidfilename, 'w') as pidfile:
        pidfile.write(str(os.getpid()))

    try:
        run(instance)
    finally:
        os.unlink(pidfilename)


if __name__ == '__main__':
    main()
