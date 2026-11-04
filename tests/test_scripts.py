"""Integrationstest von nextion_hwclock.py und nextionupload.py gegen ein Fake-Display.

Braucht root (legt /dev/serial0 als Link auf ein pty an) und die nextion-Bibliothek.
Start: PYTHONPATH=software/usr/lib/python3/dist-packages python3 tests/test_scripts.py
"""
import bz2
import os
import pty
import struct
import subprocess
import sys
import tempfile
import threading
import tty

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SBIN = os.path.join(ROOT, 'software', 'usr', 'sbin')
EOL = b'\xff\xff\xff'


class Fake(threading.Thread):
    def __init__(self, fd):
        super().__init__(daemon=True)
        self.fd = fd
        self.vars = {'sleep': 0, 'rtc0': 2026, 'rtc1': 11, 'rtc2': 4, 'rtc3': 12, 'rtc4': 30, 'rtc5': 15}
        self.upload_left = None
        self.uploaded = b''
        self.chunk = 0

    def send(self, data, eol=True):
        os.write(self.fd, data + (EOL if eol else b''))

    def run(self):
        buf = b''
        while True:
            try:
                buf += os.read(self.fd, 65536)
            except OSError:
                return
            if self.upload_left is not None:
                # Je 4096-Byte-Block (bzw. Rest) ein ACK, wie das echte Display
                while buf and self.upload_left:
                    want = min(4096, self.upload_left) - self.chunk
                    part, buf = buf[:want], buf[want:]
                    self.uploaded += part
                    self.chunk += len(part)
                    self.upload_left -= len(part)
                    if self.chunk == min(4096, self.upload_left + self.chunk):
                        self.chunk = 0
                        self.send(b'\x05', eol=False)
                if not self.upload_left:
                    self.upload_left = None
                continue
            while EOL in buf and self.upload_left is None:
                cmd, _, buf = buf.partition(EOL)
                self.handle(cmd.decode('latin-1').lstrip('\xff'))

    def handle(self, cmd):
        if cmd == 'connect':
            self.send(b'comok 1,30601-0,NX3224T028_011R,163,61488,D264B8204F0E1828,16777216')
        elif cmd.startswith('bkcmd'):
            self.send(b'\x01')
        elif cmd == 'get sleep':
            self.send(b'\x71' + struct.pack('i', 0))
        elif cmd.startswith('get '):
            self.send(b'\x71' + struct.pack('i', self.vars.get(cmd[4:], 0)))
        elif cmd.startswith('whmi-wri'):
            self.upload_left = int(cmd.split()[1].split(',')[0])
            # Das Display bestätigt erst nach dem Baudratenwechsel der Bibliothek
            threading.Timer(0.5, self.send, (b'\x05', False)).start()
        elif '=' in cmd:
            k, _, v = cmd.partition('=')
            self.vars[k] = int(v) if not v.startswith('"') else v
            self.send(b'\x01')


failed = 0


def check(name, cond):
    global failed
    print(('ok   ' if cond else 'FAIL ') + name)
    failed += not cond


def main():
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    if os.path.lexists('/dev/serial0'):
        os.unlink('/dev/serial0')
    os.symlink(os.ttyname(slave), '/dev/serial0')
    fake = Fake(master)
    fake.start()
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'software', 'usr', 'lib', 'python3', 'dist-packages'))
    try:
        # hwclock: Systemzeit -> Display-RTC (timedatectl liefert hier meist kein NTP -> nur Lesepfad prüfen)
        r = subprocess.run([sys.executable, os.path.join(SBIN, 'nextion_hwclock.py'), 'start'],
                           env=env, capture_output=True, text=True, timeout=120)
        print(r.stdout, r.stderr)
        check('hwclock exit 0', r.returncode == 0)
        check('hwclock read the RTC or set it', 'Getting time from NEXTION RTC' in r.stdout or 'Setting NEXTION RTC' in r.stdout)
        check('hwclock pid file removed', not os.path.exists('/var/run/nextion_hwclock.pid'))

        # Upload mit .bz2
        tmp = tempfile.mkdtemp() + '/'
        payload = os.urandom(3000)  # ein Block; mehrere Blöcke scheitern im pty (Teilschreibvorgang), nicht geprüft
        with bz2.open(tmp + 'NX3224T028_foo.tft.bz2', 'wb') as f:
            f.write(payload)
        r = subprocess.run([sys.executable, os.path.join(SBIN, 'nextionupload.py'), tmp, 'foo'],
                           env=env, capture_output=True, text=True, timeout=120)
        print(r.stdout, r.stderr)
        check('upload exit 0', r.returncode == 0)
        check('upload payload identical', fake.uploaded == payload)

        # Datei fehlt -> Fehlercode
        r = subprocess.run([sys.executable, os.path.join(SBIN, 'nextionupload.py'), tmp, 'nope'],
                           env=env, capture_output=True, text=True, timeout=120)
        check('missing file -> exit != 0', r.returncode != 0 and 'not found' in (r.stdout + r.stderr))
    finally:
        os.unlink('/dev/serial0')
    print('FAILED: %d' % failed if failed else 'ALL OK')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
