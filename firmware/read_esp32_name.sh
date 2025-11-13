#!/bin/bash

# Dieses Skript liest die serielle Ausgabe des ESP32 für 8 Sekunden aus,
# um den erfolgreichen Start der Anwendung und den Hostnamen zu überprüfen.
# Es verwendet stty und cat für eine einfache, automatische Ausführung.

# --- Konfiguration ---
# Standard-Baudrate für ESP32-Konsolenausgabe
BAUDRATE="115200"

# --- Funktionen ---

log() {
    echo "$(date '+%H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%H:%M:%S') [FEHLER] $1" >&2
}

find_serial_port() {
    local port=""
    # Suche nach ttyUSB* (häufig CP210x, CH340)
    port=$(ls /dev/ttyUSB* 2>/dev/null | head -n 1)
    if [ -z "$port" ]; then
        # Suche nach ttyACM* (häufig CDC ACM)
        port=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)
    fi
    echo "$port"
}

# --- Hauptlogik ---

SERIAL_PORT=$(find_serial_port)

if [ -z "$SERIAL_PORT" ]; then
    log_error "Kein geeignetes serielles Gerät für ESP32 gefunden."
    log "Bitte stellen Sie sicher, dass das ESP32-Board angeschlossen ist."
    exit 1
fi

log "Gefundenes ESP32-Gerät: $SERIAL_PORT"
log "Lese serielle Daten mit $BAUDRATE Baud..."

# NEUE WICHTIGE ANWEISUNG
log "WICHTIG: Wenn keine Ausgabe erscheint, drücken Sie bitte kurz die 'EN' (Enable/Reset) Taste auf dem ESP32-Board, um den Neustart auszulösen."

# 1. Terminal-Einstellungen setzen (wichtig für die korrekte Lesung)
# cstopb: 1 Stoppbit, -parenb: keine Parität, raw: Rohdatenmodus
stty -F "$SERIAL_PORT" $BAUDRATE raw -clocal -echo

# 2. Daten mit Timeout ausgeben
# Die Wartezeit von 8 Sekunden gibt dem ESP32 genug Zeit, um den Bootloader
# abzuschließen und die Anwendung zu starten (inkl. Hostname-Ausgabe).
timeout 8 cat "$SERIAL_PORT"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    log "Timeout erreicht. Serielle Ausgabe abgeschlossen."
elif [ $EXIT_CODE -ne 0 ]; then
    log_error "Fehler beim Lesen der seriellen Schnittstelle."
fi

log "--- Ende der seriellen Ausgabe ---"

# Hinweis für interaktives Debugging
log "Tipp: Für interaktives Debugging verwenden Sie 'picocom -b $BAUDRATE $SERIAL_PORT'."

# WICHTIG: Die Terminal-Einstellungen zurücksetzen (wieder auf standard)
stty -F "$SERIAL_PORT" sane

log "Skript-Ausführung abgeschlossen."