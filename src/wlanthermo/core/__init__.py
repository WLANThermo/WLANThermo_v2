"""Kernprozess wlanthermo-core: Messung, Pitmaster und Maverick-Empfänger als Threads in einem Prozess.

    service  Core (Threads, Signale, Ausfall) und Manager (Pitmaster, Maverick nach [ToDo])
    hub      DataHub: neueste Werte mit Zeitstempel, Warten auf Änderungen
    sources  Maverick- und Pitmaster-Werte für comp aus dem DataHub
"""
