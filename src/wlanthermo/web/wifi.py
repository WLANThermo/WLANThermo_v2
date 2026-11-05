"""WLAN-Einstellungen (bisher control/wifi.php, nach SirLagz).

Alle Befehle laufen ohne Shell mit Argumentlisten; die privilegierten über sudo
mit genau den Aufrufen, die sudoers.d/WLANThermo erlaubt.
"""
import os
import re
import subprocess
import tempfile
import time

WPA_SUPPLICANT = '/etc/wpa_supplicant/wpa_supplicant.conf'
WIFIDATA = '/tmp/wifidata'   # so in sudoers freigegeben


def run(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                env=dict(os.environ, LANG='C', LC_ALL='C'))
        return result.returncode, result.stdout
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)


def sudo(*args, timeout=15):
    return run(['sudo', '-n'] + list(args), timeout=timeout)


INFO_PATTERNS = {
    'hw_address': r'ether ([0-9a-f:]+)', 'ip_address': r'inet ([0-9.]+)', 'netmask': r'netmask ([0-9.]+)',
    'rx_packets': r'RX packets (\d+)', 'tx_packets': r'TX packets (\d+)',
    'rx_bytes': r'RX packets \d+\s+bytes (\d+ \(\d+.\d+ [KMG]iB\))',
    'tx_bytes': r'TX packets \d+\s+bytes (\d+ \(\d+.\d+ [KMG]iB\))',
    'ssid': r'ESSID:"([^"]*)"', 'bssid': r'Access Point: ([0-9a-f:]+)', 'bitrate': r'Bit Rate[:=]([0-9.]+ Mb/s)',
    'link_quality': r'Link Quality=([0-9]+/[0-9]+)', 'signal_level': r'Signal level=(\S+)',
    'tx_power': r'Tx-Power=([0-9]+ dBm)',
}


def interface_info(interface='wlan0'):
    text = ' '.join(run(['ifconfig', interface])[1].split() + run(['iwconfig', interface])[1].split())
    info = {}
    for key, pattern in INFO_PATTERNS.items():
        match = re.search(pattern, text, re.I)
        info[key] = match.group(1) if match else 'no result'
    info['up'] = 'UP' in text and 'RUNNING' in text
    return info


def interface_running(interface='wlan0'):
    return 'RUNNING' in run(['ifconfig', interface])[1]


def ifdown():
    sudo('/sbin/ifdown', 'wlan0', timeout=60)


def ifup():
    sudo('/sbin/ifup', 'wlan0', timeout=60)


def configured_networks():
    """[(SSID, Passwort)] aus wpa_supplicant.conf; das Passwort steht als Kommentar #psk=... darin."""
    _, text = sudo('/bin/cat', WPA_SUPPLICANT)
    ssids, psks = [], []
    for line in text.splitlines():
        if re.match(r'^\s*ssid', line, re.I):
            ssids.append(line.split('=', 1)[1].strip().strip('"'))
        if re.search(r'#psk', line, re.I):
            psks.append(line.split('=', 1)[1].strip().strip('"'))
    return [(ssid, psks[i] if i < len(psks) else '') for i, ssid in enumerate(ssids)]


def save_networks(networks, regdomain):
    """networks: [(SSID, Passwort)]; ungültige Passwörter (nicht 8..63 Zeichen) werden ausgelassen."""
    config = 'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry={}\n'.format(
        re.sub(r'[^A-Z]', '', regdomain.upper())[:2] or 'DE')
    for ssid, psk in networks:
        if not ssid or not 8 <= len(psk) <= 63 or '\n' in ssid + psk:
            continue
        code, output = run(['wpa_passphrase', ssid, psk])
        if code == 0:
            config += output
    # Datei ohne Shell schreiben; /tmp/wifidata ist der in sudoers freigegebene Pfad
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(WIFIDATA))
    with os.fdopen(fd, 'w') as f:
        f.write(config)
    os.replace(tmp, WIFIDATA)
    code, _ = sudo('/bin/cp', WIFIDATA, WPA_SUPPLICANT)
    return code == 0


def channel_of(frequency):
    try:
        frequency = int(frequency)
    except ValueError:
        return 'Invalid Channel'
    if 2412 <= frequency <= 2472 and (frequency - 2412) % 5 == 0:
        return (frequency - 2412) // 5 + 1
    return 'Invalid Channel'


SECURITY = {
    '[WPA2-PSK-CCMP][ESS]': 'WPA2-PSK (AES)', '[WPA2-PSK-TKIP][ESS]': 'WPA2-PSK (TKIP)',
    '[WPA-PSK-TKIP+CCMP][WPS][ESS]': 'WPA-PSK (TKIP/AES) with WPS',
    '[WPA-PSK-TKIP+CCMP][WPA2-PSK-TKIP+CCMP][ESS]': 'WPA/WPA2-PSK (TKIP/AES)',
    '[WPA-PSK-TKIP][ESS]': 'WPA-PSK (TKIP)', '[WEP][ESS]': 'WEP',
}


def scan(wait=5):
    """Gefundene Netze als [{'ssid', 'channel', 'signal', 'security'}]."""
    sudo('/sbin/wpa_cli', 'scan')
    time.sleep(wait)
    _, output = sudo('/sbin/wpa_cli', 'scan_results')
    networks = []
    for line in output.splitlines():
        fields = re.split(r'\t+', line)
        if len(fields) >= 5 and re.match(r'^[0-9a-f:]{17}$', fields[0], re.I):
            networks.append({'ssid': fields[4], 'channel': channel_of(fields[1]), 'signal': fields[2] + ' dBm',
                             'security': SECURITY.get(fields[3], fields[3])})
    return networks
