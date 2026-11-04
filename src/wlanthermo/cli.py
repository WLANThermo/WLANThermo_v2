"""Einstiegspunkte für die Konsolenbefehle (siehe [project.scripts] in pyproject.toml).

Die Dienste sind als Skripte mit Code auf Modulebene geschrieben. Sie werden
daher wie mit ``python3 -m wlanthermo.<modul>`` als __main__ ausgeführt.
"""
import runpy


def _run(module):
    runpy.run_module('wlanthermo.' + module, run_name='__main__', alter_sys=True)


def comp():
    _run('comp')


def nextion():
    _run('nextion_ui')


def lcd204():
    _run('lcd_204')


def watchdog():
    _run('watchdog')


def pitmaster():
    _run('pitmaster')


def hwclock():
    _run('nextion_hwclock')


def nextion_upload():
    _run('nextion_upload')


def updateconfig():
    _run('updateconfig')


def maverick():
    _run('maverick')


def update_checker():
    _run('update_checker')
