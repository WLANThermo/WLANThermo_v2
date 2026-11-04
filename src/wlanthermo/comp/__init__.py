"""Hauptdienst wlanthermo-comp: misst die Temperaturen, wertet die Grenzwerte aus, alarmiert und protokolliert.

    service    Comp (Messzyklus) und main()
    settings   Einstellungen aus WLANThermo.conf
    sensors    Fühlerkennlinien aus sensor.conf
    hardware   AD-Wandler, Thermoelement-Wandler, Summer
    channels   woher die Temperatur eines Kanals kommt
    alarm      Grenzwerte, Quittierung, Zeitplan der Benachrichtigungen
    notify     Email, Telegram, Push
    datafiles  Übergabedateien und Temperatur-Log
"""
