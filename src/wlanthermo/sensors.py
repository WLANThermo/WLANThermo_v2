"""Temperaturfühler und Aufbereitung der AD-Wandler-Messwerte.

Widerstände werden wie in sensor.conf in kOhm angegeben.
"""
import logging
import math

logger = logging.getLogger('WLANthermo.sensors')

# Auflösung des MCP3208 (12 Bit)
ADC_RANGE = 4096


class NtcSensor:
    """Heißleiter, Kennlinie nach Steinhart-Hart mit den Koeffizienten a, b, c."""

    def __init__(self, name, a, b, c, rn):
        self.name = name
        self.a = a
        self.b = b
        self.c = c
        self.rn = rn

    def temperature(self, resistance):
        """Temperatur in °C, None bei unsinnigen Werten (z.B. Fühler wird gerade gesteckt)."""
        try:
            v = math.log(resistance / self.rn)
            return (1 / (self.a + self.b * v + self.c * v * v)) - 273
        except (ValueError, ZeroDivisionError, OverflowError):
            return None


class PtSensor:
    """Platin-Messwiderstand (PT100/PT1000), Kennlinie nach Callendar-Van Dusen für T >= 0 °C."""

    A = 0.0039083
    B = -0.0000005775

    def __init__(self, name, r0, rkomp=0.0):
        self.name = name
        self.r0 = r0          # Widerstand bei 0 °C
        self.rkomp = rkomp    # Leitungswiderstand, wird abgezogen

    def temperature(self, resistance):
        r = resistance - self.rkomp
        a, b = self.A, self.B
        try:
            return -math.sqrt(r / (self.r0 * b) + a ** 2 / (4 * b ** 2) - 1 / b) - a / (2 * b)
        except (ValueError, ZeroDivisionError, OverflowError):
            return None


class KTypeSensor:
    """Thermoelement Typ K am AD595 (10 mV/°C), gemessen wird direkt die Spannung."""

    def __init__(self, name):
        self.name = name

    def temperature_from_adc(self, adc_value):
        return adc_value * 330 / ADC_RANGE


PT_R0 = {'PT100': 0.1, 'PT1000': 1.0}


def sensor_from_section(section):
    """Erzeugt den Fühler zu einem Abschnitt aus sensor.conf."""
    # Zugriff per [] statt getfloat(): fehlende Werte sollen als KeyError auffallen, nicht als None
    name = section['name']
    if name in PT_R0:
        return PtSensor(name, PT_R0[name], float(section.get('Rkomp', '0')))
    if name == 'KTYPE':
        return KTypeSensor(name)
    return NtcSensor(name, float(section['a']), float(section['b']),
                     float(section['c']), float(section['Rn']))


def load_sensors(config):
    """Alle Fühler aus sensor.conf, Schlüssel ist der Abschnittsname (Nummer als String).

    Fehlerhafte Abschnitte werden protokolliert und ausgelassen.
    """
    sensors = {}
    for key in config.sections():
        try:
            sensors[key] = sensor_from_section(config[key])
        except (KeyError, TypeError, ValueError) as e:
            logger.error('Invalid sensor definition [{}] in sensor.conf: {}'.format(key, e))
    return sensors


def resistance_from_adc(adc_value, series_resistor):
    """Fühlerwiderstand aus dem Spannungsteiler mit dem Messwiderstand (gleiche Einheit)."""
    return series_resistor * ((ADC_RANGE / adc_value) - 1)


def median_filter(raw):
    """Kombinierter Median- und Mittelwertfilter.

    Mittelt um den Median herum über 1 + 2 * (1 + ln(n)) Werte.
    """
    laenge = len(raw)
    sortiert = sorted(raw)
    # Mitte des Arrays finden; Python 2 rundete .5 auf, Python 3 rundet round() zur geraden Zahl
    index = int(math.floor(laenge * 0.5 + 0.5))
    area_groesse = 1 + int(round(math.log(laenge)))
    # max(0, ...): bei sehr wenigen Werten würde der Bereich sonst bei einem negativen Index beginnen
    area = sortiert[max(0, index - area_groesse):index + area_groesse + 1]
    return sum(area) / len(area)
