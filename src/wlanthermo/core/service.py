"""Dienst wlanthermo-core: Messung, Pitmaster und Maverick-Empfänger als Threads in einem Prozess.

    Messung (comp) ──Measurement──▶ DataHub ──▶ Pitmaster 1/2 ──PitState──▶ DataHub ──▶ comp
    Maverick-Empfänger ──Reading──▶ DataHub ──▶ comp

Die Dateien für Webinterface und Displays (current.temp, pit.temp, TEMPLOG.csv)
schreiben comp und Pitmaster weiterhin. Der Pitmaster schaltet seinen Ausgang
ab, wenn keine aktuelle Messung mehr kommt.

Fällt ein Thread mit einem Fehler aus, beendet sich der ganze Prozess geordnet
(Ausgänge aus) mit Exit-Code 1, systemd startet ihn neu (Restart=on-failure).
"""
import logging
import os
import signal
import sys
import threading
import traceback

import pigpio

from ..comp import service as comp_service
from ..comp.hardware import Board
from ..config import CONFIG_FILE, ConfigWatcher, update_config
from ..pitmaster import service as pitmaster_service
from ..pitmaster.settings import section_suffix
from ..sensors.maverick.receiver import MaverickReceiver
from .hub import DataHub
from .sources import MAVERICK

logger = logging.getLogger('WLANthermo.core')

PIDFILE = '/var/run/wlanthermo-core.pid'
# Wie oft die Verwaltung die Konfiguration prüft (s)
MANAGER_INTERVAL = 1
MAVERICK_PIN = 22


class Shutdown(Exception):
    """Wird vom SIGTERM-Handler ausgelöst."""


def handle_sigterm(signum, frame):
    raise Shutdown()


def max_measurement_age(delay):
    """Ab welchem Alter der Pitmaster eine Messung nicht mehr benutzt.

    Ein Messzyklus dauert delay, mindestens aber 1 s Systemlast + Abtastung +
    Summer; drei verpasste Zyklen gelten als Ausfall.
    """
    return max(15, 3 * (delay + 2))


class ServiceThread(threading.Thread):
    """Thread für einen Dienst; ein Fehler wird protokolliert und an den Kern gemeldet."""

    def __init__(self, name, target, on_failure):
        super().__init__(name=name, daemon=True)
        self._target_function = target
        self.on_failure = on_failure

    def run(self):
        try:
            self._target_function()
        except Exception:
            logger.critical('{} failed:\n{}'.format(self.name, traceback.format_exc()))
            self.on_failure(self.name)


class ManagedSettings:
    """Was die Verwaltung aus der Konfiguration braucht."""

    def __init__(self, config):
        self.version = config.get('Hardware', 'version')
        self.pitmaster_count = 2 if self.version == 'miniV2' else 1
        self.pit_on = [config.getboolean('ToDo', 'pit' + section_suffix(i) + '_on')
                       for i in range(self.pitmaster_count)]
        self.restart_pit = [config.getboolean('ToDo', 'restart_pitmaster' + section_suffix(i), fallback=False)
                            for i in range(self.pitmaster_count)]
        self.maverick = config.getboolean('ToDo', 'maverick_enabled')
        self.delay = config.getfloat('Messen', 'delay')


