"""Dienst wlanthermo-web: das Webinterface hinter lighttpd (Proxy auf 127.0.0.1:8080).

Läuft als www-data. Jede offene Live-Verbindung (Server-Sent Events) belegt
einen Thread, daher mehr Threads als der Standard von waitress.
"""
import argparse
import logging

from . import create_app


def main():
    parser = argparse.ArgumentParser(description='WLANThermo web interface')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--threads', type=int, default=16)
    parser.add_argument('--www-root', default='/var/www', help='Verzeichnis mit css, js, images, tmp, conf')
    parser.add_argument('--serve-static', action='store_true', help='Statische Dateien selbst ausliefern (ohne lighttpd)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app = create_app({'WWW_ROOT': args.www_root, 'SERVE_STATIC': args.serve_static,
                      'CONFIG_FILE': args.www_root + '/conf/WLANThermo.conf',
                      'SENSOR_FILE': args.www_root + '/conf/sensor.conf'})
    from waitress import serve
    serve(app, host=args.host, port=args.port, threads=args.threads, channel_timeout=120)


if __name__ == '__main__':
    main()
