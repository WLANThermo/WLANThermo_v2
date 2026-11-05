"""Webinterface (Flask), ersetzt die PHP-Seiten unter /var/www.

Die Seiten behalten ihre bisherigen Adressen (/index.php, /control/config.php,
...), damit Lesezeichen, das vorhandene JavaScript und der Passwortschutz von
lighttpd für /control weiter passen. Statische Dateien (css, js, images, tmp,
thermolog, ...) liefert lighttpd direkt aus /var/www; zum Testen ohne lighttpd
kann Flask sie ebenfalls ausliefern (SERVE_STATIC).

Messwerte kommen über die Schnittstelle des Kernprozesses (wlanthermo.core.client),
Einstellungen werden mit update_config() unter der Konfig-Sperre geschrieben.
"""
import os
import secrets

from flask import Flask

DEFAULTS = {
    'WWW_ROOT': '/var/www',
    'CONFIG_FILE': '/var/www/conf/WLANThermo.conf',
    'SENSOR_FILE': '/var/www/conf/sensor.conf',
    'LOG_DIR': '/var/log/WLAN_Thermo',
    'CORE_SOCKET': '/run/wlanthermo/core.sock',
    'SECRET_FILE': '/var/lib/wlanthermo/web_secret',
    'SERVE_STATIC': False,
    # Kamerabilder und Diagramm höchstens so oft neu erzeugen (s)
    'IMAGE_INTERVAL': 9,
}


def secret_key(path):
    """Schlüssel für die Sitzungs-Cookies, beim ersten Start erzeugt."""
    try:
        with open(path, 'rb') as f:
            key = f.read()
        if len(key) >= 32:
            return key
    except OSError:
        pass
    key = secrets.token_bytes(32)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(key)
    except OSError:
        pass   # dann gilt der Schlüssel nur bis zum Neustart
    return key


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(DEFAULTS)
    app.config.update(config or {})
    root = app.config['WWW_ROOT']
    app.config.setdefault('TMP_DIR', os.path.join(root, 'tmp'))
    app.config.setdefault('PLOT_DIR', os.path.join(root, 'thermoplot'))
    app.config.setdefault('LANG_DIR', os.path.join(root, 'lang'))
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = secret_key(app.config['SECRET_FILE'])

    from . import views
    app.register_blueprint(views.bp)
    if app.config['SERVE_STATIC']:
        views.register_static(app)
    return app
