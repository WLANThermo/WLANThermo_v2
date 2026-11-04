"""Alarmauswertung: Grenzwerte je Kanal, Quittierung und Zeitplan der Benachrichtigungen."""
import enum
import logging

logger = logging.getLogger('WLANthermo.alarm')


class _MissingKeys(dict):
    def __missing__(self, key):
        logger.error('Key "{key_name}" not found in template!'.format(key_name=key))
        return '!!' + key + '!!'


def safe_format(template, args):
    """str.format(), unbekannte Platzhalter werden als !!name!! ausgegeben.

    Die Vorlagen kommen vom Benutzer. Ein Fehler in einer Vorlage darf die
    Messschleife nicht beenden, dann wird die Vorlage unverändert geliefert.
    """
    try:
        return template.format_map(_MissingKeys(args))
    except (ValueError, IndexError, AttributeError, TypeError) as e:
        logger.error('Invalid template "{}": {}'.format(template, e))
        return template


class AlarmState(enum.Enum):
    OK = 'ok'
    HI = 'hi'          # über dem oberen Grenzwert, nicht quittiert
    HI_ACK = 'hi_ack'  # über dem oberen Grenzwert, quittiert
    LO = 'lo'
    LO_ACK = 'lo_ack'


class ChannelStatus(enum.Enum):
    """Status eines Kanals in einem Messzyklus, wie er in die Übergabedatei geschrieben wird."""
    OK = 'ok'
    HI = 'hi'
    LO = 'lo'
    ERROR = 'er'       # kein Messwert


class Evaluation:
    """Ergebnis eines Messzyklus."""

    def __init__(self, statuses, active, new):
        self.statuses = statuses  # ChannelStatus je Kanal
        self.active = active      # irgendwo ein nicht quittierter Alarm
        self.new = new            # neuer Alarm in diesem Zyklus


class AlarmMonitor:
    """Zustand der Grenzwertalarme aller Kanäle.

    Ein Alarm bleibt aktiv, bis er quittiert wird oder die Temperatur wieder
    innerhalb der Grenzen liegt. Ohne Messwert bleibt der Zustand erhalten.
    """

    def __init__(self, channel_count):
        self.states = [AlarmState.OK] * channel_count

    def acknowledge(self):
        for kanal, state in enumerate(self.states):
            if state == AlarmState.HI:
                logger.debug('Acknowledging temperature over upper limit on channel {}'.format(kanal))
                self.states[kanal] = AlarmState.HI_ACK
            elif state == AlarmState.LO:
                logger.debug('Acknowledging temperature under lower limit on channel {}'.format(kanal))
                self.states[kanal] = AlarmState.LO_ACK

    def evaluate(self, temperatures, temp_min, temp_max):
        statuses = []
        active = False
        new = False
        for kanal, temperature in enumerate(temperatures):
            if temperature is None:
                statuses.append(ChannelStatus.ERROR)
                continue
            if temperature >= temp_max[kanal]:
                status, alarm, acked = ChannelStatus.HI, AlarmState.HI, AlarmState.HI_ACK
            elif temperature <= temp_min[kanal]:
                status, alarm, acked = ChannelStatus.LO, AlarmState.LO, AlarmState.LO_ACK
            else:
                statuses.append(ChannelStatus.OK)
                self.states[kanal] = AlarmState.OK
                continue
            state = self.states[kanal]
            if state == alarm:
                active = True
            elif state != acked:
                active = True
                new = True
                self.states[kanal] = alarm
            statuses.append(status)
        return Evaluation(statuses, active, new)


class NotificationSchedule:
    """Wann Benachrichtigungen verschickt werden.

    - bei einem neuen Alarm oder einem Testalarm sofort
    - solange ein Alarm aktiv ist alle alarm_interval Sekunden erneut
    - sonst alle status_interval Sekunden eine Statusmeldung
    Ein Intervall von 0 schaltet die Wiederholung bzw. die Statusmeldung ab.
    Jede verschickte Nachricht startet beide Intervalle neu.
    """

    def __init__(self):
        self.last_sent = 0

    def check(self, evaluation, test, alarm_interval, status_interval, now):
        """Liefert (repeat, status, send) und merkt sich den Zeitpunkt, wenn gesendet wird."""
        repeat = (evaluation.active and alarm_interval > 0
                  and self.last_sent + alarm_interval < now)
        status = (not repeat and status_interval > 0
                  and self.last_sent + status_interval < now)
        send = evaluation.new or test or repeat or status
        if send:
            self.last_sent = now
        return repeat, status, send