class Manager:
    """Startet und stoppt Pitmaster und Maverick-Empfänger nach [ToDo] (bisher Aufgabe des Watchdogs)."""

    def __init__(self, hub, on_failure, create_pitmaster=None, create_receiver=None, config_path=CONFIG_FILE):
        self.hub = hub
        self.on_failure = on_failure
        self.create_pitmaster = create_pitmaster or self._create_pitmaster
        self.create_receiver = create_receiver or self._create_receiver
        self.config_path = config_path
        self.config = ConfigWatcher(config_path, ManagedSettings)
        self.pitmasters = {}      # Instanz -> (Pitmaster, Thread, Stop-Event)
        self.receiver = None
        self.receiver_pi = None

    def _create_pitmaster(self, instance, max_age, stop_event):
        return pitmaster_service.create_pitmaster(instance, hub=self.hub, max_age=max_age, sleep=stop_event.wait)

    def _create_receiver(self):
        self.receiver_pi = pigpio.pi()
        return MaverickReceiver(self.receiver_pi, lambda reading: self.hub.publish(MAVERICK, reading),
                                pin=MAVERICK_PIN)

    def check(self):
        settings = self.config.current()
        for instance in range(settings.pitmaster_count):
            running = self.running(instance)
            if settings.restart_pit[instance]:
                logger.info('Restart pitmaster {}'.format(instance + 1))
                self.stop_pitmaster(instance)
                update_config({'ToDo': {'restart_pitmaster' + section_suffix(instance): 'False'}}, self.config_path)
                running = False
            if settings.pit_on[instance] and not running:
                self.start_pitmaster(instance, max_measurement_age(settings.delay))
            elif not settings.pit_on[instance] and running:
                self.stop_pitmaster(instance)
        if settings.maverick and self.receiver is None:
            logger.info('Start Maverick receiver')
            self.receiver = self.create_receiver()
            self.receiver.start()
        elif not settings.maverick and self.receiver is not None:
            self.stop_receiver()

    def running(self, instance):
        entry = self.pitmasters.get(instance)
        if entry is None:
            return False
        if not entry[1].is_alive():
            # hat sich selbst beendet (z.B. pit_on in der Konfiguration aus)
            del self.pitmasters[instance]
            return False
        return True

    def start_pitmaster(self, instance, max_age):
        stop_event = threading.Event()
        pitmaster = self.create_pitmaster(instance, max_age, stop_event)
        if pitmaster is None:
            return
        logger.info('Start pitmaster {}'.format(instance + 1))
        thread = ServiceThread('pitmaster{}'.format(instance + 1), pitmaster.run, self.on_failure)
        self.pitmasters[instance] = (pitmaster, thread, stop_event)
        thread.start()

    def stop_pitmaster(self, instance, timeout=10):
        entry = self.pitmasters.pop(instance, None)
        if entry is None:
            return
        pitmaster, thread, stop_event = entry
        logger.info('Stop pitmaster {}'.format(instance + 1))
        pitmaster.stop()
        stop_event.set()
        thread.join(timeout)
        if thread.is_alive():
            logger.error('Pitmaster {} did not stop within {}s'.format(instance + 1, timeout))

    def stop_receiver(self):
        logger.info('Stop Maverick receiver')
        self.receiver.stop()
        self.receiver = None
        if self.receiver_pi is not None:
            self.receiver_pi.stop()
            self.receiver_pi = None

    def stop(self):
        for instance in list(self.pitmasters):
            self.stop_pitmaster(instance)
        if self.receiver is not None:
            self.stop_receiver()


class Core:
    def __init__(self, startup, sensor_types, board_factory=Board):
        self.startup = startup
        self.sensor_types = sensor_types
        self.board_factory = board_factory
        self.hub = DataHub()
        self.stop_event = threading.Event()
        self.failed = []
        self.comp = None
        self.manager = Manager(self.hub, self.fail)

    def fail(self, name):
        self.failed.append(name)
        self.stop_event.set()

    def run_comp(self):
        with self.board_factory() as board:
            self.comp = comp_service.Comp(self.startup, self.sensor_types, board, hub=self.hub,
                                          sleep=self.stop_event.wait)
            if self.stop_event.is_set():
                return
            self.comp.run()

    def run_manager(self):
        while not self.stop_event.is_set():
            self.manager.check()
            self.stop_event.wait(MANAGER_INTERVAL)

    def run(self):
        """Läuft bis stop() oder bis ein Dienst ausfällt; True bei Ausfall."""
        threads = [ServiceThread('comp', self.run_comp, self.fail),
                   ServiceThread('manager', self.run_manager, self.fail)]
        for thread in threads:
            thread.start()
        try:
            while not self.stop_event.wait(1):
                pass
        finally:
            self.shutdown(threads)
        return bool(self.failed)

    def stop(self):
        self.stop_event.set()

    def shutdown(self, threads):
        logger.info('Shutting down')
        self.stop_event.set()
        if self.comp is not None:
            self.comp.stop()
        # zuerst die Pitmaster (Ausgänge aus), dann die Messung
        for thread in threads:
            if thread.name == 'manager':
                thread.join(5)
        self.manager.stop()
        for thread in threads:
            thread.join(30)
            if thread.is_alive():
                logger.error('{} did not stop'.format(thread.name))


def main():
    startup, sensor_types = comp_service.prepare()
    comp_service.claim_pidfile(PIDFILE)
    sys.excepthook = comp_service.log_uncaught_exceptions
    core = Core(startup, sensor_types)
    signal.signal(signal.SIGTERM, handle_sigterm)
    failed = False
    try:
        failed = core.run()
    except (KeyboardInterrupt, Shutdown):
        logger.info('WLANThermo stopped!')
    finally:
        try:
            os.unlink(PIDFILE)
        except OSError:
            pass
        logging.shutdown()
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
