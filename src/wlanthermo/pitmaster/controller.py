"""Regler des Pitmasters: berechnen aus Ist- und Solltemperatur den Stellwert in %.

Jeder Regler liefert neben dem Stellwert einen Meldungstext für die
Pitmaster-Datei (Teile beginnen mit '|').

Hinweis: Die Typen der Stellwerte (int 0 bzw. 100 oder float) bleiben wie
bisher, sie erscheinen so in der Pitmaster-Datei ("0%" bzw. "0.0%").
"""
from abc import ABC, abstractmethod

from ..i18n import PITMASTER, translator

_ = translator(PITMASTER)

PID_MIN = 0
PID_MAX = 100


class Controller(ABC):
    @abstractmethod
    def compute(self, now, settings):
        """(Stellwert in %, Meldung) zur Isttemperatur now und den PitmasterSettings."""


class StepCurveController(Controller):
    """Wertekurve: der erste Schritt, dessen Abweichung (Ist - Soll) nicht überschritten wird, gibt den Stellwert vor.

    Ab Erreichen der Solltemperatur ist der Ausgang aus.
    """

    def compute(self, now, settings):
        msg = ''
        setpoint = settings.setpoint
        for step, value in settings.curve:
            dif = now - setpoint
            msg += _("|dif: ") + str(dif)
            output = None
            if dif <= float(step):
                msg += _("|step: ") + str(step)
                output = float(value)
                msg += _("|new: ") + str(value)
            if now >= setpoint:
                output = 0
                msg += _("|new overshoot: ") + str(output)
            if output is not None:
                return output, msg
        msg += _("|no matching rule, stop pit!")
        return 0, msg


class PidController(Controller):
    """PID-Regler mit Anti-Windup und eigenen Parametern für das Anheizen (unter switch_a % des Sollwerts)."""

    def __init__(self):
        self.dif = 0          # Regelabweichung des letzten Zyklus
        self.dif_sum = 0      # Integral der Regelabweichung
        self.ki_alt = 0

    def compute(self, now, settings):
        p = settings.pid
        pause = settings.pause
        dif_last = self.dif
        self.dif = dif = settings.setpoint - now
        if now > (p.switch_a / 100 * settings.setpoint):
            kp, ki, kd = p.kp, p.ki, p.kd
        else:
            kp, ki, kd = p.kp_a, p.ki_a, p.kd_a
        p_out = kp * dif
        d_input = dif - dif_last
        d_out = kd * d_input / pause
        # Wenn Ki = 0 nicht berechnen (P/PD-Regler)
        if ki != 0:
            # Sprünge im Reglerausgangswert bei Anpassung von Ki vermeiden
            if ki != self.ki_alt:
                self.dif_sum = (self.dif_sum * self.ki_alt) / ki
                self.ki_alt = ki
            # Anti-Windup: keine Erhöhung des I-Anteils, wenn der Regler bereits an der Grenze ist
            if not p_out + d_out >= PID_MAX:
                self.dif_sum = self.dif_sum + float(dif) * pause
            # Anti-Windup: Grenzen des I-Anteils
            if self.dif_sum * ki > p.iterm_max:
                self.dif_sum = p.iterm_max / ki
            elif self.dif_sum * ki < p.iterm_min:
                self.dif_sum = p.iterm_min / ki
            i_out = ki * self.dif_sum
        else:
            # Historie vergessen, da wir nach Ki = 0 von 0 aus anfangen
            self.dif_sum = 0
            i_out = 0
            self.ki_alt = 0
        output = p_out + i_out + d_out
        msg = _("|PID values P {p_out}, Iterm {i_out}, d_input {d_input}").format(
            p_out=p_out, i_out=i_out, d_input=d_input)
        if output > PID_MAX:
            output = PID_MAX
        elif output < PID_MIN:
            output = PID_MIN
        return output, msg


CONTROLLERS = {'False': StepCurveController, 'PID': PidController}


class OpenLidDetector:
    """Erkennt einen geöffneten Deckel am Temperatursturz und hält die Regelung an.

    Der Deckel gilt als wieder geschlossen, wenn die Temperatur vor dem Öffnen
    (rising_border %) wieder erreicht ist, spätestens nach lid.pause Sekunden.
    """

    def __init__(self, logger):
        self.logger = logger
        self.detected = False
        self.ref_temps = [0.0] * 5
        self.lid_temp = 0
        self.count = 0

    def reset(self):
        self.detected = False

    def update(self, now, settings):
        """(gerade geöffnet, Meldung)"""
        lid = settings.lid
        if not lid.enabled:
            self.detected = False
            return False, ''
        self.ref_temps = self.ref_temps[1:] + [now]
        temp_ref = sum(self.ref_temps[:3]) / 3
        if self.detected:
            # erkennen ob Temperatur wieder eingependelt oder Timeout
            self.logger.info(_('Open lid detected!'))
            self.count = self.count - 1
            if self.count <= 0:
                self.logger.info(_('Open lid detection: timeout!'))
                self.detected = False
                return False, _('|timeout open lid detection')
            if now > (self.lid_temp * (lid.rising_border / 100)):
                self.logger.info(_('Open lid detection: lid closed again!'))
                self.detected = False
                return False, _('|lid closed')
            return False, ''
        if now < (temp_ref * (lid.falling_border / 100)):
            # Wenn Temp innerhalb der letzten beiden Messzyklen den falling Wert unterschreitet
            self.logger.info(_('Opened lid detected!'))
            self.detected = True
            # nicht die aktuelle Temperatur, die ist schon zu niedrig
            self.lid_temp = self.ref_temps[0]
            self.count = lid.pause / settings.pause
            return True, _('|open lid detected')
        return False, ''


def limit_rate(value, last, settings, logger):
    """Begrenzt die Änderung gegenüber dem letzten Stellwert (ratelimit = s für 0 -> 100 %)."""
    change = value - last
    if change > 0 and settings.ratelimit_rise > 0:
        max_rise = 100 / settings.ratelimit_rise * settings.pause
        if change > max_rise:
            logger.debug(_('Limiting raising rate'))
            return last + max_rise
    elif change < 0 and settings.ratelimit_fall > 0:
        max_lower = -100 / settings.ratelimit_fall * settings.pause
        if change < max_lower:
            logger.debug(_('Limiting lowering rate'))
            return last + max_lower
    return value
