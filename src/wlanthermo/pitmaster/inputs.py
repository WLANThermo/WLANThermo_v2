"""Woher der Pitmaster die Isttemperatur bekommt.

FileInput liest die Übergabedatei von wlanthermo-comp (Pitmaster als eigener
Prozess), HubInput den neuesten Messwert aus dem DataHub (im Kernprozess).

available() sagt, ob es schon einen Messwert gibt; vorher regelt der Pitmaster
nicht. value() liefert (Isttemperatur oder None, Meldung).
"""
import codecs
import time

from ..core.hub import MEASUREMENT
from ..i18n import PITMASTER, translator

_ = translator(PITMASTER)


def check_temp(temp):
    """Temperatur aus der Übergabedatei; ältere Formate hatten zwei Zeichen vor dem Wert."""
    try:
        return float(temp)
    except ValueError:
        return float(temp[2:])


def no_probe(channel, logger):
    logger.info(_('No signal on channel {}').format(channel))
    return None, _('|no probe connected to channel {}!').format(channel)


class FileInput:
    def __init__(self, path, channel_count, logger):
        self.path = path
        self.channel_count = channel_count
        self.logger = logger
        self.line = ''

    def available(self):
        # Die Datei wird atomar ersetzt; fehlt sie, auf comp warten
        while True:
            try:
                with codecs.open(self.path, 'r', 'utf_8') as f:
                    self.line = f.readline()
                break
            except OSError:
                time.sleep(1)
        return len(self.line) > 5

    def value(self, channel):
        temps = self.line.split(';')
        if temps[channel + 1 + self.channel_count] in ('er', 'no'):
            return no_probe(channel, self.logger)
        try:
            return float(check_temp(temps[channel + 1])), ''
        except ValueError:
            self.logger.info(_('Error parsing value on channel {}').format(channel))
            return None, _('|no valid value on channel {}!').format(channel)


class HubInput:
    """Neuester Messwert aus dem DataHub; ein zu alter Wert gilt als ungültig (Ausgang aus)."""

    def __init__(self, hub, max_age, logger):
        self.hub = hub
        self.max_age = max_age
        self.logger = logger

    def _measurement(self):
        return self.hub.latest(MEASUREMENT)

    def available(self):
        return self._measurement() is not None

    def value(self, channel):
        measurement = self._measurement()
        age = measurement.age()
        if age > self.max_age:
            # comp hängt oder läuft nicht mehr: nicht mit einem alten Wert weiterregeln
            self.logger.error(_('No current measurement for {:.0f}s').format(age))
            return None, _('|no current measurement for {:.0f}s!').format(age)
        statuses = measurement.statuses
        if channel >= len(statuses) or statuses[channel] in ('er', 'no'):
            return no_probe(channel, self.logger)
        temperature = measurement.temperature(channel)
        if temperature is None:
            return no_probe(channel, self.logger)
        # wie in der Übergabedatei auf 2 Stellen gerundet
        return float('%.2f' % temperature), ''
