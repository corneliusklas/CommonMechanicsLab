#!/bin/bash

# --- Configuration ---
BAUDRATE="115200"
SERIAL_PORT="/dev/ttyUSB0"

# --- Main Logic ---

echo ""
echo "================================================================"
echo "⚠️ HINT: Please restart the ESP32 NOW using the EN button."
echo "================================================================"
echo ""

# Start picocom
picocom -b "$BAUDRATE" "$SERIAL_PORT"

# Message after picocom exits (after pressing Ctrl+A, Ctrl+X)
echo ""
echo "Picocom terminated. Press Enter to close the terminal."
read