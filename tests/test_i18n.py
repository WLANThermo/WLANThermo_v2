"""Tests für wlanthermo.i18n: mehrere Übersetzungsdomänen in einem Prozess.

Start: python3 -m unittest tests/test_i18n.py
"""
import builtins
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo import i18n  # noqa: E402

LOCALEDIR = os.path.join(os.path.dirname(__file__), '..', 'software', 'usr', 'share', 'WLANThermo', 'locale')


class TranslatorTest(unittest.TestCase):
    def test_domains_side_by_side(self):
        with mock.patch.object(i18n, 'LOCALEDIR', LOCALEDIR), mock.patch.dict(os.environ, {'LANGUAGE': 'de_DE'}):
            comp = i18n.translator(i18n.COMP)
            pitmaster = i18n.translator(i18n.PITMASTER)
        self.assertEqual(comp('Date_Time'), 'Datum_Uhrzeit')
        self.assertEqual(pitmaster('|new overshoot: '), '|Neuer overshoot: ')
        # jede Domäne nur mit ihrem eigenen Katalog
        self.assertEqual(comp('|new overshoot: '), '|new overshoot: ')

    def test_fallback_without_catalog(self):
        with mock.patch.dict(os.environ, {'LANGUAGE': 'xx'}):
            self.assertEqual(i18n.translator(i18n.COMP)('Date_Time'), 'Date_Time')

    def test_no_global_install(self):
        had = hasattr(builtins, '_')
        i18n.translator(i18n.COMP)
        self.assertEqual(hasattr(builtins, '_'), had)


if __name__ == '__main__':
    unittest.main()
