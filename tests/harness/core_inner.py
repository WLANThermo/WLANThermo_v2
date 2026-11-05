"""End-to-end test of wlanthermo-core with fake pigpio, real threads and real time (inside a mount namespace)."""
import configparser
import os
import shutil
import struct
import sys
import threading
import time
import types

SRC, CONF_DIR = sys.argv[1:3]
sys.path.insert(0, SRC)

calls = []
calls_lock = threading.Lock()
adc_hang = threading.Event()
adc_released = threading.Event()
adc_released.set()

pigpio = types.ModuleType('pigpio')
class _error(Exception):
    def __init__(self, value): self.value = value
pigpio.error = _error
pigpio.PI_GPIO_IN_USE = -50
pigpio.error_text = lambda n: 'GPIO already in use'
pigpio.OUTPUT, pigpio.INPUT, pigpio.EITHER_EDGE = 1, 0, 2
pigpio.pulse = lambda on, off, delay: (on, off, delay)
class _pi:
    connected = True
    def bb_spi_xfer(self, cs, data):
        if adc_hang.is_set():
            adc_released.clear()
            adc_released.wait(30)
        if cs == 25:
            ch = (struct.unpack('>H', data[:2])[0] >> 6) - 0x18
            # Kanal 0: Fühler 1 (Fantast, Messwiderstand 47) bei etwa 100 °C
            return 3, b'\x00' + struct.pack('>H', 4095 - 3700 if ch == 0 else 0)
        return 2, b'\x00\x01'
    def __getattr__(self, name):
        def call(*args):
            with calls_lock:
                calls.append((threading.current_thread().name, name) + args)
            return 0
        return call
pigpio.pi = _pi
sys.modules['pigpio'] = pigpio
psutil = types.ModuleType('psutil')
psutil.cpu_percent = lambda interval=1, percpu=True: (time.sleep(0.05), [1.0])[1]
psutil.virtual_memory = lambda: types.SimpleNamespace(free=0)
sys.modules['psutil'] = psutil

for d in ('/var/www/conf', '/var/www/tmp/display', '/var/run', '/var/log'):
    os.makedirs(d)
shutil.copy(os.path.join(CONF_DIR, 'sensor.conf'), '/var/www/conf/sensor.conf')

def write_config(changes=None):
    config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
    config.read(os.path.join(CONF_DIR, 'WLANThermo.conf'), encoding='utf-8')
    values = {('Messen', 'delay'): '0.5', ('Messen', 'iterations'): '3', ('ToDo', 'pit_on'): 'True',
              ('Pitmaster', 'pit_pause'): '0.5', ('Pitmaster', 'pit_type'): 'fan', ('Pitmaster', 'pit_set'): '250',
              ('Pitmaster', 'pit_controller_type'): 'PID', ('Hardware', 'version'): 'v3',
              ('daemon_logging', 'log_file'): '/var/log/WLANThermo.log', ('daemon_logging', 'level_compy'): 'DEBUG',
              ('daemon_logging', 'level_pit'): 'DEBUG', ('Sound', 'beeper_enabled'): 'False',
              ('Email', 'email_alert'): 'False', ('Telegram', 'telegram_alert'): 'False', ('Push', 'push_on'): 'False'}
    values.update(changes or {})
    for (section, key), value in values.items():
        config.set(section, key, value)
    with open('/var/www/conf/WLANThermo.conf', 'w') as f:
        config.write(f)
    stamp = time.time() + write_config.count
    write_config.count += 1
    os.utime('/var/www/conf/WLANThermo.conf', (stamp, stamp))
write_config.count = 0
write_config()

from wlanthermo.comp import service as comp_service
from wlanthermo.core import service
from wlanthermo.core.hub import MEASUREMENT, pit_topic
service.max_measurement_age = lambda delay: 2

def pit_file():
    try:
        with open('/var/www/tmp/display/pit.temp') as f:
            return f.read()
    except FileNotFoundError:
        return None

def fan_values(since=0):
    with calls_lock:
        return [c[3] for c in calls[since:] if c[1] == 'set_PWM_dutycycle']

