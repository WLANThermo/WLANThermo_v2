"""Benachrichtigungen per Email, Telegram und Push-URL.

Fehler beim Versand werden protokolliert und nicht weitergegeben, die
Messschleife soll in jedem Fall weiterlaufen.
"""
import logging
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText

logger = logging.getLogger('WLANthermo.notify')

# Zeitlimit in Sekunden, damit die Messschleife nicht hängen bleibt
NETWORK_TIMEOUT = 10

TELEGRAM_URL = 'https://api.telegram.org/bot{token}/sendMessage'


class EmailNotifier:
    name = 'Email'

    def __init__(self, settings):
        self.settings = settings

    def send(self, message, urgent):
        s = self.settings
        logger.info('Send mail!')
        port = 587 if s.starttls else 25
        try:
            smtp = smtplib.SMTP(s.server, port, timeout=NETWORK_TIMEOUT)
            if s.starttls:
                smtp.starttls()
            if s.auth:
                smtp.login(s.username, s.password)
            mail = MIMEText(message, 'plain', 'UTF-8')
            mail['Subject'] = s.subject
            mail['From'] = s.sender
            mail['To'] = s.recipient
            smtp.sendmail(s.sender, s.recipient, mail.as_string())
            smtp.quit()
            logger.debug('Alert Email has been sent!')
        except smtplib.SMTPException as e:
            logger.error('Error: unable to send email: {}'.format(e))
        except OSError as e:
            # Namensauflösung, Verbindungsaufbau, Zeitüberschreitung
            logger.error('Error: unable to connect to mail server (no internet connection?): {}'.format(e))


def http_request(name, url, body=None):
    """GET (body None) oder POST; Fehler werden protokolliert."""
    try:
        if body is None:
            logger.debug('{} GET request, URL: {}'.format(name, url))
            response = urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT)
        else:
            logger.debug('{} POST request, URL: {}\nbody: {}'.format(name, url, body))
            response = urllib.request.urlopen(url, body.encode('utf-8'), timeout=NETWORK_TIMEOUT)
        logger.info('{} HTTP return code: {}'.format(name, response.getcode()))
        logger.debug('{} URL: {}'.format(name, response.geturl()))
        logger.debug('{} result: {}'.format(name, response.read(500).decode('utf-8', 'replace')))
    except urllib.error.HTTPError as e:
        logger.error('{} HTTP error: {} - {}'.format(name, e.code, e.read(500).decode('utf-8', 'replace')))
    except urllib.error.URLError as e:
        logger.error('{} URLError: {}'.format(name, e.reason))
    except ValueError as e:
        # z.B. ungültige URL
        logger.error('{} ValueError: {}'.format(name, e))
    except OSError as e:
        # z.B. Zeitüberschreitung beim Lesen der Antwort
        logger.error('{} error: {}'.format(name, e))


class TelegramNotifier:
    name = 'Telegram'

    def __init__(self, settings):
        self.settings = settings

    def send(self, message, urgent):
        body = urllib.parse.urlencode({
            'text': message,
            'chat_id': self.settings.chat_id,
            # Statusmeldungen ohne Ton
            'disable_notification': 'false' if urgent else 'true'})
        http_request(self.name, TELEGRAM_URL.format(token=self.settings.token), body)


class PushNotifier:
    """Ruft eine frei konfigurierbare URL auf, {messagetext} wird durch die Nachricht ersetzt.

    Ist ein Body konfiguriert, wird er per POST gesendet, sonst GET.
    """
    name = 'Push'

    def __init__(self, settings):
        self.settings = settings

    def send(self, message, urgent):
        # Zeilenumbrüche werden als %0A übertragen. Das frühere .replace('\n', '<br/>') nach
        # quote() hatte nie eine Wirkung, weil quote() '\n' bereits kodiert hat.
        text = urllib.parse.quote(message.encode('utf-8'))
        try:
            url = self.settings.url.format(messagetext=text)
            body = self.settings.body.format(messagetext=text)
        except KeyError as key:
            logger.error('Key "{}" is undefined!'.format(key))
            return
        except (ValueError, IndexError) as e:
            logger.error('Invalid push URL or body: {}'.format(e))
            return
        http_request(self.name, url, body if self.settings.body != '' else None)


def build_notifiers(settings):
    """Die aktivierten Benachrichtigungsarten, in der Reihenfolge Email, Telegram, Push."""
    notifiers = []
    if settings.email is not None:
        notifiers.append(EmailNotifier(settings.email))
    if settings.telegram is not None:
        notifiers.append(TelegramNotifier(settings.telegram))
    if settings.push is not None:
        notifiers.append(PushNotifier(settings.push))
    return notifiers
