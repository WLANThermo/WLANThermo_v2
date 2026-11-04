"""Thermoelemente Typ K: am Verstärker AD595 (über den AD-Wandler) oder am Wandler MAX31855."""
from bitstring import BitArray

from .adc import ADC_RANGE
from .base import TemperatureSensor


class Ad595Thermocouple(TemperatureSensor):
    """Thermoelement am AD595 (10 mV/°C), gemessen wird direkt die Spannung."""

    voltage_divider = False

    def __init__(self, name, channel=None, resistor=None):
        self.name = name
        self.channel = channel   # AdcChannel; resistor wird nicht gebraucht

    def read(self):
        value = self.channel.value()
        if not self.channel.in_range(value):
            return None
        return self.temperature_from_adc(value)

    @staticmethod
    def temperature_from_adc(adc_value):
        return adc_value * 330 / ADC_RANGE


class Max31855:
    """Wandler für ein Thermoelement Typ K am Software-SPI-Bus von pigpio."""

    def __init__(self, pi, cs):
        self.pi = pi
        self.cs = cs

    def read(self):
        """Temperatur in °C, None bei einem Fehler (z.B. kein Thermoelement angeschlossen)."""
        data = BitArray(self.pi.bb_spi_xfer(self.cs, b'\x00\x00')[1])
        if data[15]:
            return None
        return data[0:14].int / 4.0


class Max31855Thermocouple(TemperatureSensor):
    name = 'MAX31855'

    def __init__(self, chip):
        self.chip = chip

    def read(self):
        return self.chip.read()
