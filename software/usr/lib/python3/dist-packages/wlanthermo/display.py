"""Zugriff auf das Nextion-Display für die WLANThermo-Dienste.

Das Protokoll (Verbindungsaufbau, Befehle, Antworten, Ereignisse, Firmware-
Upload) übernimmt die Bibliothek ``nextion`` von PyPI (LGPLv3). Sie arbeitet
mit asyncio, die WLANThermo-Dienste arbeiten mit Threads. ``Display`` lässt
die Bibliothek deshalb in einem eigenen Thread laufen und bietet den Threads
der Dienste einfache, blockierende Aufrufe an.

Zusätzlich zu den Standard-Ereignissen kennt die WLANThermo-Display-Firmware
eigene Meldungen, die die Bibliothek nicht kennt:

* ``0x40 area id``          Werte sollen aus dem Display gelesen werden
* ``0x41 area id action``   Sonderkommando
* ``0x66 page``             aktuelle Seite, vom Display von sich aus gesendet

Ereignisse landen als ``{'type': ..., 'data': {...}}`` in ``Display.events``.
"""
import asyncio
import concurrent.futures
import fcntl
import logging
import os
import queue
import threading

from nextion import CommandFailed, CommandTimeout, ConnectionFailed, Nextion
from nextion.protocol import NextionProtocol

EVT_READ_CMD = 0x40
EVT_CUSTOM_CMD = 0x41
EVT_CURRENT_PAGE = 0x66
_EXTRA_EVENTS = (EVT_READ_CMD, EVT_CUSTOM_CMD, EVT_CURRENT_PAGE)

# Namen der Standard-Ereignisse (Typ-Code der Bibliothek -> Name)
_EVENT_NAMES = {
    0x65: 'touch_event',
    0x67: 'touch_coord',
    0x68: 'touch_coord_sleep',
    0x86: 'sleep',
    0x87: 'wakeup',
    0x88: 'startup',
    0x89: 'sdupgrade',
}

# Variablen ohne Komponentenname, die als Zahl gesetzt werden
SYSTEM_VARS = frozenset(['rtc0', 'rtc1', 'rtc2', 'rtc3', 'rtc4', 'rtc5', 'rtc6', 'dim', 'dims'])

# Obergrenze für einen blockierenden Aufruf (Sekunden). Die Bibliothek hat
# eigene, kürzere Timeouts; das hier fängt nur hängende Aufrufe ab.
CALL_TIMEOUT = 30
CONNECT_TIMEOUT = 90

ENCODING = 'iso-8859-1'  # das Display kennt nur Latin-1


class PortBusy(OSError):
    """Die serielle Schnittstelle wird von einem anderen Prozess benutzt."""


def lock_port(port, blocking=True):
    """Sperrt die serielle Schnittstelle gegen andere WLANThermo-Prozesse.

    Gibt den Dateideskriptor zurück, der die Sperre hält (``os.close()``
    gibt sie frei). Ohne ``blocking`` kommt sofort ``PortBusy``.
    """
    fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
    except OSError as e:
        os.close(fd)
        raise PortBusy('Serial port {} is busy'.format(port)) from e
    return fd


class _Protocol(NextionProtocol):
    """Erkennt zusätzlich die WLANThermo-eigenen Meldungen als Ereignisse."""

    def is_event(self, message):
        if len(message) > 0 and message[0] in _EXTRA_EVENTS:
            return True
        return super().is_event(message)


