"""Hilfsfunktionen des Webinterfaces: Konfiguration, Formatierung, Systeminformationen, Dateien."""
import gettext
import json
import os
import re
import subprocess
import threading
import time

import psutil

from ..config import make_parser, read_config_file

# gnuplot-Farbnamen, für CSS mit to_css_color() umgesetzt
PLOT_COLORS = ['green', 'red', 'blue', 'olive', 'magenta', 'yellow', 'violet', 'orange',
               'mediumpurple3', 'aquamarine', 'brown', 'plum', 'skyblue', 'orange-red', 'salmon',
               'black', 'dark-grey', 'purple', 'turquoise', 'khaki', 'dark-violet', 'seagreen', 'web-blue',
               'steelblue', 'gold', 'dark-green', 'midnight-blue', 'dark-khaki', 'dark-olivegreen',
               'pink', 'chartreuse', 'gray', 'slategrey']
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
LOG_DATE_FORMAT = '%d.%m.%y %H:%M:%S'


# ---------------------------------------------------------------- Konfiguration

def read_ini(path):
    """Konfiguration als {Abschnitt: {Schlüssel: Wert}} (Schlüssel klein geschrieben wie in configparser)."""
    config = make_parser()
    read_config_file(config, path)
    return {section: dict(config.items(section, raw=True)) for section in config.sections()}


class Settings:
    """Bequemer Zugriff auf die Werte, die das Webinterface braucht (bisher $_SESSION)."""

    def __init__(self, ini):
        self.ini = ini
        self.version = self.get('Hardware', 'version', 'v3')
        self.channel_count = 12 if self.version == 'miniV2' else 10
        self.pitmaster_count = 2 if self.version == 'miniV2' else 1
        self.nextion_variant = '180' if self.version == 'miniV2' else '0'

    def get(self, section, key, default=''):
        return self.ini.get(section, {}).get(key.lower(), default)

    def flag(self, section, key):
        return self.get(section, key) == 'True'

    def channel(self, i):
        return {'name': self.get('ch_name', 'ch_name%d' % i),
                'color': self.get('plotter', 'color_ch%d' % i),
                'temp_min': to_number(self.get('temp_min', 'temp_min%d' % i, '0')),
                'temp_max': to_number(self.get('temp_max', 'temp_max%d' % i, '0')),
                'alert': self.flag('web_alert', 'ch%d' % i),
                'show': self.flag('ch_show', 'ch%d' % i)}

    def pitmaster(self, i):
        suffix = '' if i == 0 else str(i + 1)
        section = 'Pitmaster' + suffix
        return {'suffix': suffix, 'on': self.flag('ToDo', 'pit%s_on' % suffix),
                'ch': int(to_number(self.get(section, 'pit_ch', '0'))),
                'type': self.get(section, 'pit_controller_type'),
                'lid': self.get(section, 'pit_open_lid_detection')}

    @property
    def temp_unit(self):
        return self.get('locale', 'temp_unit', 'celsius')

    @property
    def unit_short(self):
        return '°F' if self.temp_unit == 'fahrenheit' else '°C'


def to_number(value):
    """Zahl aus einem Text, ',' als Dezimaltrenner erlaubt; ungültig -> 0 (wie PHP)."""
    try:
        number = float(str(value).replace(',', '.'))
    except ValueError:
        match = re.match(r'\s*-?\d+(\.\d+)?', str(value).replace(',', '.'))
        number = float(match.group()) if match else 0.0
    return int(number) if number == int(number) else number


def from_float(value):
    """Wie PHP from_float(): ohne überflüssige Nullen, '.' als Trenner."""
    text = ('%f' % float(value)).rstrip('0').rstrip('.')
    return text if text not in ('', '-0') else '0'


def to_css_color(gnuplot_color):
    return '#0080ff' if gnuplot_color == 'web-blue' else gnuplot_color.replace('-', '')


# ---------------------------------------------------------------- Übersetzung

