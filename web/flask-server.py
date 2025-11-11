#!/usr/bin/env python3
from flask import Flask, send_from_directory
import subprocess
import re
import socket
import ipaddress

app = Flask(__name__, static_folder="../turbowrap")

# ---------- Hilfsfunktionen ----------

def get_mdns_devices():
    """Findet Geräte im Netz per mDNS (über avahi-browse)"""
    mdns_devices = {}
    try:
        result = subprocess.run(
            ["avahi-browse", "-alr"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.splitlines()
        current_name, current_ip = None, None
        for line in lines:
            if "_workstation._tcp" in line or "_http._tcp" in line:
                m = re.search(r"IPv4\s+([^\s]+)\s+_", line)
                if m:
                    current_name = m.group(1)
            if "address =" in line:
                ip_match = re.search(r"address = \[([0-9\.]+)\]", line)
                if ip_match:
                    current_ip = ip_match.group(1)
            if current_name and current_ip:
                mdns_devices[current_ip] = current_name.replace(".local", "")
                current_name, current_ip = None, None
    except Exception:
        pass
    return mdns_devices


def get_arp_devices(mdns_devices):
    """ARP-Tabelle lesen und MAC + Hostname zuordnen"""
    devices = []
    try:
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        lines = result.stdout.splitlines()

        for line in lines:
            match = re.match(r'\S+ \(([\d\.]+)\) at (\S+)', line)
            if match:
                ip, mac = match.groups()
                hostname = mdns_devices.get(ip, ip)
                devices.append({'ip': ip, 'mac': mac, 'hostname': hostname})
    except Exception as e:
        devices.append({'ip': '-', 'mac': f'Error: {e}', 'hostname': '-'})
    return devices


# ---------- Flask-Routen ----------

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/devices')
def devices():
    mdns_devices = get_mdns_devices()
    devices = get_arp_devices(mdns_devices)

    # IPs sortieren (Subnetz-Reihenfolge)
    def ip_key(dev):
        try:
            return ipaddress.IPv4Address(dev['ip'])
        except Exception:
            return ipaddress.IPv4Address("0.0.0.0")

    devices.sort(key=ip_key)

    html = """
    <!DOCTYPE html><html><head><meta charset='UTF-8'><title>Netzwerkgeräte</title>
    <style>
    body{font-family:Arial,sans-serif;padding:20px;}
    table{border-collapse:collapse;width:100%;}
    th,td{border:1px solid #ddd;padding:8px;text-align:left;}
    th{background-color:#007acc;color:white;}
    tr:nth-child(even){background-color:#f2f2f2;}
    </style></head><body>
    <h1>Geräte im lokalen Netzwerk</h1>
    <table><tr><th>IP-Adresse (Link)</th><th>Hostname</th><th>MAC-Adresse</th></tr>
    """

    for d in devices:
        ip_link = f"<a href='http://{d['ip']}' target='_blank'>{d['ip']}</a>"
        html += f"<tr><td>{ip_link}</td><td>{d['hostname']}</td><td>{d['mac']}</td></tr>"

    html += "</table></body></html>"
    return html


@app.route('/turbowrap/build-tw/<path:path>')
def turbowrap_editor(path):
    return send_from_directory('../turbowrap/build-tw', path)


@app.route('/turbowrap/extensions/<path:path>')
def turbowrap_extensions(path):
    return send_from_directory('../turbowrap/extensions', path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
