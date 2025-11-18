import subprocess
import os
import requests
import numpy as np
import scipy.io.wavfile as wav # Alias wav for scipy.io.wavfile
import time
# HINWEIS: Es werden nur noch openai, scipy, numpy benötigt.
# Die Audiowiedergabe und Konvertierung erfolgt über die installierten Systemtools ffplay/ffmpeg.
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client globally
client = OpenAI(api_key=OPENAI_API_KEY)

# --- CONFIGURATION ---
OPENAI_TTS_OUTPUT_MP3 = "/tmp/openai_output.mp3"
OPENAI_TTS_OUTPUT_WAV = "/tmp/openai_output.wav"
MODULATED_OUTPUT_WAV = "/tmp/openai_modulated.wav"

def get_audio_duration_ffprobe(file_path):
    """
    Calculates the duration of an audio file using ffprobe (part of ffmpeg).
    Requires 'ffmpeg' package to be installed on the system.
    """
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"❌ Error calculating duration with ffprobe: {e}")
        return 0.0

def convert_mp3_to_wav_ffmpeg(input_mp3, output_wav):
    """
    Converts MP3 to 16-bit PCM WAV using ffmpeg.
    This replaces the functionality of pydub.
    """
    try:
        # -i: input file, -acodec pcm_s16le: 16-bit PCM codec, -ar 44100: sample rate
        subprocess.run(
            ['ffmpeg', '-i', input_mp3, '-acodec', 'pcm_s16le', '-ar', '44100', output_wav],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"Audio converted to WAV using ffmpeg: {output_wav}")
        return True
    except Exception as e:
        print(f"❌ Error converting MP3 to WAV with ffmpeg: {e}")
        return False

def play_audio_ffplay(file_path):
    """
    Plays an audio file using the system's ffplay command.
    """
    duration_s = get_audio_duration_ffprobe(file_path)
    if duration_s == 0:
        return 0
    
    # ffplay command: -nodisp (no video window), -autoexit (exit after playing)
    try:
        print(f"▶️ Playing audio for {duration_s:.2f}s via ffplay...")
        subprocess.run(
            ['ffplay', '-nodisp', '-autoexit', '-hide_banner', '-loglevel', 'error', file_path],
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        print("ffplay playback finished.")
        return duration_s
    except FileNotFoundError:
        print("❌ Error: ffplay command not found. Please ensure ffmpeg is installed.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during ffplay playback: {e}")
        return 0


def apply_ring_modulation(input_file, output_file, frequency=80, depth=.5):
    """
    Applies a ring modulation effect to a WAV file.
    
    Args:
        input_file (str): Path to the input WAV file.
        output_file (str): Path to the output WAV file.
        frequency (float): Modulator frequency in Hz.
        depth (float): Intensity of the effect (0 to 1).
    """
    
    # Load the audio file
    rate, data = wav.read(input_file)
    
    # Ensure data is numpy array and handle stereo/mono
    data = np.array(data)
    if len(data.shape) > 1:
        data = data[:, 0]  # Use only the first channel
    
    # Create a sine wave as the modulator
    t = np.arange(len(data)) / rate
    modulator = np.sin(2 * np.pi * frequency * t)
    
    # Scale the modulation with `depth`
    modulated_data = (1 - depth) * data + depth * (data * modulator)
    
    # Normalize back into 16-bit integer values (assumed format)
    int16_max = 32767.0
    
    # Normalize the modulated data to fit within the INT16 range
    abs_max = np.max(np.abs(modulated_data))
    if abs_max > 0:
        scaling_factor = int16_max / abs_max
    else:
        scaling_factor = 1 
        
    modulated_data = np.int16(modulated_data * scaling_factor)
    
    # Save the new file
    wav.write(output_file, rate, modulated_data)
    print(f"Modulated audio saved to: {output_file}")


def say_with_openai(text, voice="fable", model="tts-1"): 
    """
    Uses OpenAI TTS to convert text to speech, applies ring modulation, and plays it.
    """
    if not text or str(text).strip() == "":
        print("say_with_openai: empty text provided, skipping TTS request")
        return False

    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set.")
            
        # 1. Generate MP3 from OpenAI
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )

        with open(OPENAI_TTS_OUTPUT_MP3, "wb") as f:
            f.write(response.content)

        # 2. Convert MP3 to WAV using ffmpeg (NO pydub needed)
        if not convert_mp3_to_wav_ffmpeg(OPENAI_TTS_OUTPUT_MP3, OPENAI_TTS_OUTPUT_WAV):
            return False # Conversion failed
        
        # 3. Apply Ring Modulation
        apply_ring_modulation(OPENAI_TTS_OUTPUT_WAV, MODULATED_OUTPUT_WAV)
        
        # 4. Play the modulated audio using ffplay (system utility)
        duration = play_audio_ffplay(MODULATED_OUTPUT_WAV)
        print(f"Playback finished (Duration: {duration}s)")

        return duration > 0
    except Exception as e:
        print(f"Error in OpenAI TTS pipeline: {e}")
        return False
    finally:
        # Clean up temporary files
        for f in [OPENAI_TTS_OUTPUT_MP3, OPENAI_TTS_OUTPUT_WAV, MODULATED_OUTPUT_WAV]:
            if os.path.exists(f):
                os.remove(f)


def speak_with_espeak(text_to_speak):
    """Uses the local espeak command for playback."""
    try:
        subprocess.run(['espeak', '-v', 'de', '-s', '130', text_to_speak], 
                       check=True, 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, f"Espeak execution error: {e.stderr.decode()}"
    except FileNotFoundError:
        return False, "espeak command not found. Install with: sudo apt install espeak"
    except Exception as e:
        return False, f"Unknown error during espeak: {e}"


def speak(text, mode="espeak"):
    """
    Main entry point for the TTS service.
    Mode 'espeak' uses local system, mode 'openai' uses cloud TTS with modulation.
    """
    print(f"🔊 Speaking Text: '{text}' using mode '{mode}'")
    if mode == "espeak":
        return speak_with_espeak(text)
    elif mode == "openai":
        return say_with_openai(text)
    else:
        return False, f"Unknown TTS mode: {mode}"

if __name__ == "__main__":
    print("\n--- TTS Service Self-Test (Speaking) ---")
    
    # --- 1. Test Espeak (Lokal) ---
    print("\n1. Teste Modus 'espeak' (Lokal)....")
    success, error = speak("Test der lokalen Sprachausgabe mit Espeak.", mode="espeak")
    if success:
        print("✅ Espeak Test erfolgreich.")
    else:
        print(f"❌ Espeak Test FEHLGESCHLAGEN: {error}")
        
    # --- 2. Test OpenAI (Cloud mit Modulation) ---
    print("\n2. Teste Modus 'openai' (Cloud mit Ringmodulation)...")
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ TEST-HINWEIS: OPENAI_API_KEY fehlt. OpenAI TTS wird übersprungen.")
    else:
        success = say_with_openai("Dies ist ein Test der roboterhaften Sprachausgabe über OpenAI.", voice="fable", model="tts-1")
        if success:
            print("✅ OpenAI TTS Test erfolgreich.")
        else:
            print("❌ OpenAI TTS Test FEHLGESCHLAGEN.")
            
    print("\n--- Test abgeschlossen ---")