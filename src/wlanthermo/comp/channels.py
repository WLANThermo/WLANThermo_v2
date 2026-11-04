"""Belegung der Messkanäle: welcher Fühler an welchem Kanal hängt.

    Kanal 0-7    Fühler am AD-Wandler (Typ aus sensor.conf, je Kanal einstellbar)
    Kanal 8-9    Maverick-Funkthermometer
    Kanal 10-11  Thermoelemente am MAX31855 (nur miniV2)
"""
import logging

from ..sensors.adc import AdcSampler
from ..sensors.maverick import MaverickFile, MaverickProbe
from ..sensors.thermocouple import Max31855Thermocouple

logger = logging.getLogger('WLANthermo.channels')

ADC_CHANNELS = 8
MAVERICK_CHANNELS = 2


class Channels:
    """Die Fühler aller Kanäle, None wo kein Fühler verfügbar ist."""

    def __init__(self, startup, board):
        self.sampler = AdcSampler(board.adc, startup.version)
        self.maverick = MaverickFile() if startup.maverick else None
        maverick_probes = [MaverickProbe(self.maverick, n + 1) if self.maverick else None
                           for n in range(MAVERICK_CHANNELS)]
        thermocouples = []
        if startup.version == 'miniV2':
            thermocouples = [Max31855Thermocouple(chip) if startup.max31855 else None
                             for chip in board.thermocouples]
        # Fühler, die nicht von der Konfiguration abhängen
        self.fixed = maverick_probes + thermocouples
        self.settings = None
        self.adc_probes = []

    def update(self):
        """Einmal je Messzyklus vor dem Messen: Werte des Maverick-Empfängers lesen."""
        if self.maverick is None:
            logger.info('Maverick is disabled')
            return
        logger.info('Reading from Maverick receiver...')
        self.maverick.update()

    def configure(self, settings):
        """Fühler am AD-Wandler nach den Einstellungen; nur bei geänderten Einstellungen neu."""
        if settings is self.settings:
            return
        self.settings = settings
        self.adc_probes = []
        for channel, adc_channel in zip(settings.channels[:ADC_CHANNELS], self.sampler.channels):
            sensor_type = channel.sensor_type
            self.adc_probes.append(sensor_type.create(adc_channel, channel.resistor)
                                   if sensor_type is not None else None)

    @property
    def sensors(self):
        return self.adc_probes + self.fixed

    def measure(self, iterations):
        """Temperaturen aller Kanäle in °C, None ohne Wert."""
        self.sampler.sample([probe is not None and probe.voltage_divider for probe in self.adc_probes],
                            iterations)
        temperatures = []
        for kanal, sensor in enumerate(self.sensors):
            temperature = sensor.read() if sensor is not None else None
            logger.debug('Channel {}, {}, temperature {}'.format(kanal, sensor, temperature))
            temperatures.append(temperature)
        return temperatures
