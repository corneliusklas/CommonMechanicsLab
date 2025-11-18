import serial
import threading

PORT = "COM4"      # Anpassen!
BAUDRATE = 460800

def read_from_laser(ser):
    """Liest ständig vom Laser"""
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if line:
            print(f"< {line}")

with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
    print(f"✅ Verbunden mit {PORT} @ {BAUDRATE}")
    
    # Thread zum Lesen starten
    threading.Thread(target=read_from_laser, args=(ser,), daemon=True).start()
    
    print("💬 Eingabe aktiv. Tippe Befehle (z. B. $H oder $$) und drücke Enter.")
    while True:
        cmd = input("> ")
        if cmd.lower() in {"exit", "quit"}:
            break
        ser.write((cmd + "\n").encode("ascii"))
