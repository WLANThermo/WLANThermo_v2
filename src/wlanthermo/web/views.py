"""Die Seiten des Webinterfaces; Adressen wie bisher die PHP-Dateien."""
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

from flask import (Blueprint, Response, current_app, g, jsonify, redirect, render_template, request,
                   send_from_directory, session, stream_with_context)

import wlanthermo

from ..config import update_config
from ..core.client import CoreClient, CoreError
from ..core.hub import pit_topic
from . import configform, helpers, wifi

bp = Blueprint('web', __name__)
jobs = helpers.BackgroundJobs()


# ---------------------------------------------------------------- Grundlagen

@bp.before_app_request
def load_settings():
    g.ini = helpers.read_ini(current_app.config['CONFIG_FILE'])
    g.settings = helpers.Settings(g.ini)
    g.locale = g.settings.get('locale', 'locale', 'de_DE')
    g._ = helpers.translator(current_app.config['LANG_DIR'], g.locale)


@bp.app_context_processor
def template_globals():
    updates = helpers.update_check(current_app.config['TMP_DIR'])
    return {'_': g._, 'settings': g.settings, 'ini': g.ini, 'version': version(),
            'to_css_color': helpers.to_css_color,
            'show_update': (g.settings.flag('update', 'checkupdate') and helpers.updates_available(updates))
            or session.get('nextionupdate', False)}


def version():
    return 'V' + wlanthermo.VERSION if not wlanthermo.VERSION.startswith(('V', 'XXX')) else wlanthermo.VERSION


def core():
    return CoreClient(current_app.config['CORE_SOCKET'], timeout=5)


def tmp_path(name):
    return os.path.join(current_app.config['TMP_DIR'], name)


def touch(path):
    with open(path, 'a'):
        os.utime(path, None)


def set_todo(flag):
    """[ToDo]-Flag für den Watchdog bzw. Kernprozess setzen."""
    update_config({'ToDo': {flag: 'True'}}, current_app.config['CONFIG_FILE'])


def message(text, url, extra=None):
    """Kurze Meldung, danach weiter zu url (bisher meta refresh nach 1 s)."""
    return render_template('message.html', text=text, url=url, extra=extra or [])


def current_log_name():
    """Name der aktuellen Log-Datei (letztes Feld der Übergabedatei von comp)."""
    path = current_app.config.get('CURRENT_TEMP') or g.settings.get('filepath', 'current_temp')
    try:
        with open(path) as f:
            return f.read().split(';')[-1].strip()
    except OSError:
        return ''


# ---------------------------------------------------------------- Startseite

@bp.route('/')
@bp.route('/index.php')
def index():
    return render_template('index.html', main_page=True,
                           webcam=os.path.exists(tmp_path('webcam.jpg')),
                           raspicam=os.path.exists(tmp_path('raspicam.jpg')))


def core_state():
    try:
        return core().state()
    except CoreError:
        return None


