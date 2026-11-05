"""Stellglieder des Pitmasters: setzen einen Stellwert von 0-100 % in ein Signal an einem GPIO um.

Die Grenzen und Optionen kommen aus den Einstellungen (ActuatorSettings) und
können sich im Betrieb ändern; sie werden bei jedem Setzen neu gelesen.
"""
import threading
import time
from abc import ABC, abstractmethod

import pigpio

from ..i18n import PITMASTER, translator

_ = translator(PITMASTER)


def clamp(value, minimum, maximum):
    return max(min(maximum, value), minimum)


# GPIOs je Hardware-Version, Pitmaster-Instanz und Stellglied-Typ.
# Der Damper nutzt den GPIO von 'fan' für den Lüfter und den von 'servo' für die Klappe.
GPIOS = {
    'v1': {0: {'io': 4, 'io_pwm': 4, 'servo': 4, 'fan_pwm': 4}},
    'v2': {0: {'io': 4, 'io_pwm': 4, 'servo': 4, 'fan_pwm': 4}},
    'v3': {0: {'io': 4, 'fan': 4, 'io_pwm': 4, 'servo': 4, 'fan_pwm': 4}},
    'miniV2': {0: {'io': 4, 'fan': 4, 'io_pwm': 4, 'servo': 6, 'fan_pwm': 6},
               1: {'io': 5, 'fan': 5, 'io_pwm': 5, 'servo': 12, 'fan_pwm': 12}},
    'miniplus': {0: {'io': 4, 'fan': 4, 'io_pwm': 4, 'servo': 6, 'fan_pwm': 6}},
}


class Actuator(ABC):
    """Ein Stellglied an einem GPIO."""

    #: Lüfter brauchen beim Anlaufen kurz einen Mindestwert (siehe Output.set)
    startup_boost = False

    def __init__(self, pi, gpio, settings, logger):
        self.pi = pi
        self.gpio = gpio
        self.settings = settings   # ActuatorSettings
        self.logger = logger

    def configure(self, settings):
        """Neue Einstellungen (nach dem Neu-Einlesen der Konfiguration)."""
        self.settings = settings

    @abstractmethod
    def start(self):
        """GPIO einrichten und auf den Ruhewert setzen."""

    @abstractmethod
    def set(self, value):
        """Stellwert in % (bereits auf 0-100 begrenzt)."""

    @abstractmethod
    def stop(self):
        """Ausgang abschalten."""


def fan_dutycycle(settings, value):
    """PWM-Tastgrad 0-255 für einen Lüfter, unter 0.1 % ganz aus (nicht invertiert)."""
    s = settings
    if not s.inverted:
        if value < 0.1:
            return 0
        return int(round((s.pwm_min + (s.pwm_max - s.pwm_min) * (value / 100.0)) * 2.55))
    return int(round((s.pwm_max - (s.pwm_max - s.pwm_min) * (value / 100.0)) * 2.55))


class Fan(Actuator):
    """Lüfter über PWM mit 500 Hz (Lüftersteuerung ab v3)."""

    startup_boost = True

    def start(self):
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self.pi.set_PWM_frequency(self.gpio, 500)
        idle = self.settings.pwm_min if not self.settings.inverted else self.settings.pwm_max
        self.pi.set_PWM_dutycycle(self.gpio, idle * 2.55)

    def set(self, value):
        width = fan_dutycycle(self.settings, value)
        self.pi.set_PWM_dutycycle(self.gpio, width)
        self.logger.debug(_('fan PWM {} of 255').format(width))

    def stop(self):
        self.pi.set_PWM_dutycycle(self.gpio, 0)


class FanPwm(Actuator):
    """PC-Lüfter mit 25-kHz-PWM, erzeugt als Wellenform von pigpio."""

    startup_boost = True
    PULSE_LENGTH = 47.0   # µs, 1/47 µs = 21 kHz

    def __init__(self, pi, gpio, settings, logger):
        super().__init__(pi, gpio, settings, logger)
        self.wave = None

    def _send(self, width, pause):
        pulses = [pigpio.pulse(1 << self.gpio, 0, width), pigpio.pulse(0, 1 << self.gpio, pause)]
        self.pi.wave_clear()
        self.pi.wave_add_generic(pulses)
        return self.pi.wave_create()

    def start(self):
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self.wave = self._send(1, 46)
        self.pi.wave_send_repeat(self.wave)

    def set(self, value):
        s = self.settings
        steps = 100 / (self.PULSE_LENGTH - 1)
        if not s.inverted:
            if value < 0.1:
                width = 0
            else:
                width = int(round(s.pwm_min + ((s.pwm_max - s.pwm_min) * (value / 100.0))) / steps)
        else:
            width = int(round(s.pwm_max - ((s.pwm_max - s.pwm_min) * (value / 100.0))) / steps)
        # Ohne Impuls = 100%, daher minimum 1!
        width = width + 1
        pause = int(self.PULSE_LENGTH - width)  # pigpio packt die Pulsdauer als Ganzzahl (struct "III")
        self.logger.debug(_('fan_pwm pulse width ') + str(width))
        # Neue Wellenform aktivieren, alte löschen
        wave = self._send(width, pause)
        self.pi.wave_send_repeat(wave)
        self.pi.wave_delete(self.wave)
        self.wave = wave

    def stop(self):
        self.pi.wave_tx_stop()
        # self.pi.wave_delete(self.wave) # Gives an Error
        self.pi.write(self.gpio, 0)


