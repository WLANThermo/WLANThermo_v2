"""AD-Wandler MCP3208 und die Aufbereitung seiner Messwerte.

Die Fühler an den Kanälen 0-7 werden in jedem Messzyklus mehrfach abgetastet
(AdcSampler), jeder Fühler wertet dann den gefilterten Wert seines Kanals aus.
"""
import logging
import math
import statistics
from struct import pack, unpack

logger = logging.getLogger('WLANthermo.sensors')

# Auflösung des MCP3208 (12 Bit)
ADC_RANGE = 4096
# Werte am Rand des Messbereichs: Fühler nicht gesteckt oder Kurzschluss
ADC_MIN = 15
ADC_MAX = 4080
# Ab dieser Streuung der Rohwerte wird gewarnt (Störungen, Wackelkontakt)
MAX_VARIANCE = 4


class Mcp3208:
    """12-Bit-AD-Wandler mit 8 Kanälen am Software-SPI-Bus von pigpio."""

    channels = 8

    def __init__(self, pi, cs):
        self.pi = pi
        self.cs = cs

    def read(self, channel):
        if not 0 <= channel < self.channels:
            raise ValueError('MCP3208 has no channel {}'.format(channel))
        # Startbit, Single-Ended, 3 Bit Kanal
        command = pack('>Hx', (0x18 + channel) << 6)
        return unpack('>xH', self.pi.bb_spi_xfer(self.cs, command)[1])[0] & 0x0FFF


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


class AdcChannel:
    """Ein Kanal des AD-Wandlers mit den Rohwerten des aktuellen Messzyklus."""

    def __init__(self, index):
        self.index = index
        self.samples = []

    def value(self):
        """Gefilterter Rohwert (0..4095)."""
        return median_filter(self.samples)

    def in_range(self, value):
        return ADC_MIN < value < ADC_MAX


class AdcSampler:
    """Tastet alle Kanäle des AD-Wandlers ab.

    Ab Hardware v2 ist der Spannungsteiler anders herum aufgebaut, dann wird der
    Wert von Fühlern mit Spannungsteiler invertiert.
    """

    def __init__(self, adc, version):
        self.adc = adc
        self.inverted_divider = version != 'v1'
        self.channels = [AdcChannel(index) for index in range(adc.channels)]

    def sample(self, voltage_divider, iterations):
        """voltage_divider: je Kanal, ob dort ein Fühler mit Spannungsteiler hängt.

        Die Kanäle werden abwechselnd gemessen, damit Störungen sich verteilen.
        """
        invert = [self.inverted_divider and divider for divider in voltage_divider]
        for channel in self.channels:
            channel.samples = []
        for _ in range(iterations):
            for channel in self.channels:
                value = self.adc.read(channel.index)
                channel.samples.append(ADC_RANGE - 1 - value if invert[channel.index] else value)
        for channel in self.channels:
            variance = statistics.pvariance(channel.samples)
            if variance > MAX_VARIANCE:
                logger.warning('Channel:{kanal} variance: {variance} in {iterations}, median @ {median_value}!'.format(
                    kanal=channel.index, variance=variance, iterations=iterations, median_value=channel.value()))
