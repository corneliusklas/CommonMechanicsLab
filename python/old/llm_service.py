# llm_service.py
# -------------------------------------------------------------------------------------------------
# LLM Core Service for PiBot
#
# PURPOSE: Handles all interactions with the OpenAI API (or compatible LLM).
#
# FUNCTIONALITY:
# - Manages conversation history and system message for context continuity.
# - Executes Tool Calls (Functions) requested by the LLM (e.g., set_face_emotion, get_current_time).
# - Tracks usage limits (MAX_LLM_REQUESTS).
# - Includes caching logic to return repeated prompts immediately, saving API costs.
# - Provides thread-safe global state management for history and emotion.
# -------------------------------------------------------------------------------------------------


import json
import os
import threading
from dotenv import load_dotenv
from openai import OpenAI # Offizieller OpenAI-Client
import datetime # Für get_current_time
import pytz # Für get_current_time (muss installiert sein: pip install pytz)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Globale Initialisierung ---
client = OpenAI(api_key=OPENAI_API_KEY) 

# -------------------------
# --- CONFIG / LIMITS -----
# -------------------------
MAX_LLM_REQUESTS = 500  # Beispiel: 500 Anfragen pro Session
lock = threading.Lock() # Thread-safe Zugriff

# --- GLOBAL STATE for Emotion and History ---
DEFAULT_SYSTEM_MESSAGE = (
    "Du bist ein freundlicher, hilfreicher Roboter mit einer leicht humorvollen Note. "
    "Antworte kurz und präzise auf Fragen. Dein Name ist PiBot."
)
current_system_message = DEFAULT_SYSTEM_MESSAGE
conversation_history = [{"role": "system", "content": current_system_message}]

# --- Emotion Konfiguration ---
DEFAULT_EMOTIONS = ["happy", "sad", "angry", "neutral"]
current_allowed_emotions = DEFAULT_EMOTIONS.copy() # Hält die aktuelle, editierbare Liste
last_recognized_emotion = "neutral" 

# -------------------------
# --- SESSION / CACHE -----
# -------------------------
session_state = {
    "llm_count": 0,
    "last_llm_prompt": None,
    "last_response": None
}

# -------------------------
# --- TOOL DEFINITIONS ---
# -------------------------

def get_current_time(timezone="Europe/Berlin"):
    """
    Gibt die aktuelle Uhrzeit für die angegebene Zeitzone als String zurück.
    Nützlich, um zeitbasierte Fragen zu beantworten.
    """
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.datetime.now(tz).strftime("%H:%M:%S")
        return f"Die aktuelle Uhrzeit in {timezone} ist {current_time}."
    except Exception:
        return "Fehler beim Abrufen der Uhrzeit."

def set_face_emotion(emotion: str):
    """
    Speichert die vom LLM gewählte Emotion. Gibt Bestätigung zurück.
    Verfügbare Emotionen sind dynamisch über set_allowed_emotions konfigurierbar.
    """
    global last_recognized_emotion
    last_recognized_emotion = emotion
    return f"Emotion '{emotion}' erfolgreich zur Ausführung vorgemerkt."

TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "set_face_emotion": set_face_emotion,
}

# --- DYNAMISCHE TOOL-GENERIERUNG ---

def _generate_llm_tools():
    """Generiert die LLM_TOOLS dynamisch basierend auf current_allowed_emotions."""
    
    # 1. Schema für get_current_time (konstant)
    time_tool_schema = {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Gibt die aktuelle Uhrzeit für die angegebene Zeitzone als String zurück. Nützlich, um zeitbasierte Fragen zu beantworten.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Die Zeitzone, z.B. 'Europe/Berlin'. Standard ist 'Europe/Berlin'."}
                },
                "required": [],
            },
        },
    }

    # 2. Schema für set_face_emotion (dynamisch)
    emotion_tool_schema = {
        "type": "function",
        "function": {
            "name": "set_face_emotion",
            "description": "Steuert den Gesichtsausdruck des Roboters, z.B. wenn es eine Frage beantwortet. Sollte nur einmal pro Antwort aufgerufen werden.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion": {
                        "type": "string",
                        "enum": current_allowed_emotions, # Dynamische Liste
                        "description": "Der gewünschte Gesichtsausdruck.",
                    }
                },
                "required": ["emotion"],
            },
        },
    }
    
    return [time_tool_schema, emotion_tool_schema]

