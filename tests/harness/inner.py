"""Runs wlanthermo.comp.main() against fake hardware inside a mount namespace.

argv: SRC OUT SCENARIO CONF_DIR
/var is a private tmp dir (bind mount by run.sh), so all hardcoded paths are safe.
"""
import json
import os
import random
import shutil
import struct
import sys
import types

SRC, OUT, SCENARIO, CONF_DIR = sys.argv[1:5]
sys.path.insert(0, SRC)
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- fake clock
import time
clock = [1700000000.0]
real_strftime = time.strftime
time.time = lambda: clock[0]
def _sleep(s):
    clock[0] += s
time.sleep = _sleep
time.strftime = lambda fmt, t=None: real_strftime(fmt, time.gmtime(clock[0]) if t is None else t)

def record(name, obj):
    with open(os.path.join(OUT, name), 'a') as f:
        f.write(json.dumps(obj, sort_keys=True, ensure_ascii=False) + '\n')

# ---------------------------------------------------------------- scenarios
BASE = {
    'Hardware': {'version': 'v3', 'max31855': 'False'},
    'Messen': {'iterations': '10', 'delay': '3.0'},
    'Sound': {'beeper_enabled': 'True', 'beeper_on_start': 'False'},
    'Logging': {'write_new_log_on_restart': 'False', 'separator': ','},
    'daemon_logging': {'level_compy': 'DEBUG'},
    'ToDo': {'pit_on': 'True', 'pit2_on': 'True', 'maverick_enabled': 'True'},
    'Alert': {'alarm_interval': '20', 'status_interval': '60',
              'status_template': 'Kanal {kanal} ({name}) hat {temperatur}{temp_unit}{lf}',
              'message_template': '{hostname}: {alarme}{statusse} Pit {pit_new}/{pit_set} Pit2 {pit2_new}/{pit2_set}'},
    'Email': {'email_alert': 'True', 'auth': 'True', 'starttls': 'True', 'server': 'smtp.example.org',
              'username': 'u', 'password': 'p', 'email_from': 'a@example.org', 'email_to': 'b@example.org',
              'email_subject': 'WLANThermo'},
    'Telegram': {'telegram_alert': 'True', 'telegram_chat_id': '42', 'telegram_token': 'TOKEN'},
    'Push': {'push_on': 'True', 'push_url': 'http://push.example.org/?t={messagetext}', 'push_body': ''},
    'locale': {'temp_unit': 'celsius'},
    'temp_min': {'temp_min%d' % k: '10' for k in range(12)},
    'temp_max': {'temp_max%d' % k: '60' for k in range(12)},
}
SCENARIOS = {
    'a': {'conf': {}, 'cycles': 40,
          'changes': {14: {'temp_max': {'temp_max0': '80', 'temp_max3': 'kaputt'},
                           'Push': {'push_body': 'text={messagetext}'},
                           'Sensoren': {'ch2': '10'},
                           'Alert': {'status_interval': '0'}}}},
    'b': {'conf': {'Hardware': {'version': 'miniV2', 'max31855': 'True'},
                   'locale': {'temp_unit': 'fahrenheit'},
                   'Logging': {'write_new_log_on_restart': 'True'},
                   'Sound': {'beeper_on_start': 'True'},
                   'ToDo': {'maverick_enabled': 'False', 'pit2_on': 'False'},
                   'Email': {'email_alert': 'False', 'auth': 'False'},
                   'temp_max': {'temp_max%d' % k: '140' for k in range(12)},
                   'temp_min': {'temp_min%d' % k: '50' for k in range(12)}},
          'cycles': 30,
          'changes': {10: {'Telegram': {'telegram_alert': 'False'}, 'Sound': {'beeper_enabled': 'False'}}}},
}
scenario = SCENARIOS[SCENARIO]

import configparser
def write_config(*overlays):
    config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
    config.read(os.path.join(CONF_DIR, 'WLANThermo.conf'), encoding='utf-8')
    for overlay in (BASE, scenario['conf']) + overlays:
        for section, values in overlay.items():
            for key, value in values.items():
                config.set(section, key, value)
    config.set('daemon_logging', 'log_file', '/var/log/WLANThermo.log')
    with open('/var/www/conf/WLANThermo.conf', 'w', encoding='utf-8') as f:
        config.write(f)
    os.utime('/var/www/conf/WLANThermo.conf', (clock[0], clock[0]))

os.makedirs('/var/www/conf'); os.makedirs('/var/www/tmp/display'); os.makedirs('/var/run'); os.makedirs('/var/log')
shutil.copy(os.path.join(CONF_DIR, 'sensor.conf'), '/var/www/conf/sensor.conf')
applied = []
write_config()

# ---------------------------------------------------------------- fake hardware
rnd = random.Random(1234)
cycle = [0]
# Grundwerte je Kanal, wandern über die Zyklen durch den ganzen Bereich (auch < 15 und > 4080)
BASES = [rnd.randint(0, 4095) for _ in range(8)]

