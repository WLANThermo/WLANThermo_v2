"""Tests für das Webinterface (wlanthermo.web) mit dem Flask-Testclient und einem Kernprozess-Socket.

Start: python3 -m unittest tests/test_web.py   (benötigt: pip install flask psutil)
"""
import html.parser
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from werkzeug.datastructures import MultiDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.config import make_parser, read_config_file  # noqa: E402
from wlanthermo.core.api import Api, ApiServer  # noqa: E402
from wlanthermo.core.hub import MEASUREMENT, DataHub, Measurement, PitState, pit_topic  # noqa: E402
from wlanthermo.web import create_app, helpers  # noqa: E402

WWW = os.path.join(os.path.dirname(__file__), '..', 'software', 'var', 'www')


class FormParser(html.parser.HTMLParser):
    """Sammelt, was ein Browser beim Absenden des ersten Formulars schicken würde."""

    def __init__(self):
        super().__init__()
        self.fields = []
        self.forms = 0
        self.select = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.forms += 1
        if self.forms != 1:
            return
        if tag == 'input' and a.get('name') and a.get('type') not in ('submit', 'file'):
            if a.get('type') == 'checkbox':
                if 'checked' in a:
                    self.fields.append((a['name'], a.get('value', 'on')))
            else:
                self.fields.append((a['name'], a.get('value', '')))
        elif tag == 'select':
            self.select = [a.get('name'), None, None]
        elif tag == 'option' and self.select is not None:
            if self.select[2] is None:
                self.select[2] = a.get('value')
            if 'selected' in a:
                self.select[1] = a.get('value')

    def handle_endtag(self, tag):
        if tag == 'select' and self.select is not None and self.forms == 1:
            name, selected, first = self.select
            if name and (selected or first) is not None:
                self.fields.append((name, selected if selected is not None else first))
            self.select = None


class WebTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.www = os.path.join(self.dir, 'www')
        for name in ('conf', 'lang', 'images'):
            shutil.copytree(os.path.join(WWW, name), os.path.join(self.www, name))
        os.makedirs(os.path.join(self.www, 'tmp', 'display'))
        os.makedirs(os.path.join(self.www, 'thermoplot'))
        self.log_dir = os.path.join(self.dir, 'log')
        os.makedirs(self.log_dir)
        self.config_file = os.path.join(self.www, 'conf', 'WLANThermo.conf')
        self.current_temp = os.path.join(self.www, 'tmp', 'display', 'current.temp')
        self.socket = os.path.join(self.dir, 'core.sock')
        self.hub = DataHub()
        self.comp = mock.Mock()
        self.server = ApiServer(Api(self.hub, comp=lambda: self.comp), self.socket, group='nogroup-x')
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.app = create_app({'WWW_ROOT': self.www, 'CONFIG_FILE': self.config_file,
                               'SENSOR_FILE': os.path.join(self.www, 'conf', 'sensor.conf'),
                               'LOG_DIR': self.log_dir, 'CORE_SOCKET': self.socket, 'SECRET_KEY': 'test',
                               'CURRENT_TEMP': self.current_temp, 'TESTING': True})
        self.client = self.app.test_client()

    def tearDown(self):
        self.server.close()
        shutil.rmtree(self.dir)

    def config(self):
        config = make_parser()
        read_config_file(config, self.config_file)
        return config

    def set_config(self, **values):
        config = self.config()
        for key, value in values.items():
            section, option = key.split('__')
            config.set(section, option, value)
        with open(self.config_file, 'w') as f:
            config.write(f)

    def publish_measurement(self, temps=(74.21, None, 20.0) + (25.0,) * 7, statuses=None):
        statuses = statuses or tuple('ok' if t is not None else 'er' for t in temps)
        self.hub.publish(MEASUREMENT, Measurement(time.time(), temps, statuses, 'celsius'))


