from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import threading
import sounddevice as sd

# Import modular services
import audio_service
import tts_service
import llm_service

app = Flask(os.path.basename(__file__))
CORS(app)

# --- GLOBAL LOCK ---
# The Lock remains here to protect the critical shared resources in audio_service
AUDIO_LOCK = threading.Lock() 

# --- ROUTING AND LOGIC ---

@app.route('/api/start_record', methods=['POST'])
def start_record():
    """Starts the audio recording (Hearing Service)."""
    with AUDIO_LOCK: 
        if audio_service.start_pi_recording():
            return jsonify({'status': 'recording_started'}), 200
        else:
            # Returns 409 Conflict if recording is already active
            return jsonify({'status': 'recording_already_active'}), 409

@app.route('/api/stop_transcribe', methods=['POST'])
def stop_transcribe():
    """Stops recording and sends the audio to Whisper (Hearing Service)."""
    
    # Language parameter (optional)
    lang = request.form.get('lang', None) 
    
    transcribed_text = None
    error = None
    
    with AUDIO_LOCK:
        # This function handles stop, save, transcribe, and file cleanup
        transcribed_text, error = audio_service.stop_pi_recording_and_transcribe(lang=lang)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'text': transcribed_text, 'model': 'whisper-1'})


@app.route('/api/ask_llm', methods=['POST'])
def ask_llm():
    """Takes text, generates a response, and returns the response (Thinking Service)."""
    data = request.get_json()
    prompt = data.get('prompt', '')

    if not prompt:
        return jsonify({'error': 'No prompt provided for LLM.'}), 400

    print(f"🧠 LLM receives prompt: '{prompt}'")
    
    # 1. Generate response using the LLM Service
    response_text = llm_service.generate_response(prompt)
    
    # 2. Check for LLM errors
    if response_text.startswith("Error:"):
        print(f"❌ LLM Error: {response_text}")
        return jsonify({'error': response_text}), 500

    print(f"🤖 LLM Response: '{response_text}'")
    return jsonify({'response': response_text})


@app.route('/api/tts_speak', methods=['POST'])
def tts_speak():
    """Gives text output via espeak or OpenAI TTS (Speaking Service)."""
    data = request.get_json()
    text_to_speak = data.get('text', '')
    mode = data.get('mode', 'espeak') # Can be 'espeak' or 'openai'

    if not text_to_speak:
        return jsonify({'status': 'no_text_provided'}), 400

    # 1. Execute the speaking function from the TTS service
    success, error = tts_service.speak(text_to_speak, mode=mode)
    
    if success:
        return jsonify({'status': f'speech_successful via {mode}'}), 200
    else:
        print(f"❌ TTS Error: {error}")
        return jsonify({'status': f'speech_error via {mode}', 'details': error}), 500


if __name__ == '__main__':
    # Initialisierung der Services (wird bei Import bereits ausgeführt, hier zur Bestätigung)
    print("--- Initializing AI Services ---")
    audio_service.initialize_samplerate() 
    print(sd.query_devices())
    
    # Check for API Key presence (done in module scope, but good to check here)
    if not os.getenv("OPENAI_API_KEY"):
         print("CRITICAL: OPENAI_API_KEY is not set. Transcription and LLM will fail.")

    app.run(host='0.0.0.0', port=5001)