@bp.route('/main.php')
def main_fragment():
    """Temperaturanzeige, wird von der Startseite bei jeder neuen Messung nachgeladen."""
    s = g.settings
    status = status_page()
    if status is not None:
        return status
    state = core_state()
    if state is None or state.get('measurement') is None:
        return render_template('_main.html', measurement=None, core_down=state is None)
    measurement = state['measurement']
    channels, sound = [], False
    for i in range(s.channel_count):
        channel = s.channel(i)
        value = measurement['temperatures'][i] if i < len(measurement['temperatures']) else None
        if value is None or not channel['show']:
            continue
        value = float('%.2f' % value)
        if value <= channel['temp_min']:
            indicator, alarm = 'temperature_indicator_blue', channel['alert']
        elif value >= channel['temp_max']:
            indicator, alarm = 'temperature_indicator_red', channel['alert']
        else:
            indicator, alarm = 'temperature_indicator', False
        sound = sound or alarm
        pits = []
        for p in range(s.pitmaster_count):
            pit = s.pitmaster(p)
            state_p = state.get(pit_topic(p))
            if pit['on'] and pit['ch'] == i and state_p is not None:
                pits.append({'number': p + 1, 'output': state_p['output'], 'setpoint': state_p['setpoint']})
        channels.append(dict(channel, number=i, value=value, indicator=indicator, alarm=alarm, pits=pits))
    regulations = []
    for p in range(s.pitmaster_count):
        state_p = state.get(pit_topic(p))
        if s.pitmaster(p)['on']:
            regulations.append({'number': p + 1, 'time': helpers.format_datetime(state_p['time'], g.locale)
                                if state_p else None})
    cpu = None
    if s.flag('Hardware', 'showcpulast'):
        temperature = helpers.cpu_temperature(s.temp_unit)
        cpu = {'load': round(helpers.cpu_load(), 1),
               'temperature': temperature if temperature == 'n/a' else round(temperature, 1)}
    if s.flag('ToDo', 'plot_start'):
        start_plot()
    for camera in ('webcam', 'raspicam'):
        if s.flag('webcam', camera + '_start'):
            start_camera(camera)
    flag = tmp_path('flag')
    if os.path.exists(flag) and time.time() - os.path.getmtime(flag) >= 20:
        os.unlink(flag)
    # Browser-Alarm: stumm geschaltet bleibt er, bis kein Alarm mehr anliegt
    websound = session.get('websoundalert', True)
    if not sound:
        session['websoundalert'] = True
    return render_template('_main.html', measurement=measurement, channels=channels, regulations=regulations,
                           time=helpers.format_datetime(measurement['time'], g.locale), cpu=cpu,
                           sound=sound, websound=websound, unit=s.unit_short)


def status_page():
    """Laufendes Update, Neustart oder Nextion-Update statt der Temperaturen anzeigen."""
    _ = g._
    if os.path.exists(tmp_path('update')):
        lines = []
        if os.path.exists(tmp_path('update.log')):
            with open(tmp_path('update.log'), errors='replace') as f:
                lines = f.read().splitlines()[-5:-1]
        session['to_update'] = True
        return render_template('_status.html', title=_('WLANThermo update'), lines=lines,
                               text=None if lines else _('The update is currently being installed') + '...')
    if os.path.exists(tmp_path('reboot')):
        return render_template('_status.html', title=None, lines=[], text=_('Restarting RaspberryPi') + '...')
    if os.path.exists(tmp_path('nextionupdate')):
        session['nextionupdate'] = True
        if os.path.exists(tmp_path('nextionupdatelog')):
            with open(tmp_path('nextionupdatelog'), errors='replace') as f:
                last = (f.read().splitlines() or [''])[-1]
            return render_template('_status.html', title=_('NEXTION Display update'), lines=[last], text=None)
    else:
        session.pop('nextionupdate', None)
    session.pop('to_update', None)
    return None


def start_plot():
    plot = tmp_path('temperaturkurve.png')
    view = tmp_path('temperaturkurve_view.png')
    if not jobs.due(plot):
        return
    if os.path.exists(view) and os.path.getsize(view) > 0:
        shutil.copy(view, plot)
    script = helpers.plot_script(g.settings, os.path.join(current_app.config['LOG_DIR'], 'TEMPLOG.csv'), view)
    jobs.start('plot', ['/usr/bin/gnuplot'], stdin=script)


def start_camera(camera):
    image = tmp_path(camera + '.jpg')
    view = tmp_path(camera + '_view.jpg')
    if not os.path.exists(image):
        shutil.copy(os.path.join(current_app.config['WWW_ROOT'], 'images', 'webcam_fail.jpg'), image)
    if not jobs.due(image):
        return
    if os.path.exists(view) and os.path.getsize(view) > 0:
        shutil.copy(view, image)
    s = g.settings
    width, height = (s.get('webcam', camera + '_size', '640x480').split('x') + ['480'])[:2]
    args = ['sudo', '-n', '/usr/bin/raspi_webcam.sh', 'W' if camera == 'webcam' else 'R', camera + '_view.jpg',
            width, height, s.get('webcam', camera + '_name')]
    if camera == 'raspicam':
        args.append(s.get('webcam', 'raspicam_exposure', 'auto'))
    jobs.start(camera, args)


