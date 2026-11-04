"""Hardware der WLANThermo-Platine über pigpio: AD-Wandler, Thermoelement-Wandler, Summer.

Der MCP3208 und die MAX31855 hängen an einem per Software erzeugten SPI-Bus
(bit banging), damit die Hardware-SPI-Schnittstelle frei bleibt.
"""
import logging
import time

import pigpio

from ..sensors.adc import Mcp3208
from ..sensors.thermocouple import Max31855

logger = logging.getLogger('WLANthermo.hardware')

# GPIO-Belegung (BCM)
SCLK = 18      # Serial-Clock
MOSI = 24      # Master-Out-Slave-In
MISO = 23      # Master-In-Slave-Out
CS_MCP = 25    # Chip-Select MCP3208
CS_MAX = (8, 7)  # Chip-Select MAX31855 IC1 und IC2
BEEPER = 17    # Summer
PWM = 4        # Pitmaster
IO = 2         # Pitmaster

MCP_BAUD = 20000
MAX_BAUD = 250000


class Beeper:
    def __init__(self, pi, gpio):
        self.pi = pi
        self.gpio = gpio

    def beep(self, count=1, on=0.2, off=0.2):
        for i in range(count):
            if i:
                time.sleep(off)
            self.pi.write(self.gpio, 1)
            time.sleep(on)
            self.pi.write(self.gpio, 0)


class Board:
    """Verbindung zu pigpiod mit allen Bausteinen; schließt beim Verlassen alle SPI-Busse.

        with Board() as board:
            board.adc.read(0)
    """

    def __init__(self, pi_factory=pigpio.pi):
        self.pi_factory = pi_factory
        self.pi = None

    def __enter__(self):
        self.pi = self.pi_factory()
        if not self.pi.connected:
            raise RuntimeError('Could not connect to pigpiod, is pigpiod.service running?')
        self._open_spi(CS_MCP, MCP_BAUD)
        for cs in CS_MAX:
            self._open_spi(cs, MAX_BAUD)
        self.adc = Mcp3208(self.pi, CS_MCP)
        self.thermocouples = [Max31855(self.pi, cs) for cs in CS_MAX]
        # Pitmaster-Ausgänge aus, bis der Pitmaster-Dienst sie übernimmt
        for gpio in (PWM, IO, BEEPER):
            self.pi.set_mode(gpio, pigpio.OUTPUT)
        self.pi.write(PWM, 0)
        self.pi.write(IO, 0)
        self.beeper = Beeper(self.pi, BEEPER)
        return self

    def __exit__(self, *exc):
        for cs in (CS_MCP,) + CS_MAX:
            self._close_spi(cs)
        self.pi.stop()
        return False

    def _open_spi(self, cs, baud):
        # Ist der Bus noch von einem vorherigen Lauf offen, kann er weiter benutzt werden
        try:
            self.pi.bb_spi_open(cs, MISO, MOSI, SCLK, baud, 0)
        except pigpio.error as e:
            if e.value != pigpio.error_text(pigpio.PI_GPIO_IN_USE):
                raise

    def _close_spi(self, cs):
        try:
            self.pi.bb_spi_close(cs)
        except pigpio.error as e:
            logger.warning('Could not close SPI on CS {}: {}'.format(cs, e))
