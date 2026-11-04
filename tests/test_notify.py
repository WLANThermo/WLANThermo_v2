"""Tests für wlanthermo.comp.notify (ohne Netzwerk).

Start: python3 -m unittest tests/test_notify.py
"""
import email
import os
import smtplib
import socket
import sys
import unittest
import urllib.error
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from wlanthermo.comp import notify  # noqa: E402
from wlanthermo.comp.notify import (EmailNotifier, PushNotifier, TelegramNotifier,  # noqa: E402
                               build_notifiers)
from wlanthermo.comp.settings import EmailSettings, PushSettings, TelegramSettings  # noqa: E402

EMAIL = EmailSettings(server='smtp.example.org', auth=True, username='user', password='pw%1',
                      sender='a@example.org', recipient='b@example.org', subject='WLANThermo',
                      starttls=True)


def response(code=200, body=b'ok'):
    r = mock.Mock()
    r.getcode.return_value = code
    r.geturl.return_value = 'http://example.org/'
    r.read.return_value = body
    return r


class EmailNotifierTest(unittest.TestCase):
    def test_send_with_starttls_and_auth(self):
        with mock.patch('smtplib.SMTP') as smtp:
            EmailNotifier(EMAIL).send('Grüße vom Grill', urgent=True)
        smtp.assert_called_once_with('smtp.example.org', 587, timeout=notify.NETWORK_TIMEOUT)
        server = smtp.return_value
        server.starttls.assert_called_once_with()
        server.login.assert_called_once_with('user', 'pw%1')
        sender, recipient, text = server.sendmail.call_args[0]
        self.assertEqual((sender, recipient), ('a@example.org', 'b@example.org'))
        mail = email.message_from_string(text)
        self.assertEqual(mail['Subject'], 'WLANThermo')
        self.assertEqual(mail.get_payload(decode=True).decode('utf-8'), 'Grüße vom Grill')

    def test_without_auth_and_tls(self):
        settings = EmailSettings(**dict(EMAIL.__dict__, auth=False, starttls=False))
        with mock.patch('smtplib.SMTP') as smtp:
            EmailNotifier(settings).send('x', urgent=True)
        smtp.assert_called_once_with('smtp.example.org', 25, timeout=notify.NETWORK_TIMEOUT)
        smtp.return_value.login.assert_not_called()
        smtp.return_value.starttls.assert_not_called()

    def test_errors_are_logged(self):
        for error in (socket.gaierror('Name or service not known'), smtplib.SMTPAuthenticationError(535, b'no'),
                      socket.timeout('timed out')):
            with mock.patch('smtplib.SMTP', side_effect=error), \
                    self.assertLogs('WLANthermo.notify', 'ERROR'):
                EmailNotifier(EMAIL).send('x', urgent=True)


class TelegramNotifierTest(unittest.TestCase):
    def send(self, urgent):
        with mock.patch('urllib.request.urlopen', return_value=response()) as urlopen:
            TelegramNotifier(TelegramSettings(chat_id='42', token='TOKEN')).send('Alarm!\nKanal 1', urgent)
        url, data = urlopen.call_args[0]
        self.assertEqual(url, 'https://api.telegram.org/botTOKEN/sendMessage')
        self.assertEqual(urlopen.call_args[1], {'timeout': notify.NETWORK_TIMEOUT})
        return urllib.parse.parse_qs(data.decode('utf-8'))

    def test_alarm_with_sound(self):
        body = self.send(urgent=True)
        self.assertEqual(body, {'text': ['Alarm!\nKanal 1'], 'chat_id': ['42'], 'disable_notification': ['false']})

    def test_status_silent(self):
        self.assertEqual(self.send(urgent=False)['disable_notification'], ['true'])


class PushNotifierTest(unittest.TestCase):
    def test_get(self):
        with mock.patch('urllib.request.urlopen', return_value=response()) as urlopen:
            PushNotifier(PushSettings(url='http://box/?text={messagetext}', body='')).send('a b\nc', urgent=True)
        urlopen.assert_called_once_with('http://box/?text=a%20b%0Ac', timeout=notify.NETWORK_TIMEOUT)

    def test_post(self):
        with mock.patch('urllib.request.urlopen', return_value=response()) as urlopen:
            PushNotifier(PushSettings(url='http://box/', body='msg={messagetext}')).send('ä', urgent=True)
        urlopen.assert_called_once_with('http://box/', b'msg=%C3%A4', timeout=notify.NETWORK_TIMEOUT)

    def test_bad_template_is_logged(self):
        for url in ('http://box/{foo}', 'http://box/{messagetext', 'http://box/{0}'):
            with mock.patch('urllib.request.urlopen') as urlopen, \
                    self.assertLogs('WLANthermo.notify', 'ERROR'):
                PushNotifier(PushSettings(url=url, body='')).send('x', urgent=True)
            urlopen.assert_not_called()

    def test_http_errors_are_logged(self):
        errors = (urllib.error.HTTPError('http://box/', 500, 'err', {}, None),
                  urllib.error.URLError('refused'), socket.timeout('timed out'), ValueError('unknown url type'))
        for error in errors:
            with mock.patch('urllib.request.urlopen', side_effect=error), \
                    self.assertLogs('WLANthermo.notify', 'ERROR'):
                PushNotifier(PushSettings(url='http://box/', body='')).send('x', urgent=True)


class BuildNotifiersTest(unittest.TestCase):
    def test_order_and_selection(self):
        settings = mock.Mock(email=EMAIL, telegram=None, push=PushSettings(url='u', body=''))
        self.assertEqual([n.name for n in build_notifiers(settings)], ['Email', 'Push'])
        settings.telegram = TelegramSettings(chat_id='1', token='t')
        self.assertEqual([n.name for n in build_notifiers(settings)], ['Email', 'Telegram', 'Push'])


if __name__ == '__main__':
    unittest.main()
