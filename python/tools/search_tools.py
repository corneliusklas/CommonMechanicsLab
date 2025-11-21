# tools/web_tools.py
from duckduckgo_search import DDGS

def perform_web_search(query: str):
    """
    Sucht mit DuckDuckGo nach aktuellen Informationen im Internet.
    Gibt die Top-3 Suchergebnisse als Text zurück.
    """
    print(f"DEBUG: Suche im Web nach: {query}")
    try:
        results = DDGS().text(query, max_results=3)
        
        if not results:
            return "Die Internetsuche hat leider keine Ergebnisse geliefert."

        # Ergebnisse schön formatieren
        formatted_results = []
        for r in results:
            title = r.get('title', 'Ohne Titel')
            body = r.get('body', 'Keine Vorschau verfügbar.')
            href = r.get('href', '')
            formatted_results.append(f"- {title}: {body}\n  (Quelle: {href})")
        
        return "\n\n".join(formatted_results)

    except Exception as e:
        return f"Fehler bei der Internetsuche: {str(e)}"

# --- EXPORTS FÜR DEN AUTO-LOADER ---

TOOL_FUNCTIONS = {
    "perform_web_search": perform_web_search
}

def get_tool_schemas():
    return [{
        "type": "function",
        "function": {
            "name": "perform_web_search",
            "description": "Nutze dieses Tool, wenn du aktuelle Informationen benötigst, die über dein Trainingswissen hinausgehen (z.B. Nachrichten, Wetter, aktuelle Events).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "Der Suchbegriff für die Suchmaschine, z.B. 'Wetter Berlin heute' oder 'Aktueller Aktienkurs Apple'."
                    }
                },
                "required": ["query"],
            },
        },
    }]