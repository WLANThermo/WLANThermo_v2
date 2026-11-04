"""Hauptdienst wlanthermo-comp: misst die Temperaturen, wertet die Grenzwerte aus, alarmiert und protokolliert.

    service    Comp (Messzyklus) und main()
    settings   Einstellungen aus WLANThermo.conf
    hardware   Platine: Software-SPI-Busse, AD-Wandler, MAX31855, Summer
    channels   welcher Fühler (wlanthermo.sensors) an welchem Kanal hängt
    alarm      Grenzwerte, Quittierung, Zeitplan der Benachrichtigungen
    notify     Email, Telegram, Push
    datafiles  Übergabedateien und Temperatur-Log
"""
