"""Quellen für wlanthermo-comp aus dem DataHub statt aus Dateien (im Kernprozess)."""
import logging

from ..comp.datafiles import PitValues
from ..sensors.maverick import MAX_AGE
from .hub import pit_topic

logger = logging.getLogger('WLANthermo.core')

MAVERICK = 'maverick'


class MaverickHubSource:
    """Wie MaverickFile, aber mit dem neuesten Reading des Empfänger-Threads."""

    def __init__(self, hub, max_age=MAX_AGE):
        self.hub = hub
        self.max_age = max_age
        self.values = None

    def update(self):
        reading = self.hub.latest(MAVERICK)
        if reading is None:
            self.values = None
        elif reading.age() > self.max_age:
            logger.debug('Maverick values too old, {} sec'.format(reading.age()))
            self.values = None
        else:
            self.values = reading.as_dict()


class PitHubReader:
    """Wie PitmasterReader: Stellwert und Sollwert eines Pitmasters, None wenn er nicht läuft.

    Die Werte sind Texte wie in der Pitmaster-Datei.
    """

    def __init__(self, hub, instance):
        self.hub = hub
        self.instance = instance

    def read(self):
        state = self.hub.latest(pit_topic(self.instance))
        if state is None:
            return None
        return PitValues(new=str(state.output), set=str(state.setpoint))
