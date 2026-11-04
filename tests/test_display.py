"""Test von wlanthermo.display.device gegen ein simuliertes Nextion-Display (pty).

Start: python3 tests/test_display.py   (benötigt: pip install 'nextion>=2.0,<3')
"""
import os
import pty
import struct
import sys
import threading
import time
import tty

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.display.device import Display, PortBusy, lock_port  # noqa: E402

EOL = b'\xff\xff\xff'


class FakeNextion(threading.Thread):
    def __init__(self, fd):
        super().__init__(daemon=True)
        self.fd = fd
        self.received = []
        self.vars = {'sleep': 0, 'main.n0.val': 42, 'main.t0.txt': 'Hallo Gr\xfc\xdf'}
        self.page = 3
        self.stop = False

    def send(self, data):
        os.write(self.fd, data + EOL)

    def run(self):
        buf = b''
        while not self.stop:
            try:
                buf += os.read(self.fd, 1024)
            except OSError:
                return
            while EOL in buf:
                cmd, _, buf = buf.partition(EOL)
                self.handle(cmd.decode('latin-1'))

    def handle(self, cmd):
        self.received.append(cmd)
        if cmd.startswith('\xffconnect') or cmd == 'connect' or cmd.endswith('connect'):
            self.send(b'comok 1,30601-0,NX3224T028_011R,163,61488,D264B8204F0E1828,16777216')
        elif cmd == 'get sleep':
            self.send(b'\x71' + struct.pack('i', self.vars['sleep']))
        elif cmd.startswith('get '):
            v = self.vars.get(cmd[4:])
            if isinstance(v, int):
                self.send(b'\x71' + struct.pack('i', v))
            elif v is not None:
                self.send(b'\x70' + v.encode('latin-1'))
            else:
                self.send(b'\x1a')
        elif cmd == 'sendme':
            self.send(b'\x66' + bytes([self.page]))
        elif cmd.startswith('bkcmd') or cmd.startswith('DRAKJ'):
            self.send(b'\x01') if cmd.startswith('bkcmd') else None
        elif cmd.startswith('page '):
            self.page = int(cmd[5:]) if cmd[5:].isdigit() else self.page
            self.send(b'\x01')
        elif '=' in cmd:
            k, _, v = cmd.partition('=')
            self.vars[k] = int(v) if not v.startswith('"') else v.strip('"')
            self.send(b'\x01')


def check(name, cond):
    print(('ok   ' if cond else 'FAIL ') + name)
    if not cond:
        check.failed += 1


check.failed = 0


def main():
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    port = os.ttyname(slave)
    fake = FakeNextion(master)
    fake.start()

    d = Display()
    check('start', d.start(port, 9600))
    info = d.device_info
    check('device_info model', info and info['model'] == 'NX3224T028_011R')
    check('device_info flash', info and info['flash_size'] == '16777216')
    check('awake', d.wake_event.is_set() and d.sleeping is False)

    check('send text and number', d.sendvalues({'main.t0.txt': 'Gr\xfcnkern-Rollbraten', 'main.n0.val': 7}))
    check('text arrived latin-1', fake.vars.get('main.t0.txt') == 'Gr\xfcnkern-Rollbraten')
    check('number arrived', fake.vars.get('main.n0.val') == 7)
    check('float compact', d.sendvalues({'main.t1.txt': 22.0}) and fake.vars['main.t1.txt'] == '22')
    check('length limit', d.sendvalues({'main.t2.txt:5': 'abcdefghij'}) and fake.vars['main.t2.txt'] == 'abcde')
    check('rtc int', d.sendvalues({'rtc0': 2026}) and fake.vars['rtc0'] == 2026)
    check('unknown var skipped', d.sendvalues({'main.x0.foo': 1}))

    check('get number', d.getvalue('main.n0.val') == 7)
    check('get text', d.getvalue('main.t0.txt') == 'Gr\xfcnkern-Rollbraten')
    check('get unknown -> None', d.getvalue('main.nope.val') is None)
    check('getvalues', d.getvalues(['main.n0.val', 'main.nope.val']) == {'main.n0.val': 7})

    check('switchpage', d.switchpage(5) and d.page == 5 and fake.page == 5)
    check('sendcmd', d.sendcmd('page 1') and fake.page == 1)

    # Ereignisse
    fake.send(b'\x65\x02\x05\x01')
    fake.send(b'\x40\x03\x07')
    fake.send(b'\x41\x01\x02\x03')
    fake.send(b'\x66\x04')
    events = []
    deadline = time.time() + 3
    while len(events) < 4 and time.time() < deadline:
        try:
            events.append(d.events.get(timeout=0.5))
        except Exception:
            pass
    types = [e['type'] for e in events]
    check('touch event', {'type': 'touch_event', 'data': {'page': 2, 'button': 5, 'event': 'press'}} in events)
    check('read_cmd', {'type': 'read_cmd', 'data': {'area': 3, 'id': 7}} in events)
    check('current_page', {'type': 'current_page', 'data': {'page': 4}} in events)
    check('custom_cmd', {'type': 'custom_cmd', 'data': {'area': 1, 'id': 2, 'action': 3}} in events)

    # Sleep / Wakeup
    fake.send(b'\x86')
    time.sleep(0.5)
    check('sleep clears wake_event', not d.wake_event.is_set() and d.sleeping)
    check('values deferred while sleeping', d.sendvalues({'main.t5.txt': 'spaeter'}) and 'main.t5.txt' not in fake.vars)
    fake.send(b'\x87')
    time.sleep(0.5)
    check('wake sets wake_event', d.wake_event.is_set())
    check('deferred value sent after wake', fake.vars.get('main.t5.txt') == 'spaeter')

    # Portsperre
    try:
        lock_port(port, blocking=False)
        check('port lock', False)
    except PortBusy:
        check('port lock', True)

    d.stop()
    fake.stop = True
    try:
        fd = lock_port(port, blocking=False)
        os.close(fd)
        check('lock released after stop', True)
    except PortBusy:
        check('lock released after stop', False)

    print('FAILED: %d' % check.failed if check.failed else 'ALL OK')
    return 1 if check.failed else 0


if __name__ == '__main__':
    sys.exit(main())
