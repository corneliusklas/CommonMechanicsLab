import http.server
import socketserver
import socket
import os

# 🔧 Name des Unterordners mit deiner Turbowarp-Webversion
TURBOWARP_DIR = "turbowrap-html"   # <== anpassen, falls dein Ordner anders heißt
PORT = 8000

# Absoluten Pfad berechnen
base_dir = os.path.dirname(os.path.abspath(__file__))
serve_dir = os.path.join(base_dir, TURBOWARP_DIR)

if not os.path.exists(serve_dir):
    print(f"❌ Ordner '{serve_dir}' wurde nicht gefunden!")
    exit(1)

# Lokale IP-Adresse ermitteln
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)

# In den Turbowarp-Ordner wechseln
os.chdir(serve_dir)

# Server starten
Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"🌐 Turbowarp wird bereitgestellt von:")
    print(f"   📁 {serve_dir}")
    print(f"\n👉 Öffne im Browser:")
    print(f"   • http://localhost:{PORT}")
    print(f"   • http://{local_ip}:{PORT}  (für andere Geräte im LAN)")
    print("\nBeenden mit STRG + C.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server gestoppt.")
        httpd.server_close()
