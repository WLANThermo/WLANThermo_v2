"""Tests für wlanthermo.config: Sperre und Ändern der Konfiguration.

Start: python3 -m unittest tests/test_config.py
"""
import multiprocessing
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.config import config_lock, make_parser, read_config_file, update_config, write_config_file  # noqa: E402


def increment(path, count):
    for _ in range(count):
        with config_lock(path):
            config = make_parser()
            read_config_file(config, path)
            config.set('a', 'n', str(config.getint('a', 'n') + 1))
            write_config_file(config, path)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'test.conf')
        with open(self.path, 'w') as f:
            f.write('[a]\nn = 0\nurl = http://x/?a=%20{text}\n\n[ToDo]\nbackup = True\n')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def read(self):
        config = make_parser()
        read_config_file(config, self.path)
        return config

    def test_update_keeps_other_values(self):
        update_config({'ToDo': {'backup': 'False'}, 'neu': {'x': 1}}, self.path)
        config = self.read()
        self.assertEqual(config.get('ToDo', 'backup'), 'False')
        self.assertEqual(config.get('neu', 'x'), '1')
        self.assertEqual(config.get('a', 'url'), 'http://x/?a=%20{text}')   # ohne Interpolation

    def test_no_lost_updates_between_processes(self):
        processes = [multiprocessing.Process(target=increment, args=(self.path, 25)) for _ in range(4)]
        for p in processes:
            p.start()
        for p in processes:
            p.join(60)
        self.assertEqual(self.read().getint('a', 'n'), 100)

    def test_no_lost_updates_between_threads(self):
        import threading
        threads = [threading.Thread(target=increment, args=(self.path, 25)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        self.assertEqual(self.read().getint('a', 'n'), 100)

    def test_lock_file_is_shared(self):
        with config_lock(self.path):
            pass
        self.assertEqual(os.stat(self.path + '.lock').st_mode & 0o666, 0o666 & ~self._umask())

    @staticmethod
    def _umask():
        mask = os.umask(0)
        os.umask(mask)
        return mask


if __name__ == '__main__':
    unittest.main()
