"""Hardware der WLANThermo-Platine über pigpio: AD-Wandler, Thermoelement-Wandler, Summer.

Der MCP3208 und die MAX31855 hängen an einem per Software erzeugten SPI-Bus
(bit banging), damit die Hardware-SPI-Schnittstelle frei bleibt.
"""
import logging
import time
from struct import pack, unpack

import pigpio
from bitstring import BitArray

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


class Mcp3208:
    """12-Bit-AD-Wandler mit 8 Kanälen."""

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


class Max31855:
    """Wandler für ein Thermoelement Typ K."""

    def __init__(self, pi, cs):
        self.pi = pi
        self.cs = cs

    def read(self):
        """Temperatur in °C, None bei einem Fehler (z.B. kein Thermoelement angeschlossen)."""
        data = BitArray(self.pi.bb_spi_xfer(self.cs, b'\x00\x00')[1])
        if data[15]:
            return None
        return data[0:14].int / 4.0


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
