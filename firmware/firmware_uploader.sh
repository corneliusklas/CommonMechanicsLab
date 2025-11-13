#!/bin/bash

# Dieses Skript flasht die ESP32-Firmware mit stabilen Parametern,
# um bekannte Probleme mit empfindlichen ESP-WROOM-32 Boards unter Linux/Raspberry Pi zu umgehen.

cd /home/robot/programs/common-mechanics-lab/firmware
source venv/bin/activate

# --- Konfiguration ---
# Basispfad zum PlatformIO-Build-Verzeichnis
BASE_PATH="/home/robot/programs/common-mechanics-lab/firmware/common_firmware/.pio/build/az-delivery-devkit-v4"

# Stabilisierte Parameter
CHIP_TYPE="esp32"
# Wichtig: Reduzierte Baudrate für USB-Stabilität auf dem Raspberry Pi
BAUDRATE="460800" 
TOOL_COMMAND="/usr/bin/env python3 -m esptool"

# --- Funktionen ---

log() {
    echo "$(date '+%H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%H:%M:%S') [ERROR] $1" >&2
}

find_serial_port() {
    local port=""
    port=$(ls /dev/ttyUSB* 2>/dev/null | head -n 1)
    if [ -z "$port" ]; then
        port=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)
    fi
    echo "$port"
}

# --- Hauptlogik ---

# 1. Validierung der Umgebung und Dateien
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 ist nicht installiert. Wird für esptool.py benötigt."
    exit 1
fi

if [ ! -f "$BASE_PATH/firmware.bin" ] || [ ! -f "$BASE_PATH/bootloader.bin" ] || [ ! -f "$BASE_PATH/partitions.bin" ]; then
    log_error "Eine oder mehrere notwendige ESP32 Firmware-Dateien wurden nicht gefunden."
    log_error "Bitte stellen Sie sicher, dass das PlatformIO-Projekt kompiliert wurde und der Pfad korrekt ist: $BASE_PATH"
    exit 1
fi

SERIAL_PORT=$(find_serial_port)

if [ -z "$SERIAL_PORT" ]; then
    log_error "Kein geeignetes serielles Gerät für ESP32 gefunden."
    log "Bitte stellen Sie sicher, dass das ESP32-Board angeschlossen ist."
    exit 1
fi

log "Gefundenes ESP32-Gerät: $SERIAL_PORT"
log "Starte stabilisierten ESP32 Firmware-Upload auf $SERIAL_PORT mit $BAUDRATE Baud..."

# 2. Setzen der Umgebungsvariablen (um Syntaxfehler in Python zu vermeiden)
# Dies stellt die korrekte Flash-Frequenz und den Modus sicher (Fix für Anwendungsabsturz)
export ESPTOOL_FLASH_FREQ=40m
export ESPTOOL_FLASH_MODE=dio

# 3. Multi-File-Flash-Befehl
# Flasht Bootloader, Partitionstabelle und Anwendung an den korrekten Adressen.
# --before / --after: Fix für den Absturz beim Reset des empfindlichen Boards B.
$TOOL_COMMAND --chip $CHIP_TYPE --port $SERIAL_PORT --baud $BAUDRATE \
    --before default-reset --after hard-reset \
    write-flash \
    0x1000 "$BASE_PATH/bootloader.bin" \
    0x8000 "$BASE_PATH/partitions.bin" \
    0x10000 "$BASE_PATH/firmware.bin"

EXIT_CODE=$?

# 4. Variablen und Ergebnis bereinigen
unset ESPTOOL_FLASH_FREQ
unset ESPTOOL_FLASH_MODE

if [ $EXIT_CODE -eq 0 ]; then
    log "ESP32 Upload erfolgreich abgeschlossen."
else
    log_error "ESP32 Upload fehlgeschlagen. Fehlercode: $EXIT_CODE"
fi

log "Skript-Ausführung abgeschlossen."