def translator(lang_dir, locale):
    """gettext-Funktion für die Sprache aus [locale] locale (Katalog lang/<locale>/LC_MESSAGES/messages.mo)."""
    # Ohne Eintrag in einem Katalog (z.B. leere msgstr in en_US) gilt der Text der Quelle (englisch),
    # nicht eine andere Sprache; ohne eingestellte Sprache Deutsch wie bisher
    return gettext.translation('messages', localedir=lang_dir, languages=[locale or 'de_DE'],
                               fallback=True).gettext


def available_languages(lang_dir):
    """Sprachen mit Katalog, für die das System eine UTF-8-Locale hat."""
    try:
        output = subprocess.run(['locale', '-a'], capture_output=True, text=True, timeout=5).stdout
        system = {line.strip().lower().replace('utf-8', 'utf8') for line in output.splitlines()}
    except (OSError, subprocess.SubprocessError):
        system = None
    languages = []
    for name in sorted(os.listdir(lang_dir)) if os.path.isdir(lang_dir) else []:
        if os.path.isfile(os.path.join(lang_dir, name, 'LC_MESSAGES', 'messages.mo')):
            if system is None or (name + '.utf8').lower() in system:
                languages.append(name)
    return languages


DATE_FORMATS = {'de_DE': '%d.%m.%y, %H:%M:%S', 'en_GB': '%d/%m/%Y, %H:%M:%S', 'en_US': '%m/%d/%y, %I:%M:%S %p'}


def format_datetime(timestamp, locale):
    """Datum kurz, Uhrzeit mittel (wie IntlDateFormatter SHORT/MEDIUM)."""
    return time.strftime(DATE_FORMATS.get(locale, DATE_FORMATS['de_DE']), time.localtime(timestamp))


# ---------------------------------------------------------------- System

def cpu_load():
    """CPU-Auslastung in % seit dem letzten Aufruf."""
    return psutil.cpu_percent(interval=None)


def cpu_temperature(temp_unit):
    """Temperatur des Prozessors oder 'n/a' (vcgencmd über sudo, siehe sudoers)."""
    try:
        output = subprocess.run(['sudo', '-n', '/opt/vc/bin/vcgencmd', 'measure_temp'], capture_output=True,
                                text=True, timeout=5).stdout
        value = float(re.search(r"temp=([\d.]+)", output).group(1))
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError):
        return 'n/a'
    return value * 1.8 + 32 if temp_unit == 'fahrenheit' else value


def update_check(tmp_dir):
    """Inhalt von tmp/updates.json (von wlanthermo-update-checker) oder None."""
    try:
        with open(os.path.join(tmp_dir, 'updates.json')) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def updates_available(updates):
    return bool(updates) and any(updates.get(name, {}).get('available') is True for name in ('wlanthermo', 'system'))


# ---------------------------------------------------------------- Log-Dateien

SAFE_NAME = re.compile(r'^[A-Za-z0-9_\-]+$')
UMLAUTE = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}


def safe_log_name(name):
    """Dateiname ohne Endung nur aus Buchstaben, Ziffern, _ und - (wie bisher edit.php)."""
    for umlaut, replacement in UMLAUTE.items():
        name = name.replace(umlaut, replacement)
    return re.sub(r'[^a-zA-Z0-9_\-]', '', name)