LLM_TOOLS = _generate_llm_tools() 

# -------------------------
# --- HISTORY MANAGEMENT & CONFIG ---
# -------------------------

def initialize_history():
    global conversation_history, current_system_message
    conversation_history = [{"role": "system", "content": current_system_message}]

def set_system_message(new_message):
    global current_system_message
    with lock:
        current_system_message = new_message
        initialize_history()
        # ... (session_state zurücksetzen) ...
    print(f"System message updated. New message: {new_message}")

def clear_history():
    with lock:
        initialize_history()
        # ... (session_state zurücksetzen) ...
    print("Conversation history cleared.")

# In llm_service.py (KORRIGIERT)
def get_history():
    """Gibt die Konversationshistorie als JSON-serialisierbare Dictionaries zurück."""
    
    # Der erste Eintrag ist immer die System-Nachricht, die wir überspringen (da sie fix ist).
    history_to_serialize = conversation_history[1:] if len(conversation_history) > 0 else []
    
    # Konvertiert jedes Objekt in ein Standard-Dictionary
    serialized_history = []
    for message in history_to_serialize:
        
        # Prüft, ob es sich um ein Objekt handelt, das .model_dump() unterstützt (OpenAI V1.x)
        # oder ob es bereits ein Dictionary ist (z.B. User-Einträge)
        if hasattr(message, 'model_dump'):
            serialized_history.append(message.model_dump())
        elif isinstance(message, dict):
            # Dies sollte für User-Nachrichten der Fall sein
            serialized_history.append(message)
        else:
            # Fallback für andere Fälle (z.B. ältere OpenAI-Objekte, die nur Attribute haben)
            serialized_history.append({
                "role": getattr(message, 'role', 'unknown'),
                "content": getattr(message, 'content', ''),
                # Wir ignorieren hier tool_calls, da es für die History-Anzeige nicht kritisch ist
            })

    return serialized_history

def set_history(new_history):
    # ... (Ihre bestehende set_history Logik) ...
    global conversation_history
    with lock:
        history_with_system = [{"role": "system", "content": current_system_message}]
        valid_roles = ["user", "assistant"]
        turns_added = 0
        for message in new_history:
            role = message.get("role")
            content = message.get("content")
            if role in valid_roles and content:
                history_with_system.append({"role": role, "content": content})
                turns_added += 1
            else:
                print(f"⚠️ Warning: Invalid history entry skipped: {message}")
        conversation_history = history_with_system
    print(f"Conversation history replaced. Total turns (excluding system): {turns_added}")
    return turns_added

def get_last_emotion():
    """Gibt die zuletzt vom LLM vorgeschlagene Emotion zurück."""
    global last_recognized_emotion
    return last_recognized_emotion

def set_allowed_emotions(emotion_list):
    """Setzt die erlaubten Emotionen und generiert die LLM_TOOLS neu."""
    global current_allowed_emotions, LLM_TOOLS
    with lock:
        if isinstance(emotion_list, list) and emotion_list:
            current_allowed_emotions = [str(e).lower() for e in emotion_list]
            LLM_TOOLS = _generate_llm_tools() # Werkzeuge neu laden
            print(f"Allowed emotions updated to: {current_allowed_emotions}")
            return True
        return False

def get_allowed_emotions():
    """Gibt die aktuelle Liste der erlaubten Emotionen zurück."""
    global current_allowed_emotions
    return current_allowed_emotions

# -------------------------
# --- LLM RESPONSE (MAIN LOGIC) ---
# -------------------------

