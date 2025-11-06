#!/usr/bin/env python3
from flask import Flask, send_from_directory, render_template_string
import subprocess
import re
import os
import socket

app = Flask(__name__, static_folder="../turbowrap")

# Dashboard
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Geräte im lokalen Netzwerk
@app.route('/devices')
# Geräte im lokalen Netzwerk
@app.route('/devices')
def devices():
    devices = []
    try:
        # 1. ARP-Tabelle auslesen
        # Wir verwenden 'ip neighbour' (modern) oder 'arp -a' (kompatibel)
        # Bleiben wir beim ARP-Befehl:
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        
        for line in lines:
            match = re.match(r'\S+ \(([\d\.]+)\) at (\S+)', line)
            if match:
                ip, mac = match.groups()
                hostname = "-"
                
                # 2. Hostnamen-Auflösung (Reverse DNS Look-up)
                try:
                    # Der gethostbyaddr-Aufruf kann bei unbekannter IP schnell fehlschlagen
                    # Wir verwenden einen Timeout, falls der DNS-Server nicht antwortet (wichtig!)
                    # Da socket.gethostbyaddr keinen Timeout unterstützt, muss dies ggf. 
                    # in einem separaten Thread oder Prozess laufen, für Einfachheit verzichten wir hier auf einen harten Timeout,
                    # aber der Aufruf ist in einem try/except-Block.
                    resolved_name = socket.gethostbyaddr(ip)[0]
                    # Entfernen Sie ggf. die lokale Domain (z.B. .fritz.box)
                    hostname = resolved_name.split('.')[0] 
                except socket.herror:
                    # Hostname nicht gefunden
                    hostname = ip 
                except Exception:
                    # Andere Fehler
                    hostname = ip
                    
                devices.append({'ip': ip, 'mac': mac, 'hostname': hostname})
                
    except Exception as e:
        devices.append({'ip': '-', 'mac': f'Error: {e}', 'hostname': '-'})

    # 3. HTML-Generierung mit Hostname und klickbarer IP
    html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Netzwerkgeräte</title>"
    html += "<style>body{font-family:Arial,sans-serif;padding:20px;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ddd;padding:8px;text-align:left;}th{background-color:#007acc;color:white;}tr:nth-child(even){background-color:#f2f2f2;}</style></head><body>"
    html += "<h1>Geräte im lokalen Netzwerk</h1><table><tr><th>IP-Adresse (Link)</th><th>Hostname</th><th>MAC-Adresse</th></tr>"
    
    for d in devices:
        # Erstellt den Link: <a href="http://IP_Adresse">IP_Adresse</a>
        ip_link = f"<a href='http://{d['ip']}' target='_blank'>{d['ip']}</a>"
        
        html += f"<tr><td>{ip_link}</td><td>{d['hostname']}</td><td>{d['mac']}</td></tr>"
        
    html += "</table></body></html>"
    return html

# TurboWarp Editor
@app.route('/turbowrap/build-tw/<path:path>')
def turbowrap_editor(path):
    return send_from_directory('../turbowrap/build-tw', path)

# Extensions
@app.route('/turbowrap/extensions/<path:path>')
def turbowrap_extensions(path):
    return send_from_directory('../turbowrap/extensions', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
