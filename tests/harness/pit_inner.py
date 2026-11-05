"""Runs the pitmaster main() against fake pigpio inside a mount namespace.

argv: SRC OUT SCENARIO CONF_DIR
"""
import json
import os
import sys
import threading
import types

SRC, OUT, SCENARIO, CONF_DIR = sys.argv[1:5]
sys.path.insert(0, SRC)
os.makedirs(OUT, exist_ok=True)

import time
clock = [1700000000.0]
real_strftime = time.strftime
time.time = lambda: clock[0]
main_thread = threading.main_thread()
thread_ctx = threading.local()

class _ThreadCycleDone(Exception):
    pass

def _sleep(s):
    if threading.current_thread() is main_thread and not getattr(thread_ctx, 'fake', False):
        record('gpio.jsonl', ['sleep', round(s, 6)])
        clock[0] += s
        if s > 0 and len(open(os.path.join(OUT, 'gpio.jsonl')).readlines()) > 20000:
            raise KeyboardInterrupt('harness limit')
        return
    # io_pwm thread: one switching cycle per pitmaster cycle
    thread_ctx.slept += s
    record('gpio.jsonl', ['thread-sleep', round(s, 6)])
    if thread_ctx.slept >= 2 - 1e-9:
        raise _ThreadCycleDone()
time.sleep = _sleep
time.strftime = lambda fmt, t=None: real_strftime(fmt, time.gmtime(clock[0]) if t is None else t)

def record(name, obj):
    with open(os.path.join(OUT, name), 'a') as f:
        f.write(json.dumps(obj, sort_keys=True, ensure_ascii=False) + '\n')

# ---------------------------------------------------------------- fake threading for io_pwm
fake_threads = []
class FakeThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target, self.args, self.kwargs = target, args, kwargs or {}
        self.daemon = daemon
        self.started = False
    def start(self):
        record('gpio.jsonl', ['thread-start'])
        self.started = True
        fake_threads.append(self)
    def join(self, timeout=None):
        record('gpio.jsonl', ['thread-join'])
        if self in fake_threads:
            fake_threads.remove(self)
            run_thread_cycle(self)   # sieht das End-Event und beendet sich
    def is_alive(self):
        return self in fake_threads

def run_thread_cycle(t):
    thread_ctx.fake = True
    thread_ctx.slept = 0
    try:
        t.target(*t.args, **t.kwargs)
        if t in fake_threads:
            fake_threads.remove(t)
    except _ThreadCycleDone:
        pass
    finally:
        thread_ctx.fake = False
_real_thread = threading.Thread
threading.Thread = FakeThread

# ---------------------------------------------------------------- fake pigpio
pigpio = types.ModuleType('pigpio')
pigpio.OUTPUT = 1
pigpio.INPUT = 0
pigpio.pulse = lambda on, off, delay: ('pulse', on, off, delay)
class _error(Exception):
    pass
pigpio.error = _error
class _pi:
    connected = True
    wave_id = 0
    def __getattr__(self, name):
        def call(*args):
            tag = 'thread' if getattr(thread_ctx, 'fake', False) else 'pi'
            record('gpio.jsonl', [tag, name] + [list(a) if isinstance(a, list) else a for a in args])
            if name == 'wave_create':
                _pi.wave_id += 1
                return _pi.wave_id
            return 0
        return call
pigpio.pi = _pi
sys.modules['pigpio'] = pigpio

# ---------------------------------------------------------------- scenarios
def ramp(start, step, drops=()):
    def temp(c):
        t = start + step * c
        for at, by in drops:
            if c >= at:
                t -= by
        return round(t, 2)
    return temp

