#!/usr/bin/env python3
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import os
import threading
import sounddevice as sd
import subprocess
import re
import ipaddress

# Import modular services (assuming these files exist in the same directory)
import audio_service
import tts_service
import llm_service

# --- APP INITIALIZATION ---
# Setzt den statischen Ordner relativ zum Script (z.B. '../turbowrap')
app = Flask(__name__, static_folder="../web")
# CORS bleibt, falls später von externen Quellen zugegriffen werden muss
CORS(app)

# --- GLOBAL LOCK ---
# Lock zum Schutz des kritischen Audio-Aufnahme-Threads
AUDIO_LOCK = threading.Lock() 

# ---------- Hilfsfunktionen (für /devices Route) ----------

def get_mdns_devices(timeout="1s"):
    """
    Findet Geräte im Netz per mDNS (über avahi-browse)
    Gibt eine Liste von dicts zurück: [{'ip': ..., 'hostname': ...}]
    """
    devices_map = {}
    try:
        # Führt avahi-browse aus
        result = subprocess.run(
            ["timeout", str(timeout), "avahi-browse", "-alrt"],
            capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        current_ip, current_host = None, None

        for line in lines:
            # Hostname extrahieren
            if "hostname = [" in line:
                match = re.search(r"hostname = \[([^\]]+)\]", line)
                if match:
                    current_host = match.group(1).replace(".local", "")
            # IP-Adresse extrahieren
            if "address = [" in line:
                match = re.search(r"address = \[([0-9\.]+)\]", line)
                if match:
                    current_ip = match.group(1)
            # Wenn beides vorhanden, speichern und zurücksetzen
            if current_ip and current_host:
                if current_ip not in devices_map:
                    devices_map[current_ip] = current_host
                current_ip, current_host = None, None

    except Exception as e:
        print("Fehler bei mDNS-Scan:", e)

    return [{'ip': ip, 'hostname': host} for ip, host in devices_map.items()]

# =========================================================================
# --- ROUTEN FÜR STATISCHE INHALTE & UTILITY (von flask-server.py) ---
# =========================================================================

@app.route('/')
def index():
    # Serviert die Haupt-Index-Seite
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/devices')
def devices():
    """Zeigt eine HTML-Liste der im Netzwerk gefundenen mDNS-Geräte."""
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
    # Serviert die Kern-Editor-Dateien von TurboWarp
    return send_from_directory('../turbowrap/build-tw', path)

@app.route('/turbowrap/extensions/<path:path>')
def turbowrap_extensions(path):
    # Serviert die Erweiterungsdateien (wie piai_extension.js)
    return send_from_directory('../turbowrap/extensions', path)

# =========================================================================
# --- ROUTEN FÜR AI-LOGIK (von ai_server.py) ---
# =========================================================================

# --- Audio / Hearing Service ---

@app.route('/api/start_record', methods=['POST'])
def start_record():
    """Startet die Audioaufnahme."""
    with AUDIO_LOCK: 
        if audio_service.start_pi_recording():
            return jsonify({'status': 'recording_started'}), 200
        else:
            return jsonify({'status': 'recording_already_active'}), 409

@app.route('/api/stop_transcribe', methods=['POST'])
def stop_transcribe():
    """Stoppt die Aufnahme und transkribiert das Audio."""
    lang = request.form.get('lang', None) 
    transcribed_text = None
    error = None
    
    with AUDIO_LOCK:
        transcribed_text, error = audio_service.stop_pi_recording_and_transcribe(lang=lang)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'text': transcribed_text, 'model': 'whisper-1'})

# --- LLM / Thinking Service ---

@app.route('/api/ask_llm', methods=['POST'])
def ask_llm():
    """Stellt eine Anfrage an das LLM und gibt die Antwort zurück."""
    data = request.get_json()
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({'error': 'No prompt provided for LLM.'}), 400

    print(f"🧠 LLM receives prompt: '{prompt}'")
    
    response_text = llm_service.generate_response(prompt)
    
    if response_text.startswith("Error:"):
        print(f"❌ LLM Error: {response_text}")
        return jsonify({'error': response_text}), 500

    print(f"🤖 LLM Response: '{response_text}'")
    return jsonify({'response': response_text})


@app.route('/api/llm_system_message', methods=['POST'])
def llm_system_message():
    """Aktualisiert die Persona (Systemnachricht) des LLM und löscht den Verlauf."""
    data = request.get_json()
    new_message = data.get('system_message', llm_service.DEFAULT_SYSTEM_MESSAGE)

    llm_service.set_system_message(new_message)
    
    return jsonify({
        'status': 'system_message_updated',
        'new_message': new_message,
        'note': 'Conversation history was cleared automatically.'
    }), 200

@app.route('/api/llm_history_clear', methods=['POST'])
def llm_history_clear():
    """Löscht den aktuellen Gesprächsverlauf des LLM."""
    llm_service.clear_history()
    
    return jsonify({
        'status': 'history_cleared',
        'system_message': llm_service.current_system_message
    }), 200

@app.route('/api/llm_history', methods=['GET', 'POST'])
def llm_history():
    """Gibt den Gesprächsverlauf zurück (GET) oder ersetzt ihn (POST)."""
    
    if request.method == 'GET':
        history = llm_service.get_history()
        return jsonify({
            'status': 'success',
            'history': history,
            'system_message': llm_service.current_system_message
        }), 200
        
    elif request.method == 'POST':
        data = request.get_json()
        new_history = data.get('history', [])
        
        if not isinstance(new_history, list):
            return jsonify({'error': 'History must be a list of messages.'}), 400
            
        turns_set = llm_service.set_history(new_history)
        
        return jsonify({
            'status': 'history_replaced',
            'turns_set': turns_set,
            'system_message': llm_service.current_system_message
        }), 200

# --- TTS / Speaking Service ---

@app.route('/api/tts_speak', methods=['POST'])
def tts_speak():
    """Gibt Text über espeak oder OpenAI TTS aus."""
    data = request.get_json()
    text_to_speak = data.get('text', '')
    mode = data.get('mode', 'espeak')

    if not text_to_speak:
        return jsonify({'status': 'no_text_provided'}), 400

    success, error = tts_service.speak(text_to_speak, mode=mode)
    
    if success:
        return jsonify({'status': f'speech_successful via {mode}'}), 200
    else:
        print(f"❌ TTS Error: {error}")
        return jsonify({'status': f'speech_error via {mode}', 'details': error}), 500


if __name__ == '__main__':
    # Initialisierung der Services (Sampling Rate, Devices)
    print("--- Initializing AI Services ---")
    audio_service.initialize_samplerate() 
    print(sd.query_devices())
    
    # Check for API Key presence
    if not os.getenv("OPENAI_API_KEY"):
        print("CRITICAL: OPENAI_API_KEY is not set. Transcription and LLM will fail.")

    # Starte den kombinierten Server
    print("--- Starting Combined Flask Server on 0.0.0.0:5000 (Serving static content and API) ---")
    app.run(host='0.0.0.0', port=5000)