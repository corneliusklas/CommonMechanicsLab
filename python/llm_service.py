import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- GLOBAL STATE for Conversation History ---
# The conversation history stores the system message and all user/assistant turns.
DEFAULT_SYSTEM_MESSAGE = "Du bist ein freundlicher, hilfreicher Roboter mit einer leicht humorvollen Note. Antworte kurz und präzise auf Fragen. Dein Name ist PiBot."
current_system_message = DEFAULT_SYSTEM_MESSAGE
conversation_history = [] # Stores messages in OpenAI format: [{"role": "user", "content": "..."}]

def initialize_history():
    """Initializes the history with the current system message."""
    global conversation_history, current_system_message
    conversation_history = [{"role": "system", "content": current_system_message}]
    
def set_system_message(new_message):
    """Sets a new system message and re-initializes the history."""
    global current_system_message
    current_system_message = new_message
    initialize_history()
    print(f"System message updated and history cleared. New message: {new_message}")

def clear_history():
    """Clears the entire conversation history."""
    initialize_history()
    print("Conversation history cleared.")

def get_history():
    """Returns the current conversation history (excluding the system message)."""
    # Exclude the first element, which is the system message
    return conversation_history[1:] if len(conversation_history) > 0 else []

def set_history(new_history):
    """
    Replaces the conversation history (turns only), preserving the system message.

    Args:
        new_history (list): A list of message objects [{"role": "user/assistant", "content": "..."}].
    
    Returns:
        int: The number of turns successfully added.
    """
    global conversation_history
    
    # 1. Start with the current system message
    history_with_system = [{"role": "system", "content": current_system_message}]
    
    # 2. Validate and append new history
    valid_roles = ["user", "assistant"]
    turns_added = 0
    for message in new_history:
        role = message.get("role")
        content = message.get("content")
        
        # Simple validation: required fields and valid role
        if role in valid_roles and content:
            history_with_system.append({"role": role, "content": content})
            turns_added += 1
        else:
            print(f"⚠️ Warning: Invalid history entry skipped: {message}")
            
        
    conversation_history = history_with_system
    print(f"Conversation history replaced. Total turns (excluding system): {turns_added}")
    return turns_added


def generate_response(prompt):
    """
    Generates a text response using the OpenAI Chat Completion API (GPT-3.5-turbo).
    It manages the conversation history automatically.
    
    Args:
        prompt (str): The user's transcribed text.

    Returns:
        str: The generated response text, or an error message.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY not set."

    if not conversation_history or conversation_history[0].get("role") != "system":
        initialize_history()

    # 1. Append user prompt to history
    user_message = {"role": "user", "content": prompt}
    conversation_history.append(user_message)
        
    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": conversation_history, # Send the full history
        "temperature": 0.7,
        "max_tokens": 150 
    }
    
    try:
        print(f"-> Sending full history (length: {len(conversation_history)}) to LLM. New prompt: '{prompt}'")
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        
        if response.status_code != 200:
            error_details = response.json().get('error', {}).get('message', 'Unknown API Error')
            # If API fails, remove the last user message to keep state clean
            if conversation_history[-1] == user_message:
                 conversation_history.pop()
            return f"Error communicating with OpenAI: {error_details}"

        j = response.json()
        
        # 2. Extract and append assistant response to history
        assistant_response = j['choices'][0]['message']['content'].strip()
        assistant_message = {"role": "assistant", "content": assistant_response}
        conversation_history.append(assistant_message)
        
        return assistant_response

    except Exception as e:
        # If any other exception occurs, also remove the last user message
        if conversation_history[-1] == user_message:
             conversation_history.pop()
        return f"An unexpected error occurred during LLM call: {e}"

# Call init upon module import
initialize_history()

if __name__ == "__main__":
    print("\n--- LLM Service Self-Test (Thinking with History) ---")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ TEST FEHLGESCHLAGEN: OPENAI_API_KEY ist nicht gesetzt. LLM-Test übersprungen.")
    else:
        # Test 1: Initial prompt
        test_prompt_1 = "Mein Name ist Alex und ich bin 10 Jahre alt."
        set_system_message("Du bist ein Kinderfreund und gibst leicht verständliche Antworten.")
        
        print(f"1. Sende Initial-Prompt: '{test_prompt_1}'")
        response_1 = generate_response(test_prompt_1)
        
        if response_1.startswith("Error:"):
            print(f"\n❌ TEST FEHLGESCHLAGEN (1): {response_1}")
        else:
            print(f"🤖 PiBot-Antwort (1): {response_1}")

            # Test 2: Follow-up prompt relying on history
            test_prompt_2 = "Wie alt bin ich?"
            print(f"\n2. Sende Folge-Prompt: '{test_prompt_2}'")
            response_2 = generate_response(test_prompt_2)

            if response_2.startswith("Error:"):
                print(f"\n❌ TEST FEHLGESCHLAGEN (2): {response_2}")
            else:
                print(f"🤖 PiBot-Antwort (2): {response_2}")
                print("\n✅ TEST ERFOLGREICH: Die Antwort sollte sich auf '10 Jahre' beziehen.")
            
    print("\n--- Test abgeschlossen ---")