class PagesTest(WebTestBase):
    def test_all_pages_render(self):
        for url in ('/', '/index.php', '/info.php', '/thermolog.php', '/control/reboot.php', '/control/shutdown.php',
                    '/control/new_log_file.php', '/control/update.php', '/control/config.php'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn(b'<div id="wrapper">', response.data, url)

    def test_translation(self):
        self.set_config(locale__locale='de_DE')
        self.assertIn('Einstellungen'.encode(), self.client.get('/control/config.php').data)
        self.set_config(locale__locale='en_US')
        self.assertIn(b'Settings', self.client.get('/control/config.php').data)

    def test_config_values_are_escaped(self):
        self.set_config(ch_name__ch_name0='Kern"><script>alert(1)</script>')
        data = self.client.get('/control/config.php').data
        self.assertNotIn(b'<script>alert(1)</script>', data)
        self.assertIn(b'Kern&#34;&gt;&lt;script&gt;', data)


class MainTest(WebTestBase):
    def test_temperatures_and_alarm(self):
        self.set_config(temp_max__temp_max0='60', web_alert__ch0='True', ch_show__ch0='True', ch_show__ch1='True')
        self.publish_measurement()
        data = self.client.get('/main.php').data.decode()
        self.assertIn('74.2°C', data)
        self.assertIn('temperature_indicator_red', data)
        self.assertIn('buzzer.mp3', data)                       # Browser-Alarm
        self.assertEqual(data.count('class="channel_view"'), 1 + sum(
            self.config().getboolean('ch_show', 'ch%d' % i) for i in range(2, 10)))   # Kanal 1 ohne Wert

    def test_mute_acknowledges_in_core(self):
        self.set_config(temp_max__temp_max0='60', web_alert__ch0='True', ch_show__ch0='True')
        self.publish_measurement()
        self.client.get('/session.php?websoundalert=False')
        self.comp.request_acknowledge.assert_called_once_with()
        data = self.client.get('/main.php').data.decode()
        self.assertIn('speaker_mute.png', data)
        self.assertNotIn('buzzer.mp3', data)

    def test_pitmaster_values(self):
        self.set_config(ToDo__pit_on='True', Pitmaster__pit_ch='0', ch_show__ch0='True')
        self.publish_measurement()
        self.hub.publish(pit_topic(0), PitState(0, time.time(), 110.0, 74.21, 45.0, '|x'))
        data = self.client.get('/main.php').data.decode()
        self.assertIn('45.0% / 110.0°C', data)
        self.assertIn('Last regulation on', data) if 'Last regulation on' in data else None

    def test_core_not_running(self):
        self.server.close()
        self.assertEqual(self.client.get('/main.php').status_code, 200)

    def test_update_status(self):
        open(os.path.join(self.www, 'tmp', 'update'), 'w').close()
        self.assertIn(b'showLoading', self.client.get('/main.php').data)

    def test_app_json(self):
        self.publish_measurement()
        data = json.loads(self.client.get('/app.php').data)
        self.assertEqual(data['channel']['0']['temp'], 74.21)
        self.assertEqual(data['channel']['1']['state'], 'er')
        self.assertRegex(data['timestamp'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$')

    def test_events(self):
        self.publish_measurement()
        response = self.client.get('/events', buffered=False)
        first = next(response.response)
        self.assertTrue(first.startswith(b'data: '))
        response.close()


class ConfigFormTest(WebTestBase):
    def submit_current_form(self, **overrides):
        parser = FormParser()
        parser.feed(self.client.get('/control/config.php').data.decode())
        fields = [(k, v) for k, v in parser.fields if k not in overrides]
        fields += list(overrides.items()) + [('save', '')]
        return self.client.post('/control/config.php', data=MultiDict(fields))

    def test_unchanged_form_keeps_config(self):
        for version in ('v3', 'miniV2'):
            self.set_config(Hardware__version=version)
            before = {s: dict(self.config().items(s, raw=True)) for s in self.config().sections()}
            response = self.submit_current_form()
            self.assertEqual(response.status_code, 200)
            after = {s: dict(self.config().items(s, raw=True)) for s in self.config().sections()}
            diff = {(s, k): (before[s].get(k), v) for s in after for k, v in after[s].items()
                    if before.get(s, {}).get(k) != v}
            self.assertEqual(diff, {}, version)

    def test_changes_and_limits(self):
        self.submit_current_form(tch0='Garraum', temp_max0='500', pit_set='120,5', pit_servo_min='100',
                                 pit_controller_type='True', email_password='p%w')
        config = self.config()
        self.assertEqual(config.get('ch_name', 'ch_name0'), 'Garraum')
        self.assertEqual(config.get('temp_max', 'temp_max0'), '200')            # ausserhalb -> 200
        self.assertEqual(config.get('Pitmaster', 'pit_set'), '120.5')
        self.assertEqual(config.get('Pitmaster', 'pit_servo_min'), '500')
        self.assertEqual(config.get('Pitmaster', 'pit_controller_type'), 'PID')
        self.assertEqual(config.get('Email', 'password'), 'p%w')

    def test_restart_flags(self):
        self.set_config(Sound__beeper_enabled='True')
        parser = FormParser()
        parser.feed(self.client.get('/control/config.php').data.decode())
        fields = [(k, v) for k, v in parser.fields if k != 'beeper_enabled'] + [('save', '')]
        self.set_config(locale__locale='en_US')
        response = self.client.post('/control/config.php', data=MultiDict(fields))
        self.assertIn(b'wlt_2_comp.py', response.data)
        self.assertEqual(self.config().get('ToDo', 'restart_thermo'), 'True')

    def test_newline_cannot_break_config(self):
        self.submit_current_form(plotname='a\n[ToDo]\nraspi_reboot = True')
        self.assertEqual(self.config().get('ToDo', 'raspi_reboot'), 'False')

    def test_upload(self):
        self.set_config(locale__locale='en_US')
        with mock.patch('subprocess.run', return_value=mock.Mock(returncode=0)) as run:
            response = self.client.post('/control/config.php', data={
                'upload_file': '', 'configfile': (io.BytesIO(b'[ToDo]\nbackup = False\n'), 'old.conf')},
                content_type='multipart/form-data')
        self.assertIn(b'File has been processed', response.data)
        self.assertEqual(run.call_args[0][0][0], '/usr/local/bin/wlanthermo-updateconfig')

    def test_test_alert_via_core(self):
        self.client.get('/control/config.php?alert-test=true')
        self.comp.request_test_alert.assert_called_once_with()


class ActionsTest(WebTestBase):
    def test_reboot_and_shutdown(self):
        self.client.post('/control/reboot.php', data={'reboot': ''})
        self.assertEqual(self.config().get('ToDo', 'raspi_reboot'), 'True')
        self.assertTrue(os.path.exists(os.path.join(self.www, 'tmp', 'reboot')))
        self.client.post('/control/shutdown.php', data={'shutdown': ''})
        self.assertEqual(self.config().get('ToDo', 'raspi_shutdown'), 'True')
        self.client.post('/control/reboot.php', data={'back': ''})

    def test_new_log(self):
        self.client.post('/control/new_log_file.php', data={'yes': ''})
        self.assertEqual(self.config().get('ToDo', 'create_new_log'), 'True')

    def test_update_steps(self):
        self.client.post('/control/update.php', data={'update_step2': ''})
        self.assertEqual(self.config().get('ToDo', 'start_system_update'), 'True')
        self.assertIn(b'update_step2', self.client.post('/control/update.php', data={'update_step1': ''}).data)

    def test_check_update(self):
        self.client.post('/info.php', data={'check_update': ''})
        self.assertEqual(self.config().get('ToDo', 'check_update'), 'True')

    def test_telegram_token_checked(self):
        with mock.patch('urllib.request.urlopen') as urlopen:
            self.assertEqual(json.loads(self.client.get(
                '/control/telegram.php?telegram_getid=true&telegram_token=x/../../evil').data), [])
            urlopen.assert_not_called()


class ThermologTest(WebTestBase):
    def write_log(self, name):
        with open(os.path.join(self.log_dir, name), 'w') as f:
            f.write('Datum_Uhrzeit,Kanal 0\n')

    def test_list_rename_delete(self):
        self.write_log('20181024_TEMPLOG.csv')
        self.write_log('alt.csv')
        with open(self.current_temp, 'w') as f:
            f.write('x;20181024_TEMPLOG')
        data = self.client.get('/thermolog.php').data.decode()
        self.assertIn('id="alt.csv"', data)
        self.assertIn('class="no_edit" id="20181024_TEMPLOG.csv"', data)
        self.assertEqual(self.client.post('/edit.php', data={'id': 'alt.csv', 'value': 'Grillfest Ü'}).data,
                         'Grillfest Ü'.encode())
        self.assertTrue(os.path.exists(os.path.join(self.log_dir, 'GrillfestUe.csv')))
        self.client.post('/thermolog.php', data={'GrillfestUe': 'True', 'submit': ''})
        self.assertFalse(os.path.exists(os.path.join(self.log_dir, 'GrillfestUe.csv')))

    def test_no_path_traversal(self):
        outside = os.path.join(self.dir, 'secret.csv')
        open(outside, 'w').close()
        self.assertEqual(self.client.post('/edit.php', data={'id': '../secret.csv', 'value': 'x'}).data, b'Fehler...')
        self.client.post('/thermolog.php', data={'../secret': 'True', 'submit': ''})
        self.assertTrue(os.path.exists(outside))

    def test_current_log_cannot_be_renamed(self):
        self.write_log('aktuell.csv')
        with open(self.current_temp, 'w') as f:
            f.write('x;aktuell')
        self.assertEqual(self.client.post('/edit.php', data={'id': 'aktuell.csv', 'value': 'y'}).data, b'Fehler...')


class WifiTest(WebTestBase):
    def test_info(self):
        ifconfig = 'wlan0: flags=4163<UP,BROADCAST,RUNNING> inet 192.168.1.5 netmask 255.255.255.0 ether b8:27:eb:00:00:01'
        with mock.patch('wlanthermo.web.wifi.run', return_value=(0, ifconfig + ' ESSID:"Grill"')):
            data = self.client.get('/control/wifi.php').data.decode()
        self.assertIn('192.168.1.5', data)
        self.assertIn('Interface is up', data)
        self.assertIn('Grill', data)

    def test_save_without_shell(self):
        calls = []

        def run(args, timeout=15):
            calls.append(args)
            if args[0] == 'wpa_passphrase':
                return 0, 'network={\n\tssid="%s"\n\t#psk="%s"\n\tpsk=abc\n}\n' % (args[1], args[2])
            return 0, ''
        with mock.patch('wlanthermo.web.wifi.run', side_effect=run), \
                mock.patch('wlanthermo.web.wifi.WIFIDATA', os.path.join(self.dir, 'wifidata')):
            self.client.post('/control/wifi.php?page=wpa_conf', data={
                'ssid0': "Mein'Netz", 'psk0': "geheim'; rm -rf /", 'ssid1': 'kurz', 'psk1': '123',
                'SaveWPAPSKSettings': 'Save', 'Networks': '2'})
            with open(os.path.join(self.dir, 'wifidata')) as f:
                written = f.read()
        self.assertIn('ssid="Mein\'Netz"', written)
        self.assertNotIn('kurz', written)          # Passwort zu kurz
        self.assertIn(['wpa_passphrase', "Mein'Netz", "geheim'; rm -rf /"], calls)
        self.assertIn(['sudo', '-n', '/bin/cp', os.path.join(self.dir, 'wifidata'),
                       '/etc/wpa_supplicant/wpa_supplicant.conf'], calls)


class StaticTest(WebTestBase):
    def test_serve_static_without_lighttpd(self):
        shutil.copytree(os.path.join(WWW, 'css'), os.path.join(self.www, 'css'))
        shutil.copy(os.path.join(WWW, 'buzzer.mp3'), self.www)
        app = create_app(dict(self.app.config, SERVE_STATIC=True))
        client = app.test_client()
        self.assertEqual(client.get('/css/style.css').status_code, 200)
        self.assertEqual(client.get('/buzzer.mp3').status_code, 200)
        self.assertEqual(client.get('/images/icons16x16/thermo.png').status_code, 200)
        self.assertEqual(client.get('/conf/WLANThermo.conf').status_code, 404)   # nur über lighttpd mit Passwort
        self.assertEqual(client.get('/css/../conf/WLANThermo.conf').status_code, 404)


class HelpersTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(helpers.to_number('120,5'), 120.5)
        self.assertEqual(helpers.to_number('12abc'), 12)
        self.assertEqual(helpers.to_number(''), 0)
        self.assertEqual(helpers.from_float(120.50), '120.5')
        self.assertEqual(helpers.from_float(3.0), '3')

    def test_plot_script(self):
        ini = helpers.read_ini(os.path.join(WWW, 'conf', 'WLANThermo.conf'))
        ini['plotter']['plot_pit'] = 'True'
        ini['ch_name']['ch_name0'] = "O'Brien"
        script = helpers.plot_script(helpers.Settings(ini), '/log/TEMPLOG.csv', '/tmp/out.png')
        self.assertIn('set output "/tmp/out.png"', script)
        self.assertIn("using 1:12 with lines", script)           # Pitmaster-Sollwert hinter 10 Kanälen
        self.assertNotIn("O'Brien", script)


if __name__ == '__main__':
    unittest.main()
