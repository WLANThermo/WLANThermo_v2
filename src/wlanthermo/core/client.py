"""Client für die Schnittstelle des Kernprozesses (siehe api.py), z.B. für Webinterface und Displays."""
import json
import socket

from .api import SOCKET_PATH


class CoreError(Exception):
    """Der Kernprozess hat die Anfrage abgelehnt."""


class CoreUnavailable(CoreError):
    """Der Kernprozess läuft nicht oder antwortet nicht."""


class CoreClient:
    def __init__(self, path=SOCKET_PATH, timeout=10):
        self.path = path
        self.timeout = timeout

    def _connect(self, timeout):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(self.path)
        except OSError as e:
            sock.close()
            raise CoreUnavailable('wlanthermo-core not reachable: {}'.format(e))
        return sock

    @staticmethod
    def _send(sock, request):
        sock.sendall((json.dumps(request) + '\n').encode('utf-8'))

    def request(self, cmd, **args):
        """Ein Befehl; liefert das Ergebnis oder löst CoreError aus."""
        with self._connect(self.timeout) as sock:
            self._send(sock, dict(args, cmd=cmd))
            with sock.makefile('rb') as f:
                line = f.readline()
        if not line:
            raise CoreUnavailable('no answer from wlanthermo-core')
        answer = json.loads(line.decode('utf-8'))
        if not answer.get('ok'):
            raise CoreError(answer.get('error'))
        return answer.get('result')

    def subscribe(self, topics=None, timeout=None):
        """Generator: zuerst der aktuelle Stand, dann jede Änderung als {Thema: Wert}.

        timeout: höchstens so lange auf die nächste Änderung warten (None = ohne Ende).
        """
        sock = self._connect(self.timeout)
        try:
            self._send(sock, {'cmd': 'subscribe', 'topics': topics})
            sock.settimeout(timeout)
            with sock.makefile('rb') as f:
                for line in f:
                    event = json.loads(line.decode('utf-8'))
                    if event.get('ok') is False:
                        raise CoreError(event.get('error'))
                    yield event['changes']
        except socket.timeout:
            return
        finally:
            sock.close()

    # Abkürzungen
    def state(self):
        return self.request('state')

    def acknowledge(self):
        return self.request('acknowledge')

    def test_alert(self):
        return self.request('test_alert')

    def config_get(self, section=None):
        return self.request('config_get', section=section)

    def config_set(self, changes):
        return self.request('config_set', changes=changes)

    def todo(self, flag):
        return self.request('todo', flag=flag)
