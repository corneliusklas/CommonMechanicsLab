#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile
import requests

app = Flask(__name__)
CORS(app)  # Nur in Entwicklung; Produktion ggf. restriktiv

# OpenAI API-Key aus Environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in environment!")

def save_upload(file_storage):
    fd, path = tempfile.mkstemp(suffix='.' + file_storage.filename.split('.')[-1])
    os.close(fd)
    file_storage.save(path)
    return path

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return 'no audio file', 400
    f = request.files['audio']
    model = request.form.get('model', 'whisper-1')  # OpenAI default
    lang = request.form.get('lang', None)

    audio_path = save_upload(f)

    try:
        with open(audio_path, 'rb') as af:
            files = {'file': (f.filename, af)}
            data = {'model': model}
            headers = {'Authorization': f'Bearer {OPENAI_API_KEY}'}
            response = requests.post("https://api.openai.com/v1/audio/transcriptions",
                                     headers=headers,
                                     files=files,
                                     data=data)
        if response.status_code != 200:
            return response.text, response.status_code
        j = response.json()
        return jsonify({'text': j.get('text',''), 'model': model})
    except Exception as e:
        return str(e), 500
    finally:
        try:
            os.remove(audio_path)
        except:
            pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
