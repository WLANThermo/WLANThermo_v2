"""Messkanäle: woher die Temperatur eines Kanals kommt.

    Kanal 0-7    Fühler am AD-Wandler (MCP3208)
    Kanal 8-9    Maverick-Funkthermometer
    Kanal 10-11  Thermoelemente am MAX31855 (nur miniV2)
"""
import logging
import statistics

from wlanthermo.sensors import ADC_RANGE, KTypeSensor, median_filter, resistance_from_adc

logger = logging.getLogger('WLANthermo.channels')

# Werte am Rand des Messbereichs: Fühler nicht gesteckt oder Kurzschluss
ADC_MIN = 15
ADC_MAX = 4080
# Ab dieser Streuung der Rohwerte wird gewarnt (Störungen, Wackelkontakt)
MAX_VARIANCE = 4


class AdcInput:
    """Kanäle am AD-Wandler.

    Ab Hardware v2 ist der Spannungsteiler anders herum aufgebaut, dann wird der
    Wert invertiert. Thermoelemente am AD595 liefern eine Spannung und werden
    nie invertiert.
    """

    def __init__(self, adc, version):
        self.adc = adc
        self.inverted_divider = version != 'v1'

    def sample(self, channels, iterations):
        """Rohwerte; die Kanäle werden abwechselnd gemessen, damit Störungen sich verteilen."""
        samples = [[] for _ in channels]
        invert = [self.inverted_divider and not isinstance(ch.sensor, KTypeSensor) for ch in channels]
        for _ in range(iterations):
            for kanal in range(len(channels)):
                value = self.adc.read(kanal)
                samples[kanal].append(ADC_RANGE - 1 - value if invert[kanal] else value)
        return samples

    def read(self, channels, iterations):
        """Temperaturen der Kanäle in °C (None ohne gültigen Wert)."""
        temperatures = []
        for kanal, (channel, raw) in enumerate(zip(channels, self.sample(channels, iterations))):
            median_value = median_filter(raw)
            temperatures.append(self.temperature(channel, median_value))
            variance = statistics.pvariance(raw)
            if variance > MAX_VARIANCE:
                logger.warning('Channel:{kanal} variance: {variance} in {iterations}, median @ {median_value}!'.format(
                    kanal=kanal, variance=variance, iterations=iterations, median_value=median_value))
            logger.debug('Channel {}, MCP3128 {}, temperature {}'.format(kanal, kanal, temperatures[-1]))
        return temperatures

    @staticmethod
    def temperature(channel, adc_value):
        sensor = channel.sensor
        if sensor is None or not ADC_MIN < adc_value < ADC_MAX:
            return None
        if isinstance(sensor, KTypeSensor):
            return sensor.temperature_from_adc(adc_value)
        temperature = sensor.temperature(resistance_from_adc(adc_value, channel.resistor))
        return round(temperature, 2) if temperature is not None else None


class MaverickInput:
    """Die zwei Kanäle des Maverick-Empfängers (siehe maverick.py)."""

    first_channel = 8
    count = 2

    def read(self, values):
        """values: Inhalt von maverick.json oder None, wenn nicht verfügbar."""
        temperatures = []
        for n in range(self.count):
            kanal = self.first_channel + n
            if values is None:
                temperatures.append(None)
                logger.debug('Channel {}, disabled or not available'.format(kanal))
                continue
            value = values['temperature_' + str(n + 1)]
            temperatures.append(None if value == '' else value)
            logger.debug('Channel {}, Maverick {}, temperature {}'.format(kanal, n + 1, temperatures[-1]))
        return temperatures


class ThermocoupleInput:
    """Die Thermoelemente am MAX31855; enabled=False, wenn nicht bestückt."""

    first_channel = 10

    def __init__(self, thermocouples, enabled):
        self.thermocouples = thermocouples
        self.enabled = enabled

    def read(self):
        temperatures = []
        for n, chip in enumerate(self.thermocouples):
            kanal = self.first_channel + n
            if self.enabled:
                temperatures.append(chip.read())
                logger.debug('Channel {}, MAX31855 {}, temperature {}'.format(kanal, n, temperatures[-1]))
            else:
                temperatures.append(None)
                logger.debug('Channel {}, disabled'.format(kanal))
        return temperatures
