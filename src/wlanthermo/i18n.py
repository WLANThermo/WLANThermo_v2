"""Übersetzungen der Dienste.

Jedes Modul holt sich seine Übersetzungsfunktion für die Domäne seines Dienstes:

    _ = translator(COMP)

statt gettext.install(), das _ global für den ganzen Prozess setzt. Im
Kernprozess laufen mehrere Dienste, jeder mit seinem eigenen Katalog.
Die Sprache kommt wie bei gettext.install() aus LANGUAGE, LC_ALL, LC_MESSAGES, LANG.
"""
import gettext

LOCALEDIR = '/usr/share/WLANThermo/locale/'

COMP = 'wlt_2_comp'
PITMASTER = 'wlt_2_pitmaster'


def translator(domain):
    """gettext-Funktion der Domäne; ohne Katalog werden die Texte unverändert zurückgegeben."""
    return gettext.translation(domain, localedir=LOCALEDIR, fallback=True).gettext
