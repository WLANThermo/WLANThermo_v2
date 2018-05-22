@echo off
echo Skript muss im Build Ordner liegen ('bianyi')
echo Es sollte keine unverarbeitete kompilierte Datei im Ordner liegen!
echo Nach dem kompilieren mit den genannten Einstellungen bitte bestätigen
echo main.Enhanced.txt=0 setzen
echo Display NX3224T024 Rotation: 90
pause
move /Y NX3224T028_v* NX3224T024_0.tft
echo Display NX3224T024 Rotation: 270
pause
move /Y NX3224T028_v* NX3224T024_180.tft
echo Display NX3224T028 Rotation: 270
pause
move /Y NX3224T028_v* NX3224T028_180.tft
echo Display NX3224T028 Rotation: 90
pause
move /Y NX3224T028_v* NX3224T028_0.tft
echo main.Enhanced.txt=1 setzen
echo Display NX3224K024 Rotation: 90
pause
move /Y NX3224T028_v* NX3224K024_0.tft
echo Display NX3224K024 Rotation: 270
pause
move /Y NX3224T028_v* NX3224K024_180.tft
echo Display NX3224K028 Rotation: 270
pause
move /Y NX3224T028_v* NX3224K028_180.tft
echo Display NX3224K028 Rotation: 90
pause
move /Y NX3224T028_v* NX3224K028_0.tft
echo *.tft Dateien können jetzt verschoben werden