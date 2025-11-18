# hearing_service.py
# -------------------------------------------------------------------------------------------------
# Audio Recording and Transcription Service for PiBot
#
# PURPOSE: Handles capturing audio input and converting it into text using the Whisper API.
#
# FUNCTIONALITY:
# - Dynamically initializes the audio input device and sample rate.
# - Manages the start and stop of audio recording in a thread-safe manner.
# - Saves recorded audio to a temporary WAV file.
# - Transcribes the recorded audio via a POST request to the OpenAI/Whisper API.
# - Tracks transcription usage limits (MAX_TRANSCRIPTIONS).
# -------------------------------------------------------------------------------------------------

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wavfile
import os
import requests
from dotenv import load_dotenv
import threading

# Load environment variables (like OPENAI_API_KEY) from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- CONFIGURATION ---
CHANNELS = 1
INPUT_DEVICE_ID = 2  # USB PnP Sound Device (assumed)
RECORDING_PATH = "/tmp/raspi_recording.wav"
SAMPLE_RATE = 44100  # Fallback rate
MAX_TRANSCRIPTIONS = 500

# --- GLOBAL STATE ---
audio_data_buffer = []
recording_stream = None
is_recording = False
new_audio = False  # Flag, um zu prüfen, ob neue Audio aufgenommen wurde

# Session state for limits
session_state = {
    "transcription_count": 0
}

lock = threading.Lock()

def initialize_samplerate():
    """Dynamically queries the default sample rate of the input device."""
    global SAMPLE_RATE
    try:
        device_info = sd.query_devices(INPUT_DEVICE_ID, 'input')
        rate = int(device_info['default_samplerate'])
        SAMPLE_RATE = rate
        print(f"🎧 Audio Service initialized: Input Device {INPUT_DEVICE_ID} at {SAMPLE_RATE} Hz")
    except Exception as e:
        print(f"⚠️ Warning: Audio init failed. Using Fallback: {SAMPLE_RATE} Hz. Error: {e}")

def audio_callback(indata, frames, time, status):
    """Callback function for the sounddevice stream."""
    global audio_data_buffer, is_recording
    if is_recording:
        audio_data_buffer.append(indata.copy())

def start_pi_recording():
    """Starts the background audio recording stream."""
    global recording_stream, audio_data_buffer, is_recording, new_audio
    
    with lock:
        if is_recording:
            print("⚠️ Recording already active. Skipping start command.")
            return False

        print(f"🎙️ Starting local Pi recording on device {INPUT_DEVICE_ID}...")
        audio_data_buffer = []
        is_recording = True
        new_audio = False

    try:
        recording_stream = sd.InputStream(
            samplerate=SAMPLE_RATE, 
            channels=CHANNELS, 
            dtype='int16', 
            callback=audio_callback,
            device=INPUT_DEVICE_ID 
        )
        recording_stream.start()
        return True
    except Exception as e:
        with lock:
            is_recording = False
        print(f"❌ Error starting recording stream: {e}")
        return False

def stop_pi_recording_and_transcribe(lang=None):
    """Stops recording, saves the WAV, and sends it to Whisper."""
    global recording_stream, audio_data_buffer, is_recording, new_audio, session_state

    with lock:
        if not is_recording:
            print("🛑 No active recording.")
            return None, "No active recording."

        is_recording = False

        if recording_stream:
            recording_stream.stop()
            recording_stream.close()
            recording_stream = None

        if not audio_data_buffer:
            print("🛑 Recording stopped, but no data collected.")
            return None, "No audio data collected."

        # Limit prüfen
        if session_state["transcription_count"] >= MAX_TRANSCRIPTIONS:
            print(f"🛑 Transcription limit reached ({MAX_TRANSCRIPTIONS})")
            return None, f"Transcription limit reached ({MAX_TRANSCRIPTIONS})"

        # Neue Audio auf True setzen
        new_audio = True

        # Audio speichern
        recording = np.concatenate(audio_data_buffer, axis=0)
        try:
            wavfile.write(RECORDING_PATH, SAMPLE_RATE, recording)
        except Exception as e:
            new_audio = False
            return None, f"Error saving WAV file: {e}"

    # Transkription nur durchführen, wenn neue Audio vorhanden
    if not new_audio:
        print("🛑 No new audio to transcribe.")
        return None, "No new audio to transcribe."

    print("💾 Sending audio to OpenAI Whisper for transcription...")
    try:
        if not OPENAI_API_KEY:
            return None, "OPENAI_API_KEY is not set. Cannot transcribe."

        with open(RECORDING_PATH, 'rb') as af:
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
                error_msg = response.json().get('error', {}).get('message', 'Unknown OpenAI Error')
                return None, f"OpenAI Transcription Error: {error_msg}"

            j = response.json()
            transcript = j.get('text', '')

            # Transcription count erhöhen & neue Audio Flag zurücksetzen
            with lock:
                session_state["transcription_count"] += 1
                new_audio = False

            return transcript, None

    except Exception as e:
        return None, f"Transcription API call error: {e}"

    finally:
        # Clean up temporary file
        try:
            os.remove(RECORDING_PATH)
        except Exception as e:
            print(f"Warning: Could not delete temporary file: {e}")

# Init on import
initialize_samplerate()

if __name__ == "__main__":
    print("\n--- Audio Service Self-Test (Hearing) ---")
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY fehlt. Transkription wird fehlschlagen, aber Aufnahme wird getestet.")
    
    print("\n1. Starte Aufnahme (BITTE SPRECHEN SIE KURZ INS MIKROFON!)...")
    if start_pi_recording():
        import time
        time.sleep(4)
        print("\n2. Stoppe Aufnahme und starte Transkription...")
        transcript, error = stop_pi_recording_and_transcribe(lang='de')
        if error:
            print(f"\n❌ TEST FEHLGESCHLAGEN ODER FEHLER: {error}")
        else:
            print(f"\n✅ TEST ERFOLGREICH (Transkript): '{transcript}'")
    else:
        print("\n❌ TEST FEHLGESCHLAGEN: Aufnahme konnte nicht gestartet werden.")
