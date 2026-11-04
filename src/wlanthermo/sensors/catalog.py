"""Fühlertypen aus sensor.conf.

Ein Fühlertyp beschreibt die Kennlinie (z.B. die Koeffizienten eines NTC). Erst
create() bindet ihn an einen Kanal des AD-Wandlers und dessen Messwiderstand.
"""
import logging

from .resistive import NtcProbe, PtProbe
from .thermocouple import Ad595Thermocouple

logger = logging.getLogger('WLANthermo.sensors')

PT_R0 = {'PT100': 0.1, 'PT1000': 1.0}   # kOhm bei 0 °C


class SensorType:
    def __init__(self, name, probe_class, **parameters):
        self.name = name
        self.probe_class = probe_class
        self.parameters = parameters

    @property
    def voltage_divider(self):
        """Ob der Fühler mit dem Messwiderstand einen Spannungsteiler bildet."""
        return self.probe_class.voltage_divider

    def create(self, channel, resistor):
        """Fühler an einem AdcChannel mit Messwiderstand in kOhm."""
        return self.probe_class(self.name, channel=channel, resistor=resistor, **self.parameters)

    def __repr__(self):
        return '<SensorType {} {}>'.format(self.name, self.probe_class.__name__)


def sensor_type_from_section(section):
    """Fühlertyp zu einem Abschnitt aus sensor.conf."""
    # Zugriff per [] statt getfloat(): fehlende Werte sollen als KeyError auffallen, nicht als None
    name = section['name']
    if name in PT_R0:
        return SensorType(name, PtProbe, r0=PT_R0[name], rkomp=float(section.get('Rkomp', '0')))
    if name == 'KTYPE':
        return SensorType(name, Ad595Thermocouple)
    return SensorType(name, NtcProbe, a=float(section['a']), b=float(section['b']),
                      c=float(section['c']), rn=float(section['Rn']))


def load_sensor_types(config):
    """Alle Fühlertypen aus sensor.conf, Schlüssel ist der Abschnittsname (Nummer als String).

    Fehlerhafte Abschnitte werden protokolliert und ausgelassen.
    """
    sensor_types = {}
    for key in config.sections():
        try:
            sensor_types[key] = sensor_type_from_section(config[key])
        except (KeyError, TypeError, ValueError) as e:
            logger.error('Invalid sensor definition [{}] in sensor.conf: {}'.format(key, e))
    return sensor_types
