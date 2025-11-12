#!/usr/bin/env python3
from flask import Flask, send_from_directory
import subprocess
import re
import ipaddress

app = Flask(__name__, static_folder="../turbowrap")

# ---------- Hilfsfunktionen ----------

def get_mdns_devices(timeout="1s"):
    """
    Findet Geräte im Netz per mDNS (über avahi-browse)
    Gibt eine Liste von dicts zurück: [{'ip': ..., 'hostname': ...}]
    Duplikate (gleiche IP) werden entfernt.
    """
    devices_map = {}
    try:
        result = subprocess.run(
            ["timeout", str(timeout), "avahi-browse", "-alrt"],
            capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        current_ip, current_host = None, None

        for line in lines:
            # Hostname
            if "hostname = [" in line:
                match = re.search(r"hostname = \[([^\]]+)\]", line)
                if match:
                    current_host = match.group(1).replace(".local", "")
            # IP-Adresse
            if "address = [" in line:
                match = re.search(r"address = \[([0-9\.]+)\]", line)
                if match:
                    current_ip = match.group(1)
            # Wenn beides vorhanden, speichern
            if current_ip and current_host:
                if current_ip not in devices_map:
                    devices_map[current_ip] = current_host
                current_ip, current_host = None, None

    except Exception as e:
        print("Fehler bei mDNS-Scan:", e)

    return [{'ip': ip, 'hostname': host} for ip, host in devices_map.items()]

# ---------- Flask-Routen ----------

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/devices')
def devices():
    devices_list = get_mdns_devices(timeout="1s")  # Timeout 1s

    PI_SUBNET = ipaddress.IPv4Network("192.168.50.0/24")

    # Sortierung: zuerst Pi-Subnetz, dann der Rest
    def sort_key(d):
        try:
            ip_obj = ipaddress.IPv4Address(d['ip'])
            if ip_obj in PI_SUBNET:
                return (0, ip_obj)
            else:
                return (1, ip_obj)
        except:
            return (2, ipaddress.IPv4Address("0.0.0.0"))

    devices_list.sort(key=sort_key)

    # HTML-Ausgabe
    html = """
    <!DOCTYPE html><html><head><meta charset='UTF-8'><title>Netzwerkgeräte</title>
    <style>
    body{font-family:Arial,sans-serif;padding:20px;}
    table{border-collapse:collapse;width:100%;}
    th,td{border:1px solid #ddd;padding:8px;text-align:left;}
    th{background-color:#007acc;color:white;}
    tr:nth-child(even){background-color:#f2f2f2;}
    </style></head><body>
    <h1>Geräte im lokalen Netzwerk (mDNS)</h1>
    <table><tr><th>IP-Adresse</th><th>Hostname</th></tr>
    """

    for d in devices_list:
        try:
            ip_obj = ipaddress.IPv4Address(d['ip'])
            if ip_obj in PI_SUBNET:
                style = ""
            else:
                style = "color:gray;"
        except:
            style = "color:gray;"

        ip_link = f"<a href='http://{d['ip']}/' target='_blank' style='{style}'>{d['ip']}</a>"
        hostname_link = f"<a href='http://{d['hostname']}/' target='_blank' style='{style}'>{d['hostname']}</a>"

        html += f"<tr style='{style}'><td>{ip_link}</td><td>{hostname_link}</td></tr>"

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