def check(name, cond, detail=''):
    print('ok  ' if cond else 'FAIL', name, '' if cond else detail)
    if not cond:
        check.failed = True
check.failed = False

startup, sensor_types = comp_service.prepare()
core = service.Core(startup, sensor_types, api_path='/var/run/wlanthermo/core.sock')
result = {}
runner = threading.Thread(target=lambda: result.setdefault('failed', core.run()))
runner.start()

import atexit
atexit.register(lambda: (adc_released.set(), core.stop()))

# 1. Regelung mit Werten aus dem DataHub
time.sleep(3)
m = core.hub.latest(MEASUREMENT)
state = core.hub.latest(pit_topic(0))
check('measurement in hub', m is not None and m.age() < 1.5, m)
check('pitmaster gets channel 0 from hub', state is not None and state.current == float('%.2f' % m.temperatures[0]),
      (state, m and m.temperatures[0]))
check('pitmaster output > 0 below setpoint', state is not None and state.output > 0, state)
check('no pit file in core mode', pit_file() is None, pit_file())
check('no current.temp in core mode', not os.path.exists('/var/www/tmp/display/current.temp'))
check('log name in measurement', m.log_name.endswith('_TEMPLOG'), m.log_name)

# 2. comp hängt -> Pitmaster schaltet ab
mark = len(calls)
adc_hang.set()
time.sleep(3.5)
state = core.hub.latest(pit_topic(0))
check('stale measurement switches output off', state is not None and state.output == 0 and state.current is None, state)
check('reason in pit state', 'no current measurement' in state.message, state.message)
check('fan set to 0', 0 in fan_values(mark), fan_values(mark))

# 3. comp läuft wieder -> Regelung wieder an
adc_hang.clear()
adc_released.set()
time.sleep(3)
state = core.hub.latest(pit_topic(0))
check('regulates again after recovery', state is not None and state.output > 0 and state.current is not None, state)

# 3b. Schnittstelle: Live-Werte und Sollwert ändern
from wlanthermo.core.client import CoreClient
client = CoreClient('/var/run/wlanthermo/core.sock')
check('api state', 'measurement' in client.state() and 'pit/0' in client.state())
events = client.subscribe(topics=['measurement'], timeout=5)
first = next(events)
second = next(events)
check('api live measurements', first['measurement']['time'] < second['measurement']['time'], (first, second))
events.close()
client.config_set({'Pitmaster': {'pit_set': '260'}})
time.sleep(1.5)
state = core.hub.latest(pit_topic(0))
check('setpoint change via api reaches pitmaster', state is not None and state.setpoint == 260.0, state)
client.acknowledge()
client.test_alert()
time.sleep(1.5)
check('api requests consumed by comp', not core.comp.acknowledge_requested.is_set()
      and not core.comp.test_alert_requested.is_set())

# 4. Pitmaster in der Konfiguration aus -> Manager stoppt ihn, Ausgang aus
mark = len(calls)
write_config({('ToDo', 'pit_on'): 'False'})
time.sleep(2.5)
check('pitmaster stopped by manager', 0 not in core.manager.pitmasters, list(core.manager.pitmasters))
check('fan off after stop', fan_values(mark)[-1:] == [0], fan_values(mark))

check('hub pit state cleared', core.hub.latest(pit_topic(0)) is None)

# 5. Beenden
start = time.monotonic()
core.stop()
runner.join(30)
check('core stops', not runner.is_alive() and result.get('failed') is False, result)
check('stops quickly', time.monotonic() - start < 5, time.monotonic() - start)
alive = [t.name for t in threading.enumerate() if t.name.startswith(('comp', 'manager', 'pitmaster'))]
check('no service threads left', not alive, alive)
spi_closed = [c[2] for c in calls if c[1] == 'bb_spi_close']
check('SPI closed', spi_closed == [25, 8, 7], spi_closed)
check('api socket removed', not os.path.exists('/var/run/wlanthermo/core.sock'))
sys.exit(1 if check.failed else 0)
