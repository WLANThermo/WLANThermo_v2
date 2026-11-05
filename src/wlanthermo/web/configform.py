"""Auswertung des Einstellungsformulars (bisher control/config.php).

evaluate() liefert nur die Werte, die gesetzt werden sollen, als
{Abschnitt: {Schlüssel: Text}}; geschrieben wird mit update_config() unter der
Konfig-Sperre. Bisher schrieb PHP die beim Seitenaufruf gelesene Datei
vollständig zurück und überschrieb so Änderungen aus der Zwischenzeit.
"""
from .helpers import from_float, to_number


class Changes:
    def __init__(self, ini):
        self.ini = ini
        self.values = {}

    def old(self, section, key):
        return self.ini.get(section, {}).get(key.lower())

    def set(self, section, key, value):
        if isinstance(value, float):
            value = from_float(value)
        self.values.setdefault(section, {})[key.lower()] = str(value)

    def changed(self, section, key, value):
        """Setzt den Wert und meldet, ob er sich geändert hat."""
        old = self.old(section, key)
        self.set(section, key, value)
        return old != self.values[section][key.lower()]


def checkbox(form, name, on='True', off='False'):
    return on if name in form else off


def number(form, name):
    return to_number(form.get(name, '0'))


def text_fields(form, changes, section, mapping):
    for field, key in mapping:
        if field in form:
            changes.set(section, key, form[field])


