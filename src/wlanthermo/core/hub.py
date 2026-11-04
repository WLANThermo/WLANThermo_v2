"""Datenaustausch zwischen den Diensten im Kernprozess.

Jeder Wert liegt unter einem Thema ('measurement', 'pit/0', ...) mit einer
fortlaufenden Nummer. Verbraucher holen den neuesten Wert (latest) oder warten
auf Änderungen seit einer Nummer (changes) - so geht keine Änderung verloren.

Die Werte sind unveränderliche Dataclasses mit Zeitstempel, damit jeder
Verbraucher prüfen kann, ob ein Wert noch aktuell ist.
"""
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

MEASUREMENT = 'measurement'


def pit_topic(instance):
    return 'pit/{}'.format(instance)


@dataclass(frozen=True)
class Measurement:
    """Ein Messzyklus von wlanthermo-comp."""
    time: float
    temperatures: Tuple[Optional[float], ...]   # je Kanal, in der eingestellten Einheit
    statuses: Tuple[str, ...]                   # 'ok', 'hi', 'lo', 'er' je Kanal
    unit: str                                   # 'celsius' oder 'fahrenheit'

    def age(self, now=None):
        return (time.time() if now is None else now) - self.time

    def temperature(self, channel):
        """Temperatur eines Kanals, None ohne Wert oder bei unbekanntem Kanal."""
        if 0 <= channel < len(self.temperatures):
            return self.temperatures[channel]
        return None


@dataclass(frozen=True)
class PitState:
    """Ein Regelzyklus eines Pitmasters."""
    instance: int
    time: float
    setpoint: float
    current: Optional[float]   # Isttemperatur, None ohne gültigen Wert
    output: float              # Stellwert in %
    message: str

    def age(self, now=None):
        return (time.time() if now is None else now) - self.time


class DataHub:
    def __init__(self):
        self._condition = threading.Condition()
        self._sequence = 0
        self._values = {}   # Thema -> (Nummer, Wert)

    def publish(self, topic, value):
        with self._condition:
            self._sequence += 1
            self._values[topic] = (self._sequence, value)
            self._condition.notify_all()

    def latest(self, topic):
        with self._condition:
            entry = self._values.get(topic)
        return entry[1] if entry else None

    @property
    def sequence(self):
        with self._condition:
            return self._sequence

    def changes(self, since, timeout=None, topics=None):
        """(Nummer, {Thema: Wert}) aller Themen, die sich nach since geändert haben.

        Wartet höchstens timeout Sekunden auf eine Änderung, ohne Änderung ist das
        Ergebnis leer. topics schränkt auf bestimmte Themen ein (Präfixe, z.B. 'pit/').
        """
        def changed():
            return {topic: value for topic, (sequence, value) in self._values.items()
                    if sequence > since and (topics is None or topic.startswith(tuple(topics)))}

        with self._condition:
            self._condition.wait_for(lambda: changed(), timeout)
            return self._sequence, changed()
