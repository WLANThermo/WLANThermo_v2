"""Tests für die Schnittstelle des Kernprozesses (wlanthermo.core.api und client).

Start: python3 -m unittest tests/test_api.py
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.config import make_parser, read_config_file  # noqa: E402
from wlanthermo.core.api import Api, ApiError, ApiServer  # noqa: E402
from wlanthermo.core.client import CoreClient, CoreError, CoreUnavailable  # noqa: E402
from wlanthermo.core.hub import MEASUREMENT, DataHub, Measurement, PitState, pit_topic  # noqa: E402


class ApiTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.dir, 'WLANThermo.conf')
        with open(self.config_path, 'w') as f:
            f.write('[ToDo]\nbackup = False\n\n[Pitmaster]\npit_set = 110\npit_curve = -1!0|x%y\n')
        self.hub = DataHub()
        self.comp = mock.Mock()
        self.api = Api(self.hub, comp=lambda: self.comp, config_path=self.config_path)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def config(self):
        config = make_parser()
        read_config_file(config, self.config_path)
        return config


class ApiTest(ApiTestBase):
    def test_state(self):
        self.hub.publish(MEASUREMENT, Measurement(1.0, (20.5, None), ('ok', 'er'), 'celsius'))
        state = self.api.call({'cmd': 'state'})
        self.assertEqual(state['measurement']['temperatures'], (20.5, None))

    def test_acknowledge_and_test_alert_go_to_comp(self):
        self.api.call({'cmd': 'acknowledge'})
        self.api.call({'cmd': 'test_alert'})
        self.comp.request_acknowledge.assert_called_once_with()
        self.comp.request_test_alert.assert_called_once_with()

    def test_without_running_measurement(self):
        api = Api(self.hub, comp=lambda: None, config_path=self.config_path)
        with self.assertRaises(ApiError):
            api.call({'cmd': 'acknowledge'})

    def test_config(self):
        self.assertEqual(self.api.call({'cmd': 'config_get', 'section': 'Pitmaster'})['pit_curve'], '-1!0|x%y')
        self.api.call({'cmd': 'config_set', 'changes': {'Pitmaster': {'pit_set': 120}}})
        self.assertEqual(self.config().get('Pitmaster', 'pit_set'), '120')

    def test_config_rejects_bad_values(self):
        for changes in ({'Pitmaster': {'pit_set': 'a\nb'}}, {'Pitmaster': 'x'}, {'Pitmaster': {'pit_set': [1]}}):
            with self.assertRaises(ApiError):
                self.api.call({'cmd': 'config_set', 'changes': changes})
        self.assertEqual(self.config().get('Pitmaster', 'pit_set'), '110')

    def test_todo_whitelist(self):
        self.api.call({'cmd': 'todo', 'flag': 'backup'})
        self.assertEqual(self.config().get('ToDo', 'backup'), 'True')
        with self.assertRaises(ApiError):
            self.api.call({'cmd': 'todo', 'flag': 'pit_on'})

    def test_unknown_command_and_arguments(self):
        for request in ({'cmd': 'rm'}, {'cmd': 'state', 'x': 1}, {}):
            with self.assertRaises(ApiError):
                self.api.call(request)


class SocketTest(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.dir, 'run', 'core.sock')
        self.server = ApiServer(self.api, self.path, group='nogroup-does-not-exist')
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = CoreClient(self.path, timeout=5)

    def tearDown(self):
        self.server.close()
        super().tearDown()

    def test_permissions(self):
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o660)

    def test_request(self):
        self.hub.publish(pit_topic(0), PitState(0, 1.0, 110.0, 98.0, 40.0, '|x'))
        self.assertEqual(self.client.state()['pit/0']['output'], 40.0)
        self.client.todo('check_update')
        self.assertEqual(self.config().get('ToDo', 'check_update'), 'True')

    def test_errors(self):
        with self.assertRaises(CoreError):
            self.client.todo('pit_on')
        with self.assertRaises(CoreUnavailable):
            CoreClient(os.path.join(self.dir, 'missing.sock')).state()

    def test_subscribe(self):
        self.hub.publish(MEASUREMENT, 'alt')
        events = self.client.subscribe(timeout=3)
        self.assertEqual(next(events), {'measurement': 'alt'})
        threading.Timer(0.1, self.hub.publish, (pit_topic(1), PitState(1, 2.0, 100.0, None, 0, ''))).start()
        threading.Timer(0.2, self.hub.publish, (MEASUREMENT, Measurement(3.0, (1.0,), ('ok',), 'celsius'))).start()
        received = {}
        start = time.monotonic()
        while len(received) < 2 and time.monotonic() - start < 3:
            received.update(next(events))
        self.assertEqual(received['pit/1']['instance'], 1)
        self.assertEqual(received['measurement']['temperatures'], [1.0])
        events.close()

    def test_subscribe_topic_filter(self):
        self.hub.publish(MEASUREMENT, 'm')
        self.hub.publish(pit_topic(0), 'p')
        self.assertEqual(next(self.client.subscribe(topics=['pit/'], timeout=3)), {'pit/0': 'p'})

    def test_many_clients(self):
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.client.config_get('ToDo'))) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        self.assertEqual(len(results), 10)


if __name__ == '__main__':
    unittest.main()
