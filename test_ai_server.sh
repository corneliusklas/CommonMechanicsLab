#!/bin/bash
# Skript zur Überprüfung der AI Server API Endpunkte (localhost:5000)

# --- KONFIGURATION ---
SERVER_URL="http://localhost:5000/api"
TTS_URL="${SERVER_URL}/tts_speak"
LLM_URL="${SERVER_URL}/ask_llm"
LLM_SYSTEM_URL="${SERVER_URL}/llm_system_message"
LLM_HISTORY_CLEAR_URL="${SERVER_URL}/llm_history_clear"
LLM_HISTORY_GET_URL="${SERVER_URL}/llm_history"
RECORD_START_URL="${SERVER_URL}/start_record"
RECORD_STOP_URL="${SERVER_URL}/stop_transcribe"

# NEUE ENDPUNKTE für Tools/Status
EMOTION_GET_URL="${SERVER_URL}/get_emotion"
EMOTION_SET_ALLOWED_URL="${SERVER_URL}/set_allowed_emotions"
EMOTION_GET_ALLOWED_URL="${SERVER_URL}/get_allowed_emotions"
TTS_STATUS_URL="${SERVER_URL}/is_talking"

echo "========================================="
echo "  AI SERVER API TEST-SKRIPT (Vollständig)"
echo "  Stellt sicher, dass server.py läuft."
echo "========================================="

# --- 1. LLM History und System-Nachrichten Tests ---
echo -e "\n--- 1. LLM History und System-Nachrichten Tests ---"

# 1a. System Message setzen
NEW_SYSTEM_MSG="Du bist jetzt ein Mathematiklehrer und antwortest nur mit Zahlen und Formeln."
echo "1a. Setze neue System-Nachricht und lösche Historie..."
SYS_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"system_message\": \"$NEW_SYSTEM_MSG\"}" "$LLM_SYSTEM_URL")
if echo "$SYS_RESPONSE" | grep -q "System message updated"; then 
    echo "✅ System-Nachricht erfolgreich gesetzt: '$NEW_SYSTEM_MSG'"
else
    echo "❌ System-Nachricht Test fehlgeschlagen. Antwort: $SYS_RESPONSE"
fi

# 1b. Test mit neuer Persona
LLM_PROMPT_1="Was ist 2 plus 2?"
echo "1b. Sende Prompt (mit neuer Persona): \"$LLM_PROMPT_1\""
LLM_RESPONSE_1=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"prompt\": \"$LLM_PROMPT_1\"}" "$LLM_URL")
LLM_TEXT_1=$(echo "$LLM_RESPONSE_1" | jq -r '.response')

if [ "$LLM_TEXT_1" != "null" ] && [ -n "$LLM_TEXT_1" ]; then
    echo "🤖 Antwort (1): $LLM_TEXT_1"
else
    echo "❌ LLM-Test 1b fehlgeschlagen. Antwort: $LLM_RESPONSE_1"
fi

# 1c. Test der Historienfunktion (Folgefrage)
LLM_PROMPT_2="Was ist das Ergebnis mal 3?"
echo "1c. Sende Folge-Prompt (Historie-Test): \"$LLM_PROMPT_2\""
LLM_RESPONSE_2=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"prompt\": \"$LLM_PROMPT_2\"}" "$LLM_URL")
LLM_TEXT_2=$(echo "$LLM_RESPONSE_2" | jq -r '.response')

if [ "$LLM_TEXT_2" != "null" ] && [ -n "$LLM_TEXT_2" ]; then
    echo "🤖 Antwort (2): $LLM_TEXT_2 (Sollte sich auf Antwort 1 beziehen)"
else
    echo "❌ LLM-Test 1c fehlgeschlagen. Antwort: $LLM_RESPONSE_2"
fi

# 1d. Historie abrufen
echo "1d. Rufe Historie ab (GET /api/llm_history)..."
HIST_RESPONSE=$(curl -s "$LLM_HISTORY_GET_URL")
HIST_LENGTH=$(echo "$HIST_RESPONSE" | jq '.history | length') 

