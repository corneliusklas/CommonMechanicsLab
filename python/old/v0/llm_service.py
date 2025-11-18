import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def generate_response(prompt, system_message="Du bist ein freundlicher, hilfreicher Roboter mit einer leicht humorvollen Note. Antworte kurz und präzise auf Fragen. Dein Name ist PiBot."):
    """
    Generates a text response using the OpenAI Chat Completion API (GPT-3.5-turbo).
    
    Args:
        prompt (str): The user's transcribed text.
        system_message (str): Instruction for the LLM's persona.

    Returns:
        str: The generated response text, or an error message.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY not set."
        
    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 150 
    }
    
    try:
        print(f"-> Sending prompt to LLM: '{prompt}'")
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        
        if response.status_code != 200:
            error_details = response.json().get('error', {}).get('message', 'Unknown API Error')
            return f"Error communicating with OpenAI: {error_details}"

        j = response.json()
        # Extract the content from the first choice
        return j['choices'][0]['message']['content'].strip()

    except Exception as e:
        return f"An unexpected error occurred during LLM call: {e}"

if __name__ == "__main__":
    print("\n--- LLM Service Self-Test (Thinking) ---")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ TEST FEHLGESCHLAGEN: OPENAI_API_KEY ist nicht gesetzt. LLM-Test übersprungen.")
    else:
        test_prompt = "Was ist die Hauptstadt von Frankreich?"
        print(f"1. Sende Test-Prompt: '{test_prompt}'")
        
        response = generate_response(test_prompt)
        
        if response.startswith("Error:"):
            print(f"\n❌ TEST FEHLGESCHLAGEN: {response}")
        else:
            print("\n✅ TEST ERFOLGREICH.")
            print(f"🤖 PiBot-Antwort: {response}")
            
    print("\n--- Test abgeschlossen ---")