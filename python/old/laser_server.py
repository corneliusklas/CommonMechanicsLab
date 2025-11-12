import asyncio
import serial
import serial.threaded
import websockets

SERIAL_PORT = "COM4"      # <- anpassen!
BAUDRATE = 460800

ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)

async def handler(websocket):
    print("🔌 Verbunden mit Turbowarp")
    async for message in websocket:
        msg = message.strip()
        if not msg:
            continue
        print(f"➡️  Sende: {msg}")
        ser.write((msg + "\n").encode("ascii"))
    print("❌ Verbindung getrennt")

async def main():
    async with websockets.serve(handler, "localhost", 8765):
        print("🌐 WebSocket-Server läuft auf ws://localhost:8765")
        await asyncio.Future()  # läuft für immer

if __name__ == "__main__":
    asyncio.run(main())
