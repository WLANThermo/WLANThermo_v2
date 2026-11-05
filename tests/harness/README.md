# Regressions-Harnesse

Lassen die Daemons gegen simulierte Hardware (pigpio, psutil, SMTP, HTTP) laufen.
Alle Läufe finden in einem eigenen User- und Mount-Namespace statt (`unshare -rm`),
in dem ein leeres Temp-Verzeichnis über `/var` liegt; die fest verdrahteten Pfade
(`/var/www/conf`, `/var/log`, `/var/run`) treffen also nie das echte System.
Benötigt werden Linux mit unprivilegierten User-Namespaces und ein Python mit den
Abhängigkeiten aus `pyproject.toml` (Interpreter über `PYTHON=...` wählbar).

## Vergleichsläufe comp und Pitmaster

`run.sh` (comp, Szenarien a/b) und `pit_run.sh` (12 Pitmaster-Szenarien) führen
einen Stand von `src/` mit fester Uhr aus und schreiben alle Ausgaben
(Hardware-Aufrufe, Logs, Benachrichtigungen, Dateien) in ein Verzeichnis. Zwei
Stände werden verglichen, indem man beide laufen lässt und die Ausgaben diffed:

    tests/harness/run.sh bec8695 /tmp/comp_old
    tests/harness/run.sh WORKTREE /tmp/comp_new
    diff -r /tmp/comp_old /tmp/comp_new

    tests/harness/pit_run.sh 0756bd9 /tmp/pit_old
    tests/harness/pit_run.sh WORKTREE /tmp/pit_new
    diff -r /tmp/pit_old /tmp/pit_new

`bec8695` bzw. `0756bd9` sind die Stände vor dem Umbau. Erwartete Unterschiede:
`curve_to_pid` (der erste D-Anteil nach dem Wechsel Kurve -> PID ist jetzt korrekt,
weil die Regler keinen Zustand mehr teilen). Der comp-Harness testet comp als
eigenständigen Daemon (mit current.temp), nicht den Betrieb im Kernprozess.

## Kernprozess

`core_run.sh` startet `wlanthermo-core` mit echten Threads und echter Zeit
(Messung, Pitmaster, Abschalten bei veralteten Messwerten, API, Beenden) und
prüft 22 Punkte; Exit-Code 0, wenn alle bestanden.