SCENARIOS = {
    'fan_curve': dict(version='v3', instance=0, temp=ramp(60, 4), cycles=20,
                      pit=dict(pit_type='fan', pit_controller_type='False')),
    'fan_pwm_pid': dict(version='v3', instance=0, temp=ramp(40, 5, [(18, 30)]), cycles=30,
                        pit=dict(pit_type='fan_pwm', pit_controller_type='PID', pit_ratelimit_rise='20',
                                 pit_ratelimit_fall='30', pit_startup_min='40', pit_startup_time='0.5')),
    'servo_lid': dict(version='v3', instance=0, temp=ramp(100, 1, [(12, 15), (20, -15)]), cycles=30,
                      pit=dict(pit_type='servo', pit_controller_type='PID', pit_servo_inverted='True',
                               pit_open_lid_detection='True', pit_open_lid_pause='30', pit_servo_deadband='3')),
    'io_inverted': dict(version='v3', instance=0, temp=ramp(95, 1.5), cycles=20,
                        pit=dict(pit_type='io', pit_controller_type='False', pit_inverted='True')),
    'io_pwm_pid': dict(version='v3', instance=0, temp=ramp(80, 2), cycles=20,
                       pit=dict(pit_type='io_pwm', pit_controller_type='PID', pit_pwm_min='10')),
    'damper_mini': dict(version='miniV2', instance=0, temp=ramp(70, 3), cycles=24,
                        pit=dict(pit_type='damper', pit_controller_type='PID', pit_damper_offset='10',
                                 pit_damper_pitch='1.5', pit_inverted='True')),
    'pit2_changes': dict(version='miniV2', instance=1, temp=ramp(50, 6), cycles=30,
                         pit=dict(pit_type='fan_pwm', pit_controller_type='PID', pit_man='35'),
                         changes={6: dict(pit_man='0'), 12: dict(pit_type='servo', pit_kp='5'),
                                  18: dict(pit_type='fan', pit_controller_type='False')}),
    'bad_values': dict(version='v3', instance=0, temp=lambda c: [100, 'er', 'xx', 105, 'no', 'ab107.5', 108][c % 7],
                       cycles=21, pit=dict(pit_type='fan', pit_controller_type='PID')),
    'damper_v3': dict(version='v3', instance=0, temp=ramp(90, 2), cycles=8,
                      pit=dict(pit_type='damper', pit_controller_type='PID')),
    'curve_to_pid': dict(version='v3', instance=0, temp=ramp(70, 3), cycles=14,
                         pit=dict(pit_type='fan', pit_controller_type='False'),
                         changes={6: dict(pit_controller_type='PID')}),
    'sigterm': dict(version='miniV2', instance=1, temp=ramp(60, 4), cycles=99, sigterm=8,
                    pit=dict(pit_type='fan', pit_controller_type='False')),
    'unknown_instance': dict(version='v3', instance=1, temp=ramp(90, 2), cycles=5, pit=dict(pit_type='fan')),
}
scenario = SCENARIOS[SCENARIO]
instance = scenario['instance']
section = 'Pitmaster' + (str(instance + 1) if instance else '')
on_key = 'pit' + (str(instance + 1) if instance else '') + '_on'
channel_count = 12 if scenario['version'] == 'miniV2' else 10

import configparser
def write_config(pit, on=True):
    config = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';',))
    config.read(os.path.join(CONF_DIR, 'WLANThermo.conf'), encoding='utf-8')
    config.set('Hardware', 'version', scenario['version'])
    config.set('daemon_logging', 'log_file', '/var/log/WLANThermo.log')
    config.set('daemon_logging', 'level_pit', 'DEBUG')
    config.set('ToDo', on_key, 'True' if on else 'False')
    for key, value in pit.items():
        config.set(section, key, value)
    with open('/var/www/conf/WLANThermo.conf', 'w', encoding='utf-8') as f:
        config.write(f)
    os.utime('/var/www/conf/WLANThermo.conf', (clock[0], clock[0]))

def write_current(c):
    t = scenario['temp'](c)
    temps = ['%.2f' % (20 + k) for k in range(channel_count)]
    status = ['ok'] * channel_count
    if t in ('er', 'no'):
        temps[0], status[0] = '', t
    else:
        temps[0] = t if isinstance(t, str) else '%.2f' % t
    with open('/var/www/tmp/display/current.temp', 'w') as f:
        f.write(';'.join(['01.01.24 12:00:00'] + temps + status + ['V', 'log']))

os.makedirs('/var/www/conf'); os.makedirs('/var/www/tmp/display'); os.makedirs('/var/run'); os.makedirs('/var/log')
pit_values = dict(scenario['pit'])
write_config(pit_values)
cycle = [0]
write_current(0)

pit_file = '/var/www/tmp/display/pit' + (str(instance + 1) if instance else '') + '.temp'
_real_rename = os.rename
def rename(src, dst):
    _real_rename(src, dst)
    if dst != pit_file:
        return
    with open(dst, encoding='utf-8') as f:
        record('pit.jsonl', [cycle[0], f.read()])
    for t in list(fake_threads):
        run_thread_cycle(t)
    cycle[0] += 1
    c = cycle[0]
    if c in scenario.get('changes', {}):
        pit_values.update(scenario['changes'][c])
        write_config(pit_values)
    if c == scenario['cycles']:
        write_config(pit_values, on=False)
    if c == scenario.get('sigterm'):
        # wie systemctl stop; ohne Handler beendet der Kernel den Prozess sofort
        record('end.jsonl', {'sigterm at cycle': c})
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
    write_current(c)
os.rename = rename

# ---------------------------------------------------------------- run
sys.argv = ['pitmaster', str(instance)]
try:
    from wlanthermo.pitmaster import service as pitmaster
except ImportError:
    from wlanthermo import pitmaster
try:
    pitmaster.main()
    result = 'returned'
except SystemExit as e:
    result = 'exit %s' % e.code
except BaseException as e:
    result = '%s: %s' % (type(e).__name__, e)
record('end.jsonl', {'result': result, 'cycles': cycle[0],
                     'pit file exists': os.path.exists(pit_file),
                     'pidfile exists': os.path.exists('/var/run/wlt_2_pitmaster_%d.pid' % instance)})