def evaluate(ini, form, settings):
    """(Änderungen, Fehlermeldungen, comp wird neu gestartet)"""
    c = Changes(ini)
    errors = []
    restart = lcd_restart = new_logfile = restart_pit = False

    for i in range(settings.channel_count):
        if c.old('ch_show', 'ch%d' % i) == 'True':
            if 'fuehler%d' % i in form:
                c.set('Sensoren', 'ch%d' % i, form['fuehler%d' % i])
            if 'measuring_resistance%d' % i in form:
                c.set('Messen', 'messwiderstand%d' % i, number(form, 'measuring_resistance%d' % i))
            text_fields(form, c, 'plotter', [('plot_color%d' % i, 'color_ch%d' % i)])
            text_fields(form, c, 'ch_name', [('tch%d' % i, 'ch_name%d' % i)])
            name = form.get('tch%d' % i, '')
            temp_min = number(form, 'temp_min%d' % i)
            if -40 < temp_min < 380:
                c.set('temp_min', 'temp_min%d' % i, temp_min)
            else:
                c.set('temp_min', 'temp_min%d' % i, 0)
                errors.append('Die "min" Temperatur für "{}" liegt ausserhalb des Gültigen Bereichs! '
                              '==> Gültige Werte: -40 - 380Grad'.format(name))
            temp_max = number(form, 'temp_max%d' % i)
            if -20 < temp_max < 380:
                c.set('temp_max', 'temp_max%d' % i, temp_max)
            else:
                c.set('temp_max', 'temp_max%d' % i, 200)
                errors.append('Die "max" Temperatur für "{}" liegt ausserhalb des Gültigen Bereichs! '
                              '==> Gültige Werte: -20 - 380Grad'.format(name))
            c.set('web_alert', 'ch%d' % i, checkbox(form, 'alert%d' % i))
        c.set('ch_show', 'ch%d' % i, checkbox(form, 'ch_show%d' % i))

    # Diagramm
    c.set('ToDo', 'plot_start', checkbox(form, 'plot_start'))
    c.set('plotter', 'plot_pit', checkbox(form, 'plot_pit'))
    c.set('plotter', 'plot_pit2', checkbox(form, 'plot_pit2'))
    c.set('plotter', 'keyboxframe', checkbox(form, 'keyboxframe'))
    text_fields(form, c, 'plotter', [('color_pit', 'color_pit'), ('color_pitsoll', 'color_pitsoll'),
                                     ('color_pit2', 'color_pit2'), ('color_pit2soll', 'color_pit2soll'),
                                     ('plotbereich_min', 'plotbereich_min'), ('plotbereich_max', 'plotbereich_max'),
                                     ('plotsize', 'plotsize'), ('plotname', 'plotname'), ('keybox', 'keybox')])

    # Alarmierung
    text_fields(form, c, 'Alert', [('alarm_high_template', 'alarm_high_template'),
                                   ('alarm_low_template', 'alarm_low_template'),
                                   ('status_template', 'status_template'), ('message_template', 'message_template')])
    for field in ('status_interval', 'alarm_interval'):
        if field in form:
            c.set('Alert', field, int(number(form, field)))

    # Email, Push, Telegram
    c.set('Email', 'email_alert', checkbox(form, 'email'))
    c.set('Email', 'starttls', checkbox(form, 'starttls'))
    c.set('Email', 'auth', checkbox(form, 'auth_check'))
    text_fields(form, c, 'Email', [('email_to', 'email_to'), ('email_from', 'email_from'),
                                   ('email_subject', 'email_subject'), ('email_smtp', 'server'),
                                   ('email_password', 'password'), ('email_username', 'username')])
    c.set('Push', 'push_on', checkbox(form, 'push_on'))
    text_fields(form, c, 'Push', [('push_url', 'push_url'), ('push_body', 'push_body')])
    c.set('Telegram', 'telegram_alert', checkbox(form, 'telegram_alert'))
    text_fields(form, c, 'Telegram', [('telegram_chat_id', 'telegram_chat_id'), ('telegram_token', 'telegram_token')])

    # Display
    if c.changed('Display', 'lcd_present', checkbox(form, 'lcd_show')):
        restart = lcd_restart = True
    text_fields(form, c, 'Display', [('lcd_start_page', 'start_page'), ('lcd_type', 'lcd_type')])

    # Allgemein
    c.set('Logging', 'write_new_log_on_restart', checkbox(form, 'new_logfile_restart'))
    c.set('update', 'checkupdate', checkbox(form, 'checkUpdate'))
    c.set('Hardware', 'showcpulast', checkbox(form, 'showcpulast'))
    if c.changed('Sound', 'beeper_enabled', checkbox(form, 'beeper_enabled')):
        restart = True
    if c.changed('Sound', 'beeper_on_start', checkbox(form, 'beeper_on_start')):
        restart = True
    if 'hardware_version' in form and c.changed('Hardware', 'version', form['hardware_version']):
        new_logfile = lcd_restart = restart_pit = True
    text_fields(form, c, 'locale', [('language', 'locale'), ('temp_unit', 'temp_unit')])

    # Pitmaster
    for pitmaster in range(settings.pitmaster_count):
        suffix = '' if pitmaster == 0 else str(pitmaster + 1)
        prefix = 'pit' + suffix
        section = 'Pitmaster' + suffix
        c.set('ToDo', prefix + '_on', checkbox(form, prefix + '_on'))
        c.set(section, 'pit_inverted', checkbox(form, prefix + '_inverted'))
        c.set(section, 'pit_servo_inverted', checkbox(form, prefix + '_servo_inverted'))
        c.set(section, 'pit_controller_type', checkbox(form, prefix + '_controller_type', on='PID'))
        c.set(section, 'pit_open_lid_detection', checkbox(form, prefix + '_open_lid_detection'))
        text_fields(form, c, section, [(prefix + '_curve', 'pit_curve'), (prefix + '_type', 'pit_type'),
                                       (prefix + '_io_gpio', 'pit_io_gpio'), (prefix + '_ch', 'pit_ch')])
        for field in ('man', 'kp', 'ki', 'kd', 'kp_a', 'ki_a', 'kd_a', 'set', 'pause', 'servo_deadband',
                      'ratelimit_rise', 'ratelimit_fall', 'damper_offset', 'damper_pitch'):
            if prefix + '_' + field in form:
                c.set(section, 'pit_' + field, number(form, prefix + '_' + field))
        if prefix + '_pwm_min' in form:
            c.set(section, 'pit_pwm_min', max(0, number(form, prefix + '_pwm_min')))
        if prefix + '_pwm_max' in form:
            c.set(section, 'pit_pwm_max', min(100, number(form, prefix + '_pwm_max')))
        for field in ('servo_min', 'servo_max'):
            if prefix + '_' + field in form:
                c.set(section, 'pit_' + field, min(2500, max(500, number(form, prefix + '_' + field))))

    c.set('ToDo', 'maverick_enabled', checkbox(form, 'maverick_enabled'))
    if settings.version == 'miniV2':
        # nur auf miniV2 im Formular; bisher wurde es sonst beim Speichern ausgeschaltet
        c.set('Hardware', 'max31855', checkbox(form, 'max31855'))

    # Kameras
    c.set('webcam', 'webcam_start', checkbox(form, 'webcam_start'))
    c.set('webcam', 'raspicam_start', checkbox(form, 'raspicam_start'))
    text_fields(form, c, 'webcam', [('webcam_size', 'webcam_size'), ('raspicam_size', 'raspicam_size'),
                                    ('webcam_name', 'webcam_name'), ('raspicam_name', 'raspicam_name'),
                                    ('raspicam_exposure', 'raspicam_exposure')])

    # Logging
    text_fields(form, c, 'daemon_logging', [('loglevel_pit', 'level_pit'), ('loglevel_wd', 'level_wd'),
                                            ('loglevel_compy', 'level_compy'),
                                            ('loglevel_display', 'level_display')])

    # Dienste nach Änderung neu starten (führt der Watchdog bzw. der Kernprozess aus)
    if restart:
        c.set('ToDo', 'restart_thermo', 'True')
    if lcd_restart:
        c.set('ToDo', 'restart_display', 'True')
    if new_logfile:
        c.set('ToDo', 'create_new_log', 'True')
    if restart_pit:
        for pitmaster in range(settings.pitmaster_count):
            c.set('ToDo', 'restart_pitmaster' + ('' if pitmaster == 0 else str(pitmaster + 1)), 'True')

    # Werte mit Zeilenumbruch würden die Datei zerstören
    for section in c.values.values():
        for key, value in section.items():
            section[key] = value.replace('\r', ' ').replace('\n', ' ')
    return c.values, errors, restart