if [ "$HIST_LENGTH" -eq 4 ]; then 
    echo "✅ Historienlänge korrekt: $HIST_LENGTH Einträge gefunden."
else
    echo "❌ Historienlänge inkorrekt: $HIST_LENGTH Einträge (erwartet: 4). Antwort: $HIST_RESPONSE"
fi

# 1e. Historie löschen
echo "1e. Lösche Historie..."
CLEAR_RESPONSE=$(curl -s -X POST "$LLM_HISTORY_CLEAR_URL")
if echo "$CLEAR_RESPONSE" | grep -q "Conversation history cleared"; then 
    echo "✅ Historie erfolgreich gelöscht."
else
    echo "❌ Historie löschen fehlgeschlagen. Antwort: $CLEAR_RESPONSE"
fi


# 1f. Historie neu schreiben und prüfen (POST /api/llm_history)
echo -e "\n1f. Schreibe neue Historie (POST /api/llm_history)..."
NEW_HISTORY_PAYLOAD='{"history": [{"role": "user", "content": "Mein Name ist Lisa und ich bin 7 Jahre alt."}, {"role": "assistant", "content": "Hallo Lisa! Dann weiß ich ja, dass du 7 bist."}]}'
REPLACE_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$NEW_HISTORY_PAYLOAD" "$LLM_HISTORY_GET_URL")
TURNS_SET=$(echo "$REPLACE_RESPONSE" | jq -r '.turns_set')

if [ "$TURNS_SET" -eq 2 ]; then
    echo "✅ Historie erfolgreich mit 2 Einträgen ersetzt."
    
    # Test 1g: Folgefrage nach dem Ersetzen der Historie
    LLM_PROMPT_3="Wie alt bin ich nochmal?"
    echo "1g. Sende Folge-Prompt mit NEUER Historie: \"$LLM_PROMPT_3\""
    LLM_RESPONSE_3=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"prompt\": \"$LLM_PROMPT_3\"}" "$LLM_URL")
    LLM_TEXT_3=$(echo "$LLM_RESPONSE_3" | jq -r '.response')

    if [ "$LLM_TEXT_3" != "null" ] && [ -n "$LLM_TEXT_3" ]; then
        echo "🤖 Antwort (3): $LLM_TEXT_3"
        echo "✅ Historie-Set-Test erfolgreich."
    else
        echo "❌ LLM-Test 1g fehlgeschlagen. Antwort: $LLM_RESPONSE_3"
    fi
else
    echo "❌ Historie ersetzen fehlgeschlagen. Antwort: $REPLACE_RESPONSE"
fi


# --- 2. TTS Test (Sprechen) ---
echo -e "\n--- 2. TTS Test (/api/tts_speak mit Espeak) ---"
TTS_TEXT="Der Servertest läuft erfolgreich."
echo "Sende Text an TTS (Modus: espeak): \"$TTS_TEXT\""

TTS_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"text\": \"$TTS_TEXT\", \"mode\": \"espeak\"}" "$TTS_URL")

if echo "$TTS_RESPONSE" | grep -q "Audio playback started"; then 
    echo "✅ TTS-Test erfolgreich. Server hat $TTS_TEXT zur Ausgabe gesendet."
else
    echo "❌ TTS-Test fehlgeschlagen."
    echo "Antwort: $TTS_RESPONSE"
fi


# --- 3. Audio Test (Hören) ---
echo -e "\n--- 3. Audio Test (/api/start_record & /api/stop_transcribe) ---"

# 3a. Start Aufnahme
echo "3a. Starte Aufnahme über $RECORD_START_URL..."
RECORD_START_RESPONSE=$(curl -s -X POST "$RECORD_START_URL")