def generate_response(prompt):
    """
    Generiert eine Antwort vom LLM, unterstützt Tools und History.
    Gibt (response_text, executed_tools) zurück.
    """
    global conversation_history
    with lock:
        if not OPENAI_API_KEY:
            return "Error: OPENAI_API_KEY not set.", []
        if session_state["llm_count"] >= MAX_LLM_REQUESTS:
            return f"Error: LLM request limit reached ({MAX_LLM_REQUESTS}).", []

        # --- CACHE ---
        if prompt == session_state["last_llm_prompt"]:
            return session_state["last_response"], []

        # --- User-Nachricht anhängen ---
        user_message = {"role": "user", "content": prompt}
        conversation_history.append(user_message)

        final_response_text = None
        executed_tool_calls = []
        current_messages = conversation_history
        
        # --- Multi-Turn Loop für Tool-Aufrufe ---
        for turn in range(5): # Limit auf 5 Runden
            
            try:
                print(f"-> Sending prompt to LLM (Turn {turn + 1}, History: {len(current_messages)}): '{prompt}'")
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini", # Guter Tool-Support
                    messages=current_messages,
                    tools=LLM_TOOLS,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=250
                )
            except Exception as e:
                if current_messages[-1] == user_message:
                    conversation_history.pop()
                return f"An unexpected error occurred during LLM call: {e}", []

            message = response.choices[0].message
            current_messages.append(message) # Füge die LLM-Antwort zur History hinzu
            
            # 1. PRÜFEN: Hat das LLM eine Textantwort gegeben?
            if message.content:
                final_response_text = message.content.strip()
                break 
            
            # 2. PRÜFEN: Hat das LLM Tools aufgerufen?
            elif message.tool_calls:
                
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    
                    if function_name in TOOL_FUNCTIONS:
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                            function_to_call = TOOL_FUNCTIONS[function_name]
                            
                            print(f"-> Executing Tool: {function_name} with args: {arguments}")
                            
                            function_response = function_to_call(**arguments)
                            
                            # NEU: Nur relevante Tools (Emotionen) zur Rückgabe sammeln
                            if function_name == "set_face_emotion":
                                executed_tool_calls.append({
                                    "name": function_name,
                                    "args": arguments
                                })
                            
                            # Tool-Ergebnis zur History hinzufügen (für den nächsten LLM-Turn)
                            tool_message = {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            }
                            current_messages.append(tool_message)
                            
                        except Exception as e:
                            # Fehler melden
                            current_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": f"ERROR: Function execution failed with: {e}",
                            })
                            print(f"❌ Tool Execution Error: {e}")

                # Wenn keine weiteren Tools ausgeführt werden konnten (z.B. wegen Fehler), abbrechen
                if not executed_tool_calls and not any(m["role"] == "tool" for m in current_messages if "tool_call_id" in m):
                     final_response_text = "Entschuldigung, ich konnte keine Tools ausführen."
                     break
            else:
                # Kein Inhalt, kein Tool-Aufruf -> Fehler
                final_response_text = "Entschuldigung, die LLM-Antwort war unerwartet leer."
                break

        # --- Update Global History und Session State ---
        if final_response_text:
            # Die gesamte Multi-Turn History zur globalen History hinzufügen
            conversation_history[:] = current_messages 

            session_state["llm_count"] += 1
            session_state["last_llm_prompt"] = prompt
            session_state["last_response"] = final_response_text

            return final_response_text, executed_tool_calls

        # Bei Abbruch ohne finale Textantwort
        if current_messages and current_messages[-1] == user_message:
            conversation_history.pop() 
        return "Error: Die Tool-Abarbeitung konnte nach mehreren Versuchen nicht abgeschlossen werden.", []

# -------------------------
# --- INIT ON IMPORT -------
# -------------------------
initialize_history()

if __name__ == "__main__":
    # ... (Self-Test Logik) ...
    print("\n--- LLM Service Self-Test ---")
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set. Test skipped.")
    else:
        # Test 1: History und Emotion
        set_allowed_emotions(["happy", "sad"])
        set_system_message("Du bist ein Roboter und zeigst Emotionen. Wenn du gute Nachrichten hörst, sei 'happy'.")
        p1 = "Ich habe heute die höchste Punktzahl im Spiel erreicht."
        r1_text, r1_tools = generate_response(p1)
        print(f"Prompt 1: {p1}\nAntwort: {r1_text}")
        print(f"Tools ausgeführt: {r1_tools}, Letzte Emotion: {get_last_emotion()}")
        
        # Test 2: Tool Call (Zeit)
        clear_history()
        p2 = "Wie spät ist es gerade in Sydney, Australien?"
        r2_text, r2_tools = generate_response(p2)
        print(f"Prompt 2: {p2}\nAntwort: {r2_text}")
        print(f"Tools ausgeführt: {r2_tools}")

        # Test 3: Konfigurations-Test
        set_allowed_emotions(["wow", "meh"])
        print(f"Erlaubte Emotionen nach Setzen: {get_allowed_emotions()}")

        print(f"✅ Test abgeschlossen.")