pigpio = types.ModuleType('pigpio')
class _error(Exception):
    def __init__(self, value): self.value = value
    def __str__(self): return repr(self.value)
pigpio.error = _error
pigpio.PI_GPIO_IN_USE = -50
pigpio.error_text = lambda n: {-50: 'GPIO already in use'}.get(n, 'error %d' % n)
pigpio.OUTPUT = 1
class _pi:
    connected = True
    def bb_spi_open(self, cs, *a):
        if cs == 8:   # schon offen von einem vorherigen Lauf
            raise _error('GPIO already in use')
        return 0
    def bb_spi_close(self, cs): record('gpio.jsonl', ['close', cs])
    def set_mode(self, *a): record('gpio.jsonl', ['mode'] + list(a))
    def write(self, pin, value): record('gpio.jsonl', ['write', pin, value, clock[0]])
    def stop(self): record('gpio.jsonl', ['stop'])
    def bb_spi_xfer(self, cs, data):
        if cs == 25:
            ch = (struct.unpack('>H', data[:2])[0] >> 6) - 0x18
            value = (BASES[ch] + cycle[0] * 397 * (ch + 1)) % 4096
            value = max(0, min(4095, value + rnd.randint(-3, 3)))
            if rnd.random() < 0.02:
                value = rnd.choice([0, 4095])
            return 3, b'\x00' + struct.pack('>H', value)
        # MAX31855: 14 Bit Temperatur * 4, Bit 15 (hier Bit 0 der Bytes) = Fehler
        if rnd.random() < 0.1:
            return 2, b'\x00\x01'
        t = rnd.uniform(-20, 300)
        return 2, struct.pack('>h', int(t * 4) << 2)
pigpio.pi = _pi
sys.modules['pigpio'] = pigpio

psutil = types.ModuleType('psutil')
def cpu_percent(interval=1, percpu=True):
    # Beginn eines Messzyklus
    clock[0] += interval
    if os.path.exists('/var/www/tmp/display/current.temp'):
        with open('/var/www/tmp/display/current.temp', encoding='utf-8') as f:
            record('current.jsonl', [cycle[0], f.read()])
    cycle[0] += 1
    c = cycle[0]
    if c > scenario['cycles']:
        raise KeyboardInterrupt()
    if c in scenario['changes']:
        applied.append(scenario['changes'][c])
        write_config(*applied)
    if c % 9 == 4:
        open('/var/www/alert.test', 'w').close()
    if c % 11 == 7:
        open('/var/www/alert.ack', 'w').close()
    with open('/var/www/tmp/maverick.json', 'w') as f:
        json.dump({'time': clock[0] - (40 if c % 7 == 0 else 0),
                   'temperature_1': '' if c % 5 == 0 else round(rnd.uniform(0, 120), 1),
                   'temperature_2': round(rnd.uniform(0, 120), 1)}, f)
    for n, name in enumerate(('pit.temp', 'pit2.temp')):
        with open('/var/www/tmp/display/' + name, 'w') as f:
            f.write('' if c % 6 == n else '12:00:00;%d;x;%d%%' % (100 + c, 30 + n + c))
    return [12.5]
psutil.cpu_percent = cpu_percent
psutil.virtual_memory = lambda: types.SimpleNamespace(free=512 * 2 ** 20)
sys.modules['psutil'] = psutil

import platform
platform.node = lambda: 'grill'

import smtplib
class _SMTP:
    def __init__(self, host, port, timeout=None): self.log = {'host': host, 'port': port}
    def starttls(self): self.log['tls'] = True
    def login(self, u, p): self.log['login'] = [u, p]
    def sendmail(self, sender, to, msg):
        import email
        m = email.message_from_string(msg)
        self.log.update(sender=sender, to=to, subject=m['Subject'],
                        body=m.get_payload(decode=True).decode('utf-8'))
    def quit(self): record('sent.jsonl', ['email', self.log])
smtplib.SMTP = _SMTP

import urllib.request
class _Response:
    def __init__(self, url): self.url = url
    def getcode(self): return 200
    def geturl(self): return self.url
    def read(self, n=-1): return b'ok'
def urlopen(url, data=None, timeout=None):
    record('sent.jsonl', ['http', url, data.decode('utf-8') if data else None])
    return _Response(url)
urllib.request.urlopen = urlopen

# ---------------------------------------------------------------- run
try:
    from wlanthermo.comp import service as comp   # ab der Aufteilung in Unterpakete
except ImportError:
    from wlanthermo import comp
try:
    comp.main()
finally:
    for name in sorted(os.listdir('/var/log/WLAN_Thermo')):
        path = os.path.join('/var/log/WLAN_Thermo', name)
        if os.path.islink(path):
            record('logs.jsonl', [name, '->', os.readlink(path)])
        else:
            with open(path, encoding='utf-8') as f:
                record('logs.jsonl', [name, f.read()])
    record('end.jsonl', ['pidfile exists', os.path.exists('/var/run/wlt_2_comp.pid'), 'cycles', cycle[0]])