class WLTNextion(Nextion):
    """``nextion.Nextion`` mit den WLANThermo-Ereignissen.

    Greift auf ``_make_protocol`` und ``_attempt_connect_messages`` der
    Bibliothek zu, deshalb ist ihre Version in der Paketabhängigkeit fest
    eingeschränkt (siehe DEBIAN/control).
    """

    def __init__(self, *args, extra_event_handler=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._extra_event_handler = extra_event_handler
        self.comok = None

    def _make_protocol(self):
        return _Protocol(event_message_handler=self._dispatch_message)

    def _dispatch_message(self, message):
        if message[0] in _EXTRA_EVENTS:
            if self._extra_event_handler:
                self._extra_event_handler(message)
        else:
            self.event_message_handler(message)

    async def _attempt_connect_messages(self, delay_between_connect_attempts):
        result = await super()._attempt_connect_messages(delay_between_connect_attempts)
        if result and result[:6] == b'comok ':
            self.comok = result
        return result

    @property
    def device_info(self):
        """Modell, Firmware, Seriennummer und Flashgröße aus der Antwort auf ``connect``."""
        if not self.comok:
            return None
        data = self.comok[7:].decode(ENCODING).strip('\xff\x00').split(',')
        return {'model': data[2], 'firmware': data[3], 'serial': data[5], 'flash_size': data[6]}


class Display:
    """Blockierende Schnittstelle zum Display, benutzbar aus mehreren Threads."""

    def __init__(self, logger=None):
        self.log = logger or logging.getLogger(__name__)
        # Vom Display gesendete Ereignisse im Format {'type': ..., 'data': {...}}
        self.events = queue.Queue()
        # Gesetzt, solange das Display wach ist
        self.wake_event = threading.Event()
        # Zuletzt über switchpage() angeforderte Seite
        self.page = None
        # Die Verbindung ist endgültig verloren (Bibliothek konnte nicht neu verbinden)
        self.failed = False
        self._loop = None
        self._thread = None
        self._client = None
        self._lock_fd = None

    # -- Lebenszyklus ------------------------------------------------------

    def start(self, port, baudrate, blocking=True):
        """Verbindet mit dem Display und weckt es auf. ``False`` bei Misserfolg."""
        try:
            self._lock_fd = lock_port(port, blocking)
        except PortBusy as e:
            self.log.error(str(e))
            return False
        except OSError as e:
            self.log.error('Cannot open serial port {}: {}'.format(port, e))
            return False

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name='nextion-asyncio', daemon=True)
        self._thread.start()
        try:
            self._call(self._connect(port, int(baudrate)), CONNECT_TIMEOUT)
        except (ConnectionFailed, CommandTimeout, CommandFailed, OSError) as e:
            self.log.error('Cannot connect to the display: {}'.format(e))
            self.stop()
            return False
        self.wake_event.set()
        return True

    def stop(self):
        if self._loop is not None:
            if self._client is not None:
                try:
                    self._call(self._client.disconnect(), 5)
                except Exception as e:
                    self.log.debug('Error while disconnecting: {}'.format(e))
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(5)
            if not self._thread.is_alive():
                self._loop.close()
            self._loop = None
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive() and not self.failed

    @property
    def device_info(self):
        return self._client.device_info if self._client else None

    @property
    def sleeping(self):
        return self._client.is_sleeping() if self._client else None

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self, port, baudrate):
        # Erst im Loop-Thread anlegen, ältere asyncio-Versionen binden Lock/Queue an den aktuellen Loop
        self._client = WLTNextion(
            port, baudrate,
            event_handler=self._on_event,
            extra_event_handler=self._on_extra_event,
            encoding=ENCODING)
        await self._client.connect()
        await self._client.wakeup()

    def _call(self, coro, timeout=CALL_TIMEOUT):
        """Führt eine Coroutine der Bibliothek im Loop-Thread aus und wartet darauf."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            if future.done():
                raise  # Timeout aus der Bibliothek selbst (asyncio.TimeoutError)
            future.cancel()
            raise CommandTimeout('No answer within {} s'.format(timeout))
        except ConnectionFailed:
            self.failed = True
            raise

    # -- Ereignisse vom Display (laufen im Loop-Thread) ----------------------

    def _on_event(self, type_, data):
        code = int(type_)
        name = _EVENT_NAMES.get(code)
        if name is None:
            return
        payload = {}
        if code == 0x65:
            payload = {'page': data.page_id, 'button': data.component_id,
                       'event': ['release', 'press'][data.touch_event]}
        elif code in (0x67, 0x68):
            payload = {'x': data.x, 'y': data.y, 'event': ['release', 'press'][data.touch_event]}
        elif code == 0x86:
            self.wake_event.clear()
        elif code == 0x87:
            self.wake_event.set()
        self.log.debug('Display event {}: {}'.format(name, payload))
        self.events.put({'type': name, 'data': payload})

    def _on_extra_event(self, message):
        code = message[0]
        try:
            if code == EVT_READ_CMD:
                event = {'type': 'read_cmd', 'data': {'area': message[1], 'id': message[2]}}
            elif code == EVT_CUSTOM_CMD:
                event = {'type': 'custom_cmd', 'data': {'area': message[1], 'id': message[2], 'action': message[3]}}
            else:
                event = {'type': 'current_page', 'data': {'page': message[1]}}
        except IndexError:
            self.log.warning('Truncated message 0x{:02x} from the display'.format(code))
            return
        self.log.debug('Display event {type}: {data}'.format(**event))
        self.events.put(event)

    # -- Aufrufe aus den Diensten --------------------------------------------

    @staticmethod
    def _text(value):
        """Zahlen kompakt (22.0 -> 22), alles andere als Text; nur Latin-1."""
        try:
            text = '%.12g' % float(value)
        except (TypeError, ValueError):
            text = str(value)
        else:
            if '.' in text:
                text = text.rstrip('0').rstrip('.')
        return text.encode(ENCODING, 'replace').decode(ENCODING)

    def sendvalues(self, values):
        """Setzt Werte. Schlüssel ``komponente.attribut`` oder ``komponente.txt:länge``.

        Auf ``txt`` endende Schlüssel sind Text (optional auf ``länge`` gekürzt),
        auf ``val`` endende sowie ``rtc0`` ... ``dims`` Zahlen. ``True`` wenn
        das Display alles angenommen hat. Schläft das Display, merkt sich die
        Bibliothek die Werte und sendet sie nach dem Aufwachen.
        """
        ok = True
        for rawkey, value in values.items():
            key, _, length = rawkey.partition(':')
            length = int(length) if length else None
            try:
                if key.endswith('txt'):
                    value = self._text(value)[:length]
                elif key.endswith('val') or key in SYSTEM_VARS:
                    value = int(value)
                else:
                    self.log.warning('Unknown type of variable: {}'.format(key))
                    continue
            except (TypeError, ValueError):
                self.log.warning('Invalid value for {}: {!r}'.format(key, value))
                ok = False
                continue
            self.log.debug('Sending {} to the display: {}'.format(key, value))
            try:
                self._call(self._client.set(key, value))
            except CommandTimeout:
                self.log.warning('Timeout - display possibly in sleep mode')
                return False
            except (CommandFailed, ConnectionFailed) as e:
                self.log.warning('Display rejected {}: {}'.format(key, e))
                ok = False
        return ok

    def getvalue(self, key):
        """Liest einen Wert (Zahl oder Text). ``None`` bei einem Fehler."""
        self.log.debug('Get {} from the display'.format(key))
        try:
            value = self._call(self._client.get(key))
        except (CommandFailed, CommandTimeout, ConnectionFailed) as e:
            self.log.warning('Could not read {} from the display: {}'.format(key, e))
            return None
        self.log.debug('Got {!r} from the display'.format(value))
        return value

    def getvalues(self, keys):
        """Liest mehrere Werte; nicht lesbare fehlen im Ergebnis."""
        result = {}
        for key in keys:
            value = self.getvalue(key)
            if value is not None:
                result[key] = value
        return result

    def sendcmd(self, command):
        """Sendet einen Befehl, z. B. ``page main``. ``True`` bei Erfolg."""
        self.log.debug('Send command {} to the display'.format(command))
        try:
            self._call(self._client.command(str(command)))
        except (CommandFailed, CommandTimeout, ConnectionFailed) as e:
            self.log.warning('Command {} failed: {}'.format(command, e))
            return False
        return True

    def switchpage(self, page):
        if not self.sendcmd('page {}'.format(page)):
            return False
        self.page = page
        return True

    def upload_firmware(self, file, baudrate, timeout=900):
        """Überträgt eine ``.tft``-Datei (geöffnet mit ``open(..., 'rb')``) ins Display."""
        self._call(self._client.upload_firmware(file, baudrate), timeout)

    def wakeup(self):
        """Weckt das Display auf (``sleep=0``) und sendet aufgeschobene Werte."""
        try:
            self._call(self._client.wakeup())
        except (CommandFailed, CommandTimeout, ConnectionFailed) as e:
            self.log.warning('Wake up failed: {}'.format(e))
            return False
        self.wake_event.set()
        return True
