@echo off
echo Es sollte keine unverarbeitete kompilierte Datei im Ordner liegen!
if exist NX3224T028_v*.tft (
    echo Ausgabedatei exisitert bereits!
    pause
    exit
)
echo Skript muss im Build Ordner liegen ('bianyi')
echo Bitte mit den genannten Einstellungen kompilieren!
echo .

echo main.Enhanced.txt=0 setzen
echo Display NX3224T024 Rotation: 90
:STAGE1A
IF EXIST NX3224T028_v* GOTO STAGE1B
TIMEOUT /T 1 >nul
GOTO STAGE1A
:STAGE1B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224T024_0.tft >nul

echo Display NX3224T024 Rotation: 270
:STAGE2A
IF EXIST NX3224T028_v* GOTO STAGE2B
TIMEOUT /T 1 >nul
GOTO STAGE2A
:STAGE2B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224T024_180.tft >nul

echo Display NX3224T028 Rotation: 270
:STAGE3A
IF EXIST NX3224T028_v* GOTO STAGE3B
TIMEOUT /T 1 >nul
GOTO STAGE3A
:STAGE3B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224T028_180.tft >nul

echo Display NX3224T028 Rotation: 90
:STAGE4A
IF EXIST NX3224T028_v* GOTO STAGE4B
TIMEOUT /T 1 >nul
GOTO STAGE4A
:STAGE4B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224T028_0.tft >nul

echo main.Enhanced.txt=1 setzen
echo Display NX3224K024 Rotation: 90
:STAGE5A
IF EXIST NX3224T028_v* GOTO STAGE5B
TIMEOUT /T 1 >nul
GOTO STAGE5A
:STAGE5B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224K024_0.tft >nul

echo Display NX3224K024 Rotation: 270
:STAGE6A
IF EXIST NX3224T028_v* GOTO STAGE6B
TIMEOUT /T 1 >nul
GOTO STAGE6A
:STAGE6B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224K024_180.tft >nul

echo Display NX3224K028 Rotation: 270
:STAGE7A
IF EXIST NX3224T028_v* GOTO STAGE7B
TIMEOUT /T 1 >nul
GOTO STAGE7A
:STAGE7B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224K028_180.tft >nul

echo Display NX3224K028 Rotation: 90
:STAGE8A
IF EXIST NX3224T028_v* GOTO STAGE8B
TIMEOUT /T 1 >nul
GOTO STAGE8A
:STAGE8B
echo Datei gefunnden, bitte warten...
REM Wait for compile to finish....
TIMEOUT /T 5 >nul
move /Y NX3224T028_v* NX3224K028_0.tft >nul

echo Kompilieren abgeschlossen
echo Die *.tft Dateien können jetzt verschoben werden