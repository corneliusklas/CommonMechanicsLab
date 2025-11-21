import datetime
import pytz

def get_current_time(timezone="Europe/Berlin"):
    """
    Gibt die aktuelle Uhrzeit für die angegebene Zeitzone als String zurück.
    """
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.datetime.now(tz).strftime("%H:%M:%S")
        return f"Die aktuelle Uhrzeit in {timezone} ist {current_time}."
    except Exception:
        return "Fehler beim Abrufen der Uhrzeit."

def get_current_date(timezone="Europe/Berlin"):
    """
    Gibt das aktuelle Datum (mit Wochentag) zurück.
    """
    try:
        tz = pytz.timezone(timezone)
        # Formatbeispiel: 2023-10-27 (Friday)
        current_date = datetime.datetime.now(tz).strftime("%Y-%m-%d (%A)")
        return f"Das aktuelle Datum in {timezone} ist {current_date}."
    except Exception:
        return "Fehler beim Abrufen des Datums."

# --- EXPORTS FÜR DEN AUTO-LOADER ---

# Mapping: Funktionsname -> Python Funktion
TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "get_current_date": get_current_date  # <-- NEU HINZUGEFÜGT
}

# Funktion, die die Schemas zurückgibt
def get_tool_schemas():
    return [
        # Schema für Zeit
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Gibt die aktuelle Uhrzeit für die angegebene Zeitzone zurück.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "description": "Die Zeitzone, z.B. 'Europe/Berlin'."}
                    },
                    "required": [],
                },
            },
        },
        # Schema für Datum (NEU)
        {
            "type": "function",
            "function": {
                "name": "get_current_date",
                "description": "Gibt das aktuelle Datum (Jahr, Monat, Tag, Wochentag) zurück.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "description": "Die Zeitzone, z.B. 'Europe/Berlin'."}
                    },
                    "required": [],
                },
            },
        }
    ]