def format_size(size):
    return '%sMB' % round(size / 1024 / 1024, 2) if size > 1048576 else '%dKB' % -(-size // 1024)


def log_files(log_dir, plot_dir, current_name):
    """Log-Dateien, neueste zuerst; die aktuelle und TEMPLOG.csv sind nicht änderbar."""
    files = []
    if not os.path.isdir(log_dir):
        return files
    for entry in os.scandir(log_dir):
        if not entry.name.lower().endswith('.csv') or not entry.is_file():
            continue
        base = entry.name[:-4]
        stat = entry.stat()
        files.append({'name': entry.name, 'base': base, 'size': format_size(stat.st_size), 'mtime': stat.st_mtime,
                      'editable': entry.name not in (current_name + '.csv', 'TEMPLOG.csv'),
                      'plot': os.path.isfile(os.path.join(plot_dir, base + '.png'))})
    files.sort(key=lambda f: f['mtime'], reverse=True)
    return files


# ---------------------------------------------------------------- Diagramm

def plot_script(settings, log_file, output):
    """gnuplot-Skript für das Temperaturdiagramm (wie bisher getPlotConfig())."""
    s = settings
    width, height = (s.get('plotter', 'plotsize', '800x500').split('x') + ['500'])[:2]
    unit = '[°F]' if s.temp_unit == 'fahrenheit' else '[°C]'
    keyboxframe = 'box lw 2' if s.flag('plotter', 'keyboxframe') else ''
    lines = []
    for i in range(s.channel_count):
        channel = s.channel(i)
        if channel['show']:
            lines.append("'{}' every ::1 using 1:{} with lines lw 2 lc rgb \"{}\" t '{}' axes x1y2".format(
                log_file, i + 2, channel['color'], channel['name'].replace("'", '')))
    script = ['reset', 'set encoding locale', 'set terminal png size {},{} transparent'.format(width, height),
              'set title "{}"'.format(s.get('plotter', 'plotname').replace('"', '')),
              "set datafile separator '{}'".format(s.get('Logging', 'separator', ',')),
              'set output "{}"'.format(output), 'set key {} {}'.format(s.get('plotter', 'keybox'), keyboxframe),
              'unset grid', 'set xdata time', 'set timefmt "%d.%m.%y %H:%M:%S"', 'set format x "%H:%M"',
              'set xlabel "Uhrzeit"', 'set y2label "Temperatur {}"'.format(unit),
              'set y2range [{}:{}]'.format(s.get('plotter', 'plotbereich_min'), s.get('plotter', 'plotbereich_max')),
              'set xtics nomirror', 'set y2tics nomirror']
    plot_pit, plot_pit2 = s.flag('plotter', 'plot_pit'), s.flag('plotter', 'plot_pit2')
    if plot_pit or plot_pit2:
        script += ['set ylabel "Pitmaster %"', 'set yrange ["0":"105"]', 'set ytics nomirror']
        n = s.channel_count
        if plot_pit:
            lines.append("'{}' every ::1 using 1:{} with lines lw 2 lc rgbcolor '{}' t 'Pitmaster Sollwert'  axes x1y2"
                         .format(log_file, n + 3, s.get('plotter', 'color_pitsoll')))
            lines.append("'{}' every ::1 using 1:{} with lines lw 2 lc rgbcolor '{}' t 'Pitmaster %' axes x1y1"
                         .format(log_file, n + 2, s.get('plotter', 'color_pit')))
        if plot_pit2 and s.pitmaster_count > 1:
            lines.append("'{}' every ::1 using 1:{} with lines lw 2 lc rgbcolor '{}' t 'Pitmaster 2 Sollwert'  axes x1y2"
                         .format(log_file, n + 5, s.get('plotter', 'color_pit2soll')))
            lines.append("'{}' every ::1 using 1:{} with lines lw 2 lc rgbcolor '{}' t 'Pitmaster 2 %' axes x1y1"
                         .format(log_file, n + 4, s.get('plotter', 'color_pit2')))
    else:
        script += ['set ylabel "Temperatur [°C]"',
                   'set yrange [{}:{}]'.format(s.get('plotter', 'plotbereich_min'), s.get('plotter', 'plotbereich_max')),
                   'set ytics nomirror']
    if lines:
        script.append('plot ' + ', '.join(lines))
    return ';\n'.join(script) + '\n'


class BackgroundJobs:
    """Erzeugt Diagramm und Kamerabilder höchstens alle `interval` Sekunden, nie zweimal gleichzeitig."""

    def __init__(self, interval=9):
        self.interval = interval
        self.lock = threading.Lock()
        self.running = {}

    def due(self, path):
        try:
            return time.time() - os.path.getmtime(path) >= self.interval
        except OSError:
            return True

    def start(self, name, args, stdin=None):
        """Startet args im Hintergrund, wenn der vorige Lauf fertig ist."""
        with self.lock:
            process = self.running.get(name)
            if process is not None and process.poll() is None:
                return False
            try:
                process = subprocess.Popen(args, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                return False
            if stdin:
                try:
                    process.stdin.write(stdin.encode('utf-8'))
                    process.stdin.close()
                except OSError:
                    pass
            self.running[name] = process
            return True