@bp.route('/events')
def events():
    """Server-Sent Events: eine Nachricht je neuer Messung (die Seite lädt dann main.php nach)."""
    client = core()

    def stream():
        try:
            for changes in client.subscribe(topics=['measurement', 'pit/'], timeout=60):
                yield 'data: {}\n\n'.format(json.dumps(sorted(changes)))
        except CoreError:
            yield 'event: core-unavailable\ndata: {}\n\n'
    return Response(stream_with_context(stream()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@bp.route('/session.php')
def websound():
    value = request.args.get('websoundalert')
    if value == 'False':
        session['websoundalert'] = False
        acknowledge()
    elif value == 'True':
        session['websoundalert'] = True
    return ''


def acknowledge():
    """Alarme quittieren: über den Kernprozess, sonst über die Datei alert.ack."""
    try:
        core().acknowledge()
    except CoreError:
        touch(os.path.join(current_app.config['WWW_ROOT'], 'alert.ack'))


@bp.route('/app.php')
def app_json():
    s = g.settings
    state = core_state() or {}
    measurement = state.get('measurement')
    output = {'temp_unit': s.temp_unit}
    for p in range(s.pitmaster_count):
        pit = s.pitmaster(p)
        key = 'pit' + pit['suffix']
        output[key] = {'enabled': pit['on']}
        state_p = state.get(pit_topic(p))
        if pit['on'] and state_p:
            output[key].update(timestamp=iso(state_p['time']), setpoint=state_p['setpoint'],
                               current=state_p['current'] or 0.0, control_out=float(state_p['output']),
                               ch=str(pit['ch']), type=pit['type'], open_lid=pit['lid'])
    if s.pitmaster_count < 2:
        output['pit2'] = {'enabled': False}
    output['cpu_load'] = helpers.cpu_load()
    output['cpu_temp'] = helpers.cpu_temperature(s.temp_unit)
    output['channel'] = {}
    if measurement:
        output['timestamp'] = iso(measurement['time'])
        for i in range(s.channel_count):
            channel = s.channel(i)
            temps = measurement['temperatures']
            output['channel'][str(i)] = {
                'temp': float('%.2f' % temps[i]) if i < len(temps) and temps[i] is not None else 0.0,
                'color': channel['color'], 'state': measurement['statuses'][i],
                'temp_min': float(channel['temp_min']), 'temp_max': float(channel['temp_max']),
                'name': channel['name'], 'alert': channel['alert'], 'show': channel['show']}
    return jsonify(output)


def iso(timestamp):
    """Zeit mit Zeitzone wie PHP DateTime::ATOM, z.B. 2018-10-24T18:30:12+02:00."""
    return datetime.datetime.fromtimestamp(int(timestamp)).astimezone().isoformat()


# ---------------------------------------------------------------- Log-Dateien

def log_dir():
    return current_app.config['LOG_DIR']


@bp.route('/thermolog.php', methods=['GET', 'POST'])
def thermolog():
    _ = g._
    if 'submit' in request.form:
        for name in request.form:
            if name == 'submit' or not helpers.SAFE_NAME.match(name):
                continue
            for path in (os.path.join(log_dir(), name + '.csv'),
                         os.path.join(current_app.config['PLOT_DIR'], name + '.png')):
                if os.path.isfile(path):
                    os.unlink(path)
        return message('Files werden gelöscht...', 'thermolog.php')
    files = helpers.log_files(log_dir(), current_app.config['PLOT_DIR'], current_log_name())
    for f in files:
        f['date'] = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(f['mtime']))
    return render_template('thermolog.html', files=files)


@bp.route('/edit.php', methods=['POST'])
def rename_log():
    """Log-Datei (und Diagramm) umbenennen, aufgerufen von jeditable auf thermolog.php."""
    old = request.form.get('id', '')
    new = helpers.safe_log_name(request.form.get('value', ''))
    if not old.endswith('.csv') or not helpers.SAFE_NAME.match(old[:-4]) or not new:
        return 'Fehler...'
    if old[:-4] == current_log_name() or old == 'TEMPLOG.csv':
        return 'Fehler...'
    source = os.path.join(log_dir(), old)
    if not os.path.isfile(source) or os.path.exists(os.path.join(log_dir(), new + '.csv')):
        return 'Fehler...'
    os.rename(source, os.path.join(log_dir(), new + '.csv'))
    plot = os.path.join(current_app.config['PLOT_DIR'], old[:-4] + '.png')
    if os.path.isfile(plot):
        os.rename(plot, os.path.join(current_app.config['PLOT_DIR'], new + '.png'))
    return request.form.get('value', '')


# ---------------------------------------------------------------- Info und Updates

@bp.route('/info.php', methods=['GET', 'POST'])
def info():
    if 'check_update' in request.form:
        set_todo('check_update')
        return message('Updates werden gesucht...', 'info.php')
    return render_template('info.html', updates=helpers.update_check(current_app.config['TMP_DIR']),
                           nextionupdate=session.get('nextionupdate', False))


@bp.route('/control/update.php', methods=['GET', 'POST'])
def update():
    _ = g._
    if os.path.exists(tmp_path('update.log')) or os.path.exists(tmp_path('nextionupdatelog')):
        return message(_('The update has already been installed...'), '../index.php')
    form = request.form
    if 'back' in form:
        return message(_('Leaving this page without update...'), '../index.php')
    for step, target in (('update_step1', 'update_step2'), ('wlanthermo_update_step1', 'wlanthermo_update_step2'),
                         ('update_nextion', 'nextion_update_confirm')):
        if step in form:
            return render_template('control/update_confirm.html', confirm=target, nextion=step == 'update_nextion')
    if 'update_step2' in form:
        set_todo('start_system_update')
        return message(_('The update will now be installed...'), '../index.php')
    if 'wlanthermo_update_step2' in form:
        set_todo('start_full_update')
        return message(_('The update will now be installed...'), '../index.php')
    if 'nextion_update_confirm' in form:
        with open(tmp_path('error.txt'), 'w') as log:
            subprocess.Popen(['sudo', '-n', '/usr/sbin/wlt_2_updatenextion.sh', '/usr/share/WLANThermo/nextion/',
                              g.settings.nextion_variant], stdout=log, stderr=subprocess.STDOUT)
        return message(_('The update will now be installed...'), '../index.php')
    return render_template('control/update.html', updates=helpers.update_check(current_app.config['TMP_DIR']))


# ---------------------------------------------------------------- Neustart, Herunterfahren, neues Log

@bp.route('/control/reboot.php', methods=['GET', 'POST'])
def reboot():
    _ = g._
    if 'reboot' in request.form:
        set_todo('raspi_reboot')
        touch(tmp_path('reboot'))
        return message(_('Restarting RaspberryPi') + '...', '../index.php')
    if 'back' in request.form:
        return message(_('Cancelling reboot') + '...', '../index.php')
    return render_template('control/confirm.html', page_id='shutdown', title=_('RASPBERRY PI REBOOT'),
                           question=_('Do you want to reboot the RaspberryPi?'), action='reboot.php', name='reboot')


@bp.route('/control/shutdown.php', methods=['GET', 'POST'])
def shutdown():
    _ = g._
    if 'shutdown' in request.form:
        set_todo('raspi_shutdown')
        return message(_('RaspberryPi is shutting down') + '...', 'about:blank')
    if 'back' in request.form:
        return message(_('Cancelled shutdown') + '...', '../index.php')
    return render_template('control/confirm.html', page_id='shutdown', title=_('RASPBERRY PI SHUTDOWN'),
                           question=_('Do you want to shutdown the RaspberryPi?'), action='shutdown.php',
                           name='shutdown')


@bp.route('/control/new_log_file.php', methods=['GET', 'POST'])
def new_log_file():
    _ = g._
    if 'yes' in request.form:
        extra = []
        if g.settings.flag('ToDo', 'plot_start'):
            plot = tmp_path('temperaturkurve.png')
            name = current_log_name()
            if os.path.exists(plot) and helpers.SAFE_NAME.match(name):
                shutil.copy(plot, os.path.join(current_app.config['PLOT_DIR'], name + '.png'))
                extra.append(_('Saving current plot image') + '...')
            else:
                extra.append(_('Plot image is unavilable') + '...')
        set_todo('create_new_log')
        return message(_('New log file created') + '...', '../index.php', extra)
    if 'back' in request.form:
        return message(_('No new log file has been created') + '!...', '../index.php')
    return render_template('control/confirm.html', page_id='new_log_file_site', title=_('Create New Log File'),
                           question=_('Are you sure you want to create a new log file?'), action='new_log_file.php',
                           name='yes')


# ---------------------------------------------------------------- Telegram

TELEGRAM_TOKEN = re.compile(r'^[0-9]+:[A-Za-z0-9_-]+$')


@bp.route('/control/telegram.php')
def telegram_chats():
    """Chats, die dem Bot /start geschickt haben (für die Auswahl der Chat-ID)."""
    token = request.args.get('telegram_token', '')
    if request.args.get('telegram_getid') != 'true' or not TELEGRAM_TOKEN.match(token):
        return jsonify([])
    try:
        with urllib.request.urlopen('https://api.telegram.org/bot{}/getUpdates'.format(token), timeout=10) as r:
            updates = json.load(r)
    except (OSError, ValueError):
        return jsonify([])
    chats = []
    for result in updates.get('result', []) if updates.get('ok') else []:
        msg = result.get('message', {})
        if msg.get('text') == '/start':
            chat = msg.get('chat', {})
            chats.append({'id': chat.get('id'),
                          'name': '{} {}'.format(chat.get('first_name', ''), chat.get('last_name', '')).strip()})
    return jsonify(chats)


# ---------------------------------------------------------------- WLAN

@bp.route('/control/wifi.php', methods=['GET', 'POST'])
def wifi_page():
    page = request.args.get('page', 'wlan0_info')
    form = request.form
    notice = None
    if page == 'wpa_conf':
        found = None
        if 'SaveWPAPSKSettings' in form:
            networks = []
            for key in form:
                match = re.match(r'^ssid(\d+)$', key)
                if match and 'psk' + match.group(1) in form:
                    networks.append((int(match.group(1)), form[key], form['psk' + match.group(1)]))
            ok = wifi.save_networks([(ssid, psk) for _, ssid, psk in sorted(networks)],
                                    g.settings.get('locale', 'wlan_regdomain', 'DE'))
            return redirect('?page=wpa_conf&saved={}'.format('1' if ok else '0'))
        if 'Scan' in form:
            found = wifi.scan()
        saved = request.args.get('saved')
        if saved is not None:
            notice = 'Wifi Settings Updated Successfully' if saved == '1' else 'Wifi settings failed to be updated'
        return render_template('control/wifi.html', page=page, networks=wifi.configured_networks(), found=found,
                               notice=notice)
    if 'ifdown_wlan0' in form:
        if wifi.interface_running():
            wifi.ifdown()
            notice = 'wait'
        else:
            notice = 'Interface already down'
    elif 'ifup_wlan0' in form:
        if not wifi.interface_running():
            wifi.ifup()
            notice = 'wait'
        else:
            notice = 'Interface already up'
    elif 'ifdown_up_wlan0' in form:
        wifi.ifdown()
        wifi.ifup()
        notice = 'wait'
    return render_template('control/wifi.html', page='wlan0_info', info=wifi.interface_info(), notice=notice)


# ---------------------------------------------------------------- Einstellungen

@bp.route('/control/config.php', methods=['GET', 'POST'])
def config_page():
    _ = g._
    s = g.settings
    if 'upload_file' in request.form:
        upload = request.files.get('configfile')
        if upload is None or not upload.filename:
            return message(_('Error during upload...'), 'config.php')
        fd, path = tempfile.mkstemp(prefix='wlanthermo-config-')
        with os.fdopen(fd, 'wb') as f:
            upload.save(f)
        if os.path.getsize(path) == 0 or os.path.getsize(path) > 100000:
            os.unlink(path)
            return message(_('Error during upload...'), 'config.php')
        with open(tmp_path('updateconfig.log'), 'w') as log:
            code = subprocess.run(['/usr/local/bin/wlanthermo-updateconfig', path], stdout=log,
                                  stderr=subprocess.STDOUT).returncode
        if os.path.exists(path):
            os.unlink(path)
        return message(_('File has been processed...') if code == 0 else _('Error during file processing...'),
                       'config.php')
    if 'save' in request.form:
        changes, errors, restart = configform.evaluate(g.ini, request.form, s)
        update_config(changes, current_app.config['CONFIG_FILE'])
        touch(tmp_path('flag'))
        extra = errors + ([_('wlt_2_comp.py will be restarted...')] if restart else [])
        return message(_('Settings have been saved...'), '../index.php', extra)
    if 'back' in request.form:
        return message(_('Leaving the page without saving...'), '../index.php')
    if request.args.get('alert-test') == 'true':
        try:
            core().test_alert()
        except CoreError:
            touch(os.path.join(current_app.config['WWW_ROOT'], 'alert.test'))
        return message(_('Test alert will be sent...'), 'config.php')
    if request.args.get('update-nextion') == 'true':
        touch(tmp_path('nextionupdate'))
        session['nextionupdate'] = True
        return message(_('Update flag has been set...'), 'config.php')
    if request.args.get('calibrate-display') == 'true':
        set_todo('calibrate_display')
        return message(_('Display calibration is started...'), 'config.php')
    sensors = helpers.read_ini(current_app.config['SENSOR_FILE'])
    return render_template('control/config.html', sensors=[v for _k, v in sorted(
        sensors.items(), key=lambda item: int(item[1].get('number', '0') or 0))],
        plot_colors=helpers.PLOT_COLORS, log_levels=helpers.LOG_LEVELS,
        languages=helpers.available_languages(current_app.config['LANG_DIR']))


# ---------------------------------------------------------------- Statische Dateien (nur ohne lighttpd)

STATIC_DIRS = ('css', 'js', 'images', 'font', 'tmp', 'thermolog', 'thermoplot')
STATIC_FILES = ('buzzer.mp3', 'buzzer.ogg', 'buzzer.m4a', 'LICENSE.txt', 'apple-touch-icon-180x180-precomposed.png')


def register_static(app):
    root = app.config['WWW_ROOT']

    def choices(names):
        return ', '.join("'{}'".format(name) for name in names)

    @app.route('/<any({}):folder>/<path:filename>'.format(choices(STATIC_DIRS)))
    def static_dir(folder, filename):
        if folder == 'thermolog':
            return send_from_directory(app.config['LOG_DIR'], filename)
        return send_from_directory(os.path.join(root, folder), filename)

    @app.route('/<any({}):filename>'.format(choices(STATIC_FILES)))
    def static_file(filename):
        return send_from_directory(root, filename)