class ServoLimiter:
    """Unterdrückt kleine Servobewegungen (Totband in % des Stellbereichs), schont das Servo."""

    def __init__(self, logger):
        self.logger = logger
        self.current_width = 0
        self.wouldbe_width = 0
        # Statistik
        self.move_count = 0
        self.nomove_count = 0

    def reset(self):
        self.current_width = 0

    def limit(self, width, s):
        """s: ActuatorSettings"""
        width = int(width)
        deadband = s.servo_deadband * ((s.servo_max - s.servo_min) / 100)
        if width == self.current_width:
            # Nothing would have happened, nothing happens
            pass
        elif width == s.servo_max or width == s.servo_min or abs(self.current_width - width) > deadband:
            self.move_count += 1
            self.current_width = width
        elif width != self.wouldbe_width:
            # Save a servo move, save a servo!
            self.nomove_count += 1
        self.wouldbe_width = width
        self.logger.info(_('Servo move count: {0}, saved {1}').format(self.move_count, self.nomove_count))
        return self.current_width


def servo_width(settings, value, inverted):
    s = settings
    if not inverted:
        return s.servo_min + ((s.servo_max - s.servo_min) * (value / 100.0))
    return s.servo_max - ((s.servo_max - s.servo_min) * (value / 100.0))


class Servo(Actuator):
    """Servo (oder Lüfter über einen Fahrtenregler) am Servo-GPIO."""

    startup_boost = True   # falls noch jemand einen Lüfter am Fahrtenregler betreibt

    def __init__(self, pi, gpio, settings, logger):
        super().__init__(pi, gpio, settings, logger)
        self.limiter = ServoLimiter(logger)

    def start(self):
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self.limiter.reset()
        # Ruhestellung nach pit_servo_inverted, die Stellung in set() aber nach pit_inverted
        idle = self.settings.servo_min if not self.settings.servo_inverted else self.settings.servo_max
        self.pi.set_servo_pulsewidth(self.gpio, idle)

    def set(self, value):
        width = self.limiter.limit(servo_width(self.settings, value, self.settings.inverted), self.settings)
        self.pi.set_servo_pulsewidth(self.gpio, width)
        self.logger.debug(_('servo impulse width {}µs').format(width))

    def stop(self):
        self.pi.set_servo_pulsewidth(self.gpio, 0)


class IoPwm(Actuator):
    """Schaltausgang mit Schwingungspaketsteuerung: Ein/Aus im Verhältnis des Stellwerts, Zyklus 2 s."""

    CYCLE_TIME = 2

    def __init__(self, pi, gpio, settings, logger):
        super().__init__(pi, gpio, settings, logger)
        self.on = 0.0
        self.off = 0.0
        self.lock = threading.Lock()
        self.end = threading.Event()
        self.thread = None

    def start(self):
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self.end.clear()
        self.thread = threading.Thread(target=self.run, args=(self.gpio,))
        self.thread.daemon = True
        # Startwerte nicht 0/0 wg. CPU-Last
        self.on = 1
        self.off = 1
        self.thread.start()

    def set(self, value):
        s = self.settings
        width = (s.pwm_min / 100.0 + ((s.pwm_max - s.pwm_min) / 100.0 * (value / 100.0))) * self.CYCLE_TIME
        if not s.inverted:
            on, off = width, self.CYCLE_TIME - width
        else:
            on, off = self.CYCLE_TIME - width, width
        with self.lock:
            self.on = on
            self.off = off
        self.logger.debug(_('io_pwm impulse width {on}s of {cycletime}s').format(on=on, cycletime=self.CYCLE_TIME))

    def run(self, gpio):
        self.logger.debug(_('io_pwm - starting thread'))
        while not self.end.is_set():
            with self.lock:
                on = self.on
                off = self.off
            if on > 0:
                self.pi.write(gpio, 1)
                time.sleep(on)
            if off > 0:
                self.pi.write(gpio, 0)
                time.sleep(off)
        self.logger.debug(_('io_pwm - stopping thread'))

    def stop(self):
        self.end.set()
        self.thread.join()
        self.pi.write(self.gpio, 0)


