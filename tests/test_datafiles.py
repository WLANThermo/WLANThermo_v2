"""Tests für wlanthermo.datafiles (in einem temporären Verzeichnis).

Start: python3 -m unittest tests/test_datafiles.py
"""
import builtins
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.alarm import ChannelStatus  # noqa: E402
from wlanthermo.datafiles import (CurrentTempFile, PitmasterReader, PitValues,  # noqa: E402
                                  TemperatureLog, read_maverick)

HEADER = ['Pit', 'Pit soll', 'Pit2', 'Pit2 soll']


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        # sonst von gettext.install() in main() gesetzt
        builtins._ = lambda text: text

    def tearDown(self):
        shutil.rmtree(self.dir)
        del builtins._

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding='utf-8') as f:
            return f.read()

    def write(self, name, text):
        with open(self.path(name), 'w', encoding='utf-8') as f:
            f.write(text)


class CurrentTempFileTest(TempDirTest):
    def test_creates_directory_and_writes_line(self):
        f = CurrentTempFile(self.path('display', 'current.temp'))
        f.write('24.10.18 18:30:12', ['63.40', ''], [ChannelStatus.HI, ChannelStatus.ERROR], 'V2.8', '20181024_TEMPLOG')
        self.assertEqual(self.read('display', 'current.temp'),
                         '24.10.18 18:30:12;63.40;;hi;er;V2.8;20181024_TEMPLOG')
        self.assertFalse(os.path.exists(self.path('display', 'current.temp_tmp')))

    def test_write_error_is_logged(self):
        f = CurrentTempFile(self.path('current.temp'))
        os.chmod(self.dir, 0o500)
        try:
            with self.assertLogs('WLANthermo.datafiles', 'ERROR'):
                f.write('t', [], [], 'V', 'log')
        finally:
            os.chmod(self.dir, 0o700)


class TemperatureLogTest(TempDirTest):
    def log(self):
        return TemperatureLog([True, False, True], ',', HEADER, directory=self.path('log'))

    def test_new_file_with_header_and_link(self):
        log = self.log()
        with mock.patch('time.strftime', return_value='20181024_183012'):
            log.open(new_file=True)
        self.assertEqual(log.path, self.path('log', '20181024_183012_TEMPLOG.csv'))
        self.assertEqual(os.readlink(log.link), log.path)
        self.assertEqual(log.name, '20181024_183012_TEMPLOG')
        self.assertEqual(self.read('log', '20181024_183012_TEMPLOG.csv'),
                         'Date_Time,Kanal 0,Kanal 2,Pit,Pit soll,Pit2,Pit2 soll\n')

    def test_line_contains_logged_channels_and_pits(self):
        line = self.log().line('t', [20.5, 30, None], [PitValues('55', '110'), None])
        self.assertEqual(line, 't,20.5,,55,110,,')

    def test_append_to_existing_file(self):
        log = self.log()
        log.open(new_file=True)
        first = log.path
        log.append('a')
        again = self.log()
        again.open(new_file=False)
        self.assertEqual(again.path, again.link)
        self.assertEqual(again.name, os.path.splitext(os.path.basename(first))[0])
        again.append('b')
        self.assertTrue(self.read('log', os.path.basename(first)).endswith('a\nb\n'))

    def test_broken_link_creates_new_file(self):
        os.makedirs(self.path('log'))
        os.symlink(self.path('log', 'gone.csv'), self.path('log', 'TEMPLOG.csv'))
        log = self.log()
        log.open(new_file=False)
        self.assertNotEqual(log.path, log.link)
        self.assertTrue(os.path.exists(log.link))

    def test_name_without_link(self):
        log = self.log()
        log.open(new_file=True)
        os.remove(log.link)
        self.assertEqual(log.name, os.path.splitext(os.path.basename(log.path))[0])


class PitmasterReaderTest(TempDirTest):
    def test_values(self):
        self.write('pit.temp', '12:00:00;110;98.5;55%;Regelung aktiv')
        self.assertEqual(PitmasterReader(self.path('pit.temp')).read(), PitValues(new='55', set='110'))

    def test_missing_or_incomplete(self):
        self.assertIsNone(PitmasterReader(self.path('missing')).read())
        self.write('pit.temp', '12:00:00;110')
        self.assertIsNone(PitmasterReader(self.path('pit.temp')).read())


class MaverickTest(TempDirTest):
    def test_current_values(self):
        self.write('maverick.json', json.dumps({'time': time.time(), 'temperature_1': 80}))
        self.assertEqual(read_maverick(self.path('maverick.json'))['temperature_1'], 80)

    def test_old_values_are_ignored(self):
        self.write('maverick.json', json.dumps({'time': time.time() - 31}))
        self.assertIsNone(read_maverick(self.path('maverick.json')))

    def test_invalid_or_missing(self):
        self.write('maverick.json', '{')
        with self.assertLogs('WLANthermo.datafiles', 'ERROR'):
            self.assertIsNone(read_maverick(self.path('maverick.json')))
        self.assertIsNone(read_maverick(self.path('missing.json')))


if __name__ == '__main__':
    unittest.main()
