"""Widerstandsfühler am AD-Wandler: Heißleiter (NTC) und Platin-Messwiderstände (PT100/PT1000).

Der Fühler bildet mit dem Messwiderstand des Kanals einen Spannungsteiler.
Widerstände werden wie in sensor.conf in kOhm angegeben.
"""
import math
from abc import abstractmethod

from .adc import ADC_RANGE
from .base import TemperatureSensor


def resistance_from_adc(adc_value, series_resistor):
    """Fühlerwiderstand aus dem Spannungsteiler mit dem Messwiderstand (gleiche Einheit)."""
    return series_resistor * ((ADC_RANGE / adc_value) - 1)


class ResistiveProbe(TemperatureSensor):
    """Fühler, dessen Widerstand sich mit der Temperatur ändert."""

    voltage_divider = True

    def __init__(self, name, channel=None, resistor=None):
        self.name = name
        self.channel = channel      # AdcChannel
        self.resistor = resistor    # Messwiderstand in kOhm

    def read(self):
        value = self.channel.value()
        if not self.channel.in_range(value):
            return None
        temperature = self.temperature(resistance_from_adc(value, self.resistor))
        return round(temperature, 2) if temperature is not None else None

    @abstractmethod
    def temperature(self, resistance):
        """Temperatur in °C zum Widerstand in kOhm, None bei unsinnigen Werten."""


class NtcProbe(ResistiveProbe):
    """Heißleiter, Kennlinie nach Steinhart-Hart mit den Koeffizienten a, b, c."""

    def __init__(self, name, a, b, c, rn, channel=None, resistor=None):
        super().__init__(name, channel, resistor)
        self.a = a
        self.b = b
        self.c = c
        self.rn = rn

    def temperature(self, resistance):
        try:
            v = math.log(resistance / self.rn)
            return (1 / (self.a + self.b * v + self.c * v * v)) - 273
        except (ValueError, ZeroDivisionError, OverflowError):
            # z.B. Fühler wird gerade gesteckt
            return None


class PtProbe(ResistiveProbe):
    """Platin-Messwiderstand, Kennlinie nach Callendar-Van Dusen für T >= 0 °C."""

    A = 0.0039083
    B = -0.0000005775

    def __init__(self, name, r0, rkomp=0.0, channel=None, resistor=None):
        super().__init__(name, channel, resistor)
        self.r0 = r0          # Widerstand bei 0 °C
        self.rkomp = rkomp    # Leitungswiderstand, wird abgezogen

    def temperature(self, resistance):
        r = resistance - self.rkomp
        a, b = self.A, self.B
        try:
            return -math.sqrt(r / (self.r0 * b) + a ** 2 / (4 * b ** 2) - 1 / b) - a / (2 * b)
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
