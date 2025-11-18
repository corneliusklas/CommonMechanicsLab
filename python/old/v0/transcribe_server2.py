#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import sounddevice as sd
import numpy as np
import subprocess
import scipy.io.wavfile as wavfile
import threading # NEU: Für den Lock

app = Flask(os.path.basename(__file__)) # Nutze den Dateinamen für die App
CORS(app)

# --- KONFIGURATION ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in environment!") 

# Audio-Konfiguration (Muss auf Ihr System angepasst werden)
CHANNELS = 1
INPUT_DEVICE_ID = 2        # ID Ihres USB PnP Sound Device
RECORDING_PATH = "/tmp/raspi_recording.wav"

# Standardrate als Fallback
SAMPLE_RATE = 44100 

# Globale Variablen für die Aufnahme und Lock
audio_data_buffer = []
recording_stream = None
is_recording = False
AUDIO_LOCK = threading.Lock() # NEU: Sperre für den Zugriff auf kritische Audio-Ressourcen

# --- HILFSFUNKTIONEN ---

def initialize_samplerate():
    """Fragt die Standard-Abtastrate des Input-Geräts ab."""
    global SAMPLE_RATE
    try:
        device_info = sd.query_devices(INPUT_DEVICE_ID, 'input')
        rate = int(device_info['default_samplerate'])
        SAMPLE_RATE = rate
        print(f"🎧 Info: Dynamische Rate für Aufnahme (Gerät {INPUT_DEVICE_ID}): {SAMPLE_RATE} Hz")
    except Exception as e:
        print(f"⚠️ Warnung: Konnte Geräte-Info nicht abrufen. Verwende Fallback: {SAMPLE_RATE} Hz. Fehler: {e}")

def audio_callback(indata, frames, time, status):
    """Callback-Funktion, die Audiodaten in den Puffer schreibt."""
    if status:
        print(f"Audio-Status: {status}")
    # Prüfen, ob die Aufnahme noch aktiv ist, bevor Daten hinzugefügt werden
    if is_recording:
        audio_data_buffer.append(indata.copy())

def start_pi_recording():
    """Startet die Aufnahme im Hintergrund über das Pi-Mikrofon."""
    global recording_stream, audio_data_buffer, is_recording
    
    # Pruefen, ob die Aufnahme bereits laeuft, bevor der Puffer geloescht wird
    if is_recording:
        print("⚠️ Aufnahme läuft bereits. Überspringe Startbefehl.")
        return False

    print(f"🎙️ Starte lokale Pi-Aufnahme auf Gerät {INPUT_DEVICE_ID} mit {SAMPLE_RATE} Hz...")
    audio_data_buffer = [] # Nur leeren, wenn keine Aufnahme läuft
    is_recording = True
    
    # Öffne einen Input-Stream 
    recording_stream = sd.InputStream(
        samplerate=SAMPLE_RATE, 
        channels=CHANNELS, 
        dtype='int16', 
        callback=audio_callback,
        device=INPUT_DEVICE_ID 
    )
    recording_stream.start()
    return True

def stop_pi_recording():
    """Stoppt die Aufnahme und speichert die Daten als WAV-Datei."""
    global recording_stream, audio_data_buffer, is_recording
    
    if not is_recording:
        print("🛑 Keine Aufnahme aktiv.")
        return None
    
    # Setzen von is_recording auf False, bevor der Stream gestoppt wird
    is_recording = False 
    
    # Stream schließen
    if recording_stream:
        recording_stream.stop()
        recording_stream.close()
        recording_stream = None

    if not audio_data_buffer:
        print("🛑 Aufnahme gestoppt, aber keine Daten gesammelt.")
        return None

    # Daten konvertieren und speichern
    print(f"💾 Speichere Audio...")
    
    recording = np.concatenate(audio_data_buffer, axis=0)
    
    try:
        wavfile.write(RECORDING_PATH, SAMPLE_RATE, recording)
        return RECORDING_PATH
    except Exception as e:
        print(f"Fehler beim Speichern der WAV-Datei: {e}")
        return None


# --- FLASK ENDPUNKTE ---

@app.route('/api/start_record', methods=['POST'])
def start_record():
    """Startet die Pi-Mikrofonaufnahme (thread-sicher)."""
    with AUDIO_LOCK: 
        if start_pi_recording():
            return jsonify({'status': 'recording_started'}), 200
        else:
            return jsonify({'status': 'recording_already_active'}), 409 # Conflict

@app.route('/api/stop_transcribe', methods=['POST'])
def stop_transcribe():
    """Stoppt die Aufnahme, sendet die Datei an Whisper und gibt das Transkript zurück (thread-sicher)."""
    
    with AUDIO_LOCK:
        audio_path = stop_pi_recording()
        if not audio_path:
            return jsonify({'error': 'No audio data captured or recording was not active'}), 400

    # Da der Lock nur für die kritische Audio-Steuerung benötigt wird, 
    # kann die Transkription außerhalb des Locks stattfinden, um ihn schneller freizugeben.
    lang = request.form.get('lang', None) 
    # ... (Rest des Codes zur Transkription bleibt gleich) ...
    try:
        with open(audio_path, 'rb') as af:
            files = {'file': ('raspi_recording.wav', af)}
            data = {'model': 'whisper-1'}
            if lang:
                data['language'] = lang 
            
            headers = {'Authorization': f'Bearer {OPENAI_API_KEY}'}
            
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                print(f"OpenAI Error: {response.text}")
                return response.text, response.status_code

            j = response.json()
            return jsonify({'text': j.get('text',''), 'model': 'whisper-1'})

    except Exception as e:
        print(f"Transkriptionsfehler: {e}")
        return str(e), 500
        
    finally:
        # Temporäre Datei löschen
        try:
            os.remove(audio_path)
        except Exception as e:
            print(f"Warnung: Konnte temporäre Datei nicht löschen: {e}")

@app.route('/api/tts_speak', methods=['POST'])
def tts_speak():
    """Gibt Text über espeak auf der Pi-Audioausgabe wieder."""
    # TTS wird nicht gesperrt, da es nur ein Subprocess startet, aber nicht die globalen Audio-Variablen nutzt.
    data = request.get_json()
    text_to_speak = data.get('text', '')

    if not text_to_speak:
        return jsonify({'status': 'no_text_provided'}), 400

    print(f"🔊 Spreche Text: '{text_to_speak}'")
    
    try:
        subprocess.run(['espeak', '-v', 'de', '-s', '130', text_to_speak], 
                       check=True, 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE)
        
        return jsonify({'status': 'speech_successful', 'text': text_to_speak}), 200
    
    except subprocess.CalledProcessError as e:
        print(f"Fehler bei der espeak-Ausführung: {e.stderr.decode()}")
        return jsonify({'status': 'espeak_error', 'details': e.stderr.decode()}), 500
    except FileNotFoundError:
        return jsonify({'status': 'espeak_not_found', 'details': 'espeak command not found.'}), 500

if __name__ == '__main__':
    initialize_samplerate() 
    
    print("Verfügbare Audio-Geräte (zur Info):")
    print(sd.query_devices())
    
    app.run(host='0.0.0.0', port=5001)
