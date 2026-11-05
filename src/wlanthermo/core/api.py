"""Befehls- und Live-Schnittstelle des Kernprozesses (Unix-Socket, JSON-Zeilen).

Anfrage:  {"cmd": "state"}\\n
Antwort:  {"ok": true, "result": {...}}\\n   bzw.   {"ok": false, "error": "..."}\\n

Befehle:
    state                     neueste Messung, Pitmaster, Maverick
    subscribe  [topics]       danach je Änderung eine Zeile {"seq": n, "changes": {...}}
    acknowledge               Alarme quittieren
    test_alert                Testnachricht senden
    config_get [section]      Konfiguration (alle Abschnitte oder einer)
    config_set changes        {"Abschnitt": {"Schlüssel": "Wert"}} unter der Konfig-Sperre setzen
    todo       flag           erlaubtes [ToDo]-Flag setzen (Neustart, Update, ...), der Watchdog führt es aus

Der Socket gehört root:www-data mit Modus 0660: das Webinterface darf ihn
benutzen, andere Benutzer nicht.
"""
import dataclasses
import grp
import json
import logging
import os
import socketserver

from ..config import CONFIG_FILE, make_parser, read_config_file, update_config

logger = logging.getLogger('WLANthermo.api')

SOCKET_PATH = '/run/wlanthermo/core.sock'
SOCKET_GROUP = 'www-data'
# Wie lange subscribe auf eine Änderung wartet, bevor es prüft, ob der Server endet (s)
SUBSCRIBE_POLL = 1

# [ToDo]-Flags, die über die Schnittstelle gesetzt werden dürfen
TODO_FLAGS = ('raspi_reboot', 'raspi_shutdown', 'raspi_v3_shutdown', 'restart_thermo', 'restart_pitmaster',
              'restart_pitmaster2', 'restart_display', 'create_new_log', 'backup', 'check_update',
              'start_system_update', 'start_full_update', 'calibrate_display')


def to_json(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return value


class ApiError(Exception):
    pass


class Api:
    """Die Befehle; unabhängig vom Socket, damit sie sich direkt testen lassen."""

    def __init__(self, hub, comp=None, config_path=CONFIG_FILE):
        self.hub = hub
        self.comp = comp            # Callable -> laufende Comp-Instanz oder None
        self.config_path = config_path

    def state(self):
        _, changes = self.hub.changes(0, timeout=0)
        return {topic: to_json(value) for topic, value in changes.items()}

    def acknowledge(self):
        self._comp().request_acknowledge()

    def test_alert(self):
        self._comp().request_test_alert()

    def _comp(self):
        comp = self.comp() if self.comp is not None else None
        if comp is None:
            raise ApiError('measurement not running')
        return comp

    def config_get(self, section=None):
        config = make_parser()
        read_config_file(config, self.config_path)
        if section is not None:
            if not config.has_section(section):
                raise ApiError('unknown section {}'.format(section))
            return dict(config.items(section, raw=True))
        return {name: dict(config.items(name, raw=True)) for name in config.sections()}

    def config_set(self, changes):
        if not isinstance(changes, dict) or not all(isinstance(v, dict) for v in changes.values()):
            raise ApiError('changes must be {section: {key: value}}')
        for section, values in changes.items():
            for key, value in values.items():
                if not isinstance(value, (str, int, float, bool)) or '\n' in str(value):
                    raise ApiError('invalid value for {}.{}'.format(section, key))
        update_config(changes, self.config_path)
        logger.info('Configuration changed: {}'.format(
            ', '.join('{}.{}'.format(s, k) for s, values in changes.items() for k in values)))

    def todo(self, flag):
        if flag not in TODO_FLAGS:
            raise ApiError('unknown flag {}'.format(flag))
        update_config({'ToDo': {flag: 'True'}}, self.config_path)
        logger.info('ToDo flag set: {}'.format(flag))

    COMMANDS = ('state', 'acknowledge', 'test_alert', 'config_get', 'config_set', 'todo')

    def call(self, request):
        cmd = request.get('cmd')
        if cmd not in self.COMMANDS:
            raise ApiError('unknown command {}'.format(cmd))
        args = {k: v for k, v in request.items() if k != 'cmd'}
        try:
            return getattr(self, cmd)(**args)
        except TypeError as e:
            raise ApiError('invalid arguments: {}'.format(e))


class _Handler(socketserver.StreamRequestHandler):
    def send(self, obj):
        self.wfile.write((json.dumps(obj, default=to_json) + '\n').encode('utf-8'))
        self.wfile.flush()

    def handle(self):
        api = self.server.api
        for line in self.rfile:
            try:
                request = json.loads(line.decode('utf-8'))
                if not isinstance(request, dict):
                    raise ApiError('request must be an object')
                if request.get('cmd') == 'subscribe':
                    self.subscribe(request.get('topics'))
                    return
                self.send({'ok': True, 'result': api.call(request)})
            except (ApiError, ValueError) as e:
                self.send({'ok': False, 'error': str(e)})
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                logger.exception('API request failed')
                self.send({'ok': False, 'error': 'internal error: {}'.format(e)})

    def subscribe(self, topics):
        hub = self.server.api.hub
        # zuerst den aktuellen Stand, dann jede Änderung
        sequence, changes = hub.changes(0, timeout=0, topics=topics)
        self.send({'ok': True, 'seq': sequence, 'changes': changes})
        while not self.server.closing:
            sequence, changes = hub.changes(sequence, timeout=SUBSCRIBE_POLL, topics=topics)
            if changes:
                try:
                    self.send({'seq': sequence, 'changes': changes})
                except (BrokenPipeError, ConnectionResetError):
                    return


class ApiServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, api, path=SOCKET_PATH, group=SOCKET_GROUP):
        self.api = api
        self.path = path
        self.closing = False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            os.unlink(path)
        super().__init__(path, _Handler)
        os.chmod(path, 0o660)
        try:
            os.chown(path, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, OSError) as e:
            logger.warning('Could not give group {} access to {}: {}'.format(group, path, e))

    def close(self):
        self.closing = True
        self.shutdown()
        self.server_close()
        try:
            os.unlink(self.path)
        except OSError:
            pass