class Io(Actuator):
    """Schaltausgang: ab 50 % ein."""

    def _write(self, on):
        self.pi.write(self.gpio, int(on != self.settings.inverted))

    def start(self):
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self._write(False)

    def set(self, value):
        if value >= 50:
            self.logger.debug(_('io switching on!'))
            self._write(True)
        else:
            self.logger.debug(_('io switching off!'))
            self._write(False)

    def stop(self):
        self.pi.write(self.gpio, 0)


class Damper(Actuator):
    """Lüfter mit Klappe: Lüfter am PWM-GPIO, Klappe per Servo mit Versatz und Steigung."""

    def __init__(self, pi, gpio, servo_gpio, settings, logger):
        super().__init__(pi, gpio, settings, logger)
        self.servo_gpio = servo_gpio
        self.limiter = ServoLimiter(logger)

    def start(self):
        s = self.settings
        self.pi.set_mode(self.gpio, pigpio.OUTPUT)
        self.pi.set_PWM_frequency(self.gpio, 500)
        self.pi.set_PWM_dutycycle(self.gpio, (s.pwm_min if not s.inverted else s.pwm_max) * 2.55)
        self.limiter.reset()
        self.pi.set_mode(self.servo_gpio, pigpio.OUTPUT)
        self.pi.set_servo_pulsewidth(self.servo_gpio, s.servo_min if not s.servo_inverted else s.servo_max)

    def set(self, value):
        s = self.settings
        damper_value = clamp(value * s.damper_pitch + s.damper_offset, 0, 100)
        width = self.limiter.limit(servo_width(s, damper_value, s.servo_inverted), s)
        self.pi.set_servo_pulsewidth(self.servo_gpio, width)
        self.logger.debug(_('servo impulse width {}µs, {}').format(width, damper_value))
        width = fan_dutycycle(s, value)
        self.pi.set_PWM_dutycycle(self.gpio, width)
        self.logger.debug(_('fan PWM {} of 255').format(width))

    def stop(self):
        self.pi.set_servo_pulsewidth(self.servo_gpio, 0)
        self.pi.set_PWM_dutycycle(self.gpio, 0)


ACTUATORS = {'fan': Fan, 'fan_pwm': FanPwm, 'servo': Servo, 'io_pwm': IoPwm, 'io': Io}


def create_actuator(pit_type, gpios, pi, settings, logger):
    """Stellglied eines Typs mit den GPIOs der Hardware, None wenn auf der Hardware nicht möglich.

    Ein unbekannter Typ oder ein Typ ohne GPIO auf dieser Hardware löst KeyError aus.
    """
    servo_gpio = gpios['servo']
    if pit_type == 'damper':
        gpio = gpios['fan']
        if gpio == servo_gpio:
            logger.error(_('Damper needs separate GPIOs for fan and servo, not available on this hardware'))
            return None
        return Damper(pi, gpio, servo_gpio, settings, logger)
    cls = ACTUATORS[pit_type]
    return cls(pi, servo_gpio if cls is Servo else gpios[pit_type], settings, logger)


class Output:
    """Stellausgang des Pitmasters: begrenzt auf 0-100 %, Anlaufhilfe, wechselbares Stellglied.

    value ist der zuletzt gesetzte Stellwert; er bleibt beim Wechsel des Stellglieds erhalten.
    """

    def __init__(self, logger):
        self.logger = logger
        self.actuator = None
        self.value = 0.0

    def change(self, actuator):
        self.stop()
        self.actuator = actuator
        if actuator is not None:
            actuator.start()

    def set(self, value):
        s_logger = self.logger
        s_logger.debug(_('Setting pit to {}%').format(value))
        if value > 100:
            s_logger.info(_('Control-out over maximum, limiting to 100%'))
            value = 100.0
        elif value < 0:
            s_logger.info(_('Control-out below minimum, limiting to 0%'))
            value = 0.0

        actuator = self.actuator
        # Anlaufhilfe: aus dem Stillstand kurz mit dem Mindestwert starten
        if actuator is not None and actuator.startup_boost and value > 0:
            s = actuator.settings
            if self.value <= s.startup_threshold and value < s.startup_min:
                s_logger.info(_('Fan startup, 0,5s 25%'))
                self.set(s.startup_min)
                time.sleep(s.startup_time)
                self.value = s.startup_min

        if actuator is not None:
            actuator.set(value)
        self.value = value

    def stop(self):
        if self.actuator is not None:
            self.actuator.stop()
            self.actuator = None
