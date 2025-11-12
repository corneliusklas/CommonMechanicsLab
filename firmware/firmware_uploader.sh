#!/bin/bash

Dieses Skript dient zum ERSTEN Flashen der ESP32-Firmware per USB

und zum Auslesen des Hostnamens über das Netzwerk.

--- Konfiguration ---

Absoluter Pfad zur Firmware-Datei

FIRMWARE_PATH="/home/robot/programs/common-mechanics-lab/firmware/common_firmware/.pio/build/az-delivery-devkit-v4/firmware.bin"

Standard-Ziel (IP oder mDNS-Name, nach dem Neustart des ESP)

DEFAULT_TARGET="esp-RoboLab.local"

Standard-Serieller Port

DEFAULT_PORT="/dev/ttyUSB0"

Basis-URL des ESP32 Webservers

BASE_URL="http://"

--- Funktionen ---

Prüfen, ob zenity installiert ist (für die grafische Oberfläche)

if ! command -v zenity &> /dev/null
then
echo "ERROR: Das 'zenity'-Tool ist nicht installiert. Bitte installieren Sie es mit 'sudo apt install zenity'."
exit 1
fi

Prüfen, ob esptool.py installiert ist

if ! command -v esptool &> /dev/null
then
zenity --error

--title="FEHLER: esptool.py fehlt"

--text="Das notwendige Tool 'esptool.py' ist nicht installiert.\n\nBitte installieren Sie es, BEVOR Sie fortfahren, mit folgendem Befehl:\n\n<b>python -m pip install esptool</b>"
exit 1
fi

--- 1. Ziel und Port abfragen ---

PORT=$(zenity --entry 

--title="ESP32 Firmware Upload (USB)" 

--text="Bitte geben Sie den seriellen Port des ESP32 an (z.B. /dev/ttyUSB0):" 

--entry-text="$DEFAULT_PORT"

--width=400)

if [ -z "$PORT" ]; then
zenity --error --text="Upload abgebrochen. Kein serieller Port angegeben."
exit 1
fi

TARGET=$(zenity --entry 

--title="ESP32 Zieladresse" 

--text="Bitte geben Sie die IP-Adresse oder den mDNS-Namen des ESP32 nach dem Neustart ein (z.B. esp-RoboLab.local):" 

--entry-text="$DEFAULT_TARGET"

--width=400)

if [ -z "$TARGET" ]; then
# Nicht kritisch, falls nur geflasht werden soll, aber wir fordern es trotzdem an.
zenity --warning --text="Keine Zieladresse für das Auslesen des Hostnamens angegeben. Das Flashen wird trotzdem durchgeführt."
fi

--- 2. Upload-Vorbereitung und Ausführung (USB Serial Flash) ---

zenity --info --text="Starte seriellen Upload auf $PORT. \n\n<b>WICHTIG:</b> Bitte stellen Sie sicher, dass sich der ESP32 im Flash-Modus befindet (i.d.R. BOOT/GPIO0 gedrückt halten, EN drücken/loslassen)." &
PID_INFO=$!

Führt den Upload mit esptool aus

Offset 0x10000 ist der Standard für PlatformIO-Binaries

/usr/bin/env python3 -m esptool --chip esp32 --port "$PORT" --baud 460800 write_flash 0x10000 "$FIRMWARE\_PATH" 2\>&1
UPLOAD\_STATUS=$?

kill $PID_INFO 2>/dev/null

if [ $UPLOAD_STATUS -ne 0 ]; then
zenity --error --text="Fehler beim Upload (esptool Status: $UPLOAD_STATUS).\nÜberprüfen Sie:\n1. Ist der Port $PORT korrekt?\n2. Ist der ESP32 im Flash-Modus?"
exit 1
fi

zenity --info --text="Firmware erfolgreich per USB geflasht. Warte auf Neustart und Netzwerkkonnektivität (10 Sekunden)..."
sleep 10 # Länger warten, um dem ESP Zeit zu geben, WLAN zu initialisieren.

--- 3. Hostname auslesen ---

if [ -n "$TARGET" ]; then
zenity --info --text="Lese Hostnamen von $TARGET aus..." &
PID_INFO=$\!
HOSTNAME\_URL="${BASE_URL}${TARGET}"

# Nutze curl, um die HTML-Seite abzurufen.
HTML_CONTENT=$(curl -s --max-time 15 "$HOSTNAME_URL")
CURL_STATUS=$?
kill $PID_INFO 2>/dev/null

if [ $CURL_STATUS -ne 0 ]; then
    zenity --warning --text="Upload war erfolgreich, aber der ESP32 war unter $TARGET nicht erreichbar.\nBitte überprüfen Sie die Adresse manuell oder starten Sie den ESP neu."
    exit 0
fi

# Extrahiert den Namen (z.B. 'esp-RoboLab') aus der Zeile: <p><strong>Name:</strong> esp-RoboLab.local</p>
EXTRACTED_NAME=$(echo "$HTML_CONTENT" | grep -oP '<strong>Name:</strong> \K[^<]+')
EXTRACTED_NAME_CLEAN=$(echo "$EXTRACTED_NAME" | sed 's/\.local$//')


if [ -z "$EXTRACTED_NAME_CLEAN" ]; then
    zenity --warning --text="Upload erfolgreich, aber der Hostname konnte nicht ausgelesen werden. Bitte manuell prüfen."
    exit 0
fi

# --- 4. Ergebnis anzeigen ---
zenity --info \
    --title="Aktion erfolgreich!" \
    --text="Die Firmware wurde erfolgreich geflasht.\nDer neue Hostname des ESP32 lautet:\n\n<b>$EXTRACTED_NAME_CLEAN</b>"


else
zenity --info

--title="Aktion erfolgreich!"

--text="Die Firmware wurde erfolgreich geflasht.\nBitte starten Sie den ESP32 neu und prüfen Sie den Hostnamen manuell über die Konsole."
fi

exit 0