if echo "$RECORD_START_RESPONSE" | grep -q "Recording started"; then 
    echo "✅ Aufnahme gestartet."
    
    # Warte und fordere zum Sprechen auf
    SPEAK_DURATION=5
    echo -e "\n!!! JETZT INS MIKROFON SPRECHEN (Für $SPEAK_DURATION Sekunden) !!!"
    sleep $SPEAK_DURATION
    
    # 3b. Stop Aufnahme und Transkribieren
    echo -e "\n3b. Stoppe Aufnahme und transkribiere (Sprache: Deutsch)..."
    # KORREKTUR: Sende die Sprache als JSON-Payload, da server.py dies nun erwartet.
    TRANS_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d '{"lang": "de"}' "$RECORD_STOP_URL")
    TRANS_TEXT=$(echo "$TRANS_RESPONSE" | jq -r '.text')

    if [ "$TRANS_TEXT" != "null" ] && [ -n "$TRANS_TEXT" ] && ! echo "$TRANS_RESPONSE" | grep -q "error"; then
        echo "✅ Transkription erfolgreich."
        echo "👂 Transkribierter Text: \"$TRANS_TEXT\""
    else
        echo "❌ Transkription fehlgeschlagen."
        echo "Antwort: $TRANS_RESPONSE"
    fi

else
    echo "❌ Aufnahme konnte nicht gestartet werden."
    echo "Antwort: $RECORD_START_RESPONSE"
fi


# --- 4. Tool/Status Tests (Emotion und is_talking) ---
echo -e "\n--- 4. Tool/Status Tests (Emotion und is_talking) ---"

# 4a. Is Talking Status prüfen (sollte False sein, da TTS beendet ist)
echo "4a. Prüfe Is Talking Status (GET /api/is_talking)..."
STATUS_RESPONSE=$(curl -s "$TTS_STATUS_URL")
IS_TALKING=$(echo "$STATUS_RESPONSE" | jq -r '.is_talking')

if [ "$IS_TALKING" = "false" ]; then
    echo "✅ Is Talking Status korrekt: $IS_TALKING"
else
    echo "❌ Is Talking Status inkorrekt: $IS_TALKING"
fi

# 4b. Erlaubte Emotionen setzen
EMOTION_LIST="happy, confused, angry"
echo "4b. Setze erlaubte Emotionen: $EMOTION_LIST..."
SET_EMO_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"emotions\": [\"happy\", \"confused\", \"angry\"]}" "$EMOTION_SET_ALLOWED_URL")
if echo "$SET_EMO_RESPONSE" | grep -q "success"; then
    echo "✅ Erlaubte Emotionen erfolgreich gesetzt."
else
    echo "❌ Setzen der Emotionen fehlgeschlagen. Antwort: $SET_EMO_RESPONSE"
fi

# 4c. Erlaubte Emotionen abrufen
echo "4c. Rufe erlaubte Emotionen ab (GET /api/get_allowed_emotions)..."
GET_EMO_RESPONSE=$(curl -s "$EMOTION_GET_ALLOWED_URL")
ALLOWED_EMOS=$(echo "$GET_EMO_RESPONSE" | jq -r '.emotions | @tsv') 

if echo "$ALLOWED_EMOS" | grep -q "happy" && echo "$ALLOWED_EMOS" | grep -q "confused"; then
    echo "✅ Abrufen der Emotionen korrekt: $ALLOWED_EMOS"
else
    echo "❌ Abrufen der Emotionen fehlgeschlagen. Antwort: $GET_EMO_RESPONSE"
fi

# 4d. Letzte Emotion abrufen 
echo "4d. Rufe aktuelle Emotion ab (GET /api/get_emotion)..."
LAST_EMO_RESPONSE=$(curl -s "$EMOTION_GET_URL")
LAST_EMO=$(echo "$LAST_EMO_RESPONSE" | jq -r '.emotion')

if [ "$LAST_EMO" = "neutral" ] || [ -n "$LAST_EMO" ]; then
    echo "✅ Letzte Emotion korrekt: $LAST_EMO"
else
    echo "❌ Letzte Emotion Abruf fehlgeschlagen. Antwort: $LAST_EMO_RESPONSE"
fi


echo -e "\n========================================="
echo "  TEST ENDE"
echo "========================================="