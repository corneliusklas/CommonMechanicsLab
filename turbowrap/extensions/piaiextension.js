class PiAiExtension {
    constructor() {
        // Die Basis-URL (Origin) wird automatisch aus der Adresse ermittelt, 
        // von der die Scratch-Umgebung geladen wurde (z.B. http://192.168.50.1:5000).
        // Dies eliminiert CORS-Probleme, wenn die API auf dem gleichen Port läuft.
        this._serverOrigin = window.location.origin; 

        console.log(`Pi AI Server API is running on same origin: ${this._serverOrigin}/api/`);
    }

    /**
     * Beschreibt die Blöcke, Kategorien und Blocktypen für die Scratch-Erweiterung.
     */
    getInfo() {
        return {
            id: 'piai', 
            name: 'Pi AI Control (Same-Origin)', 
            color1: '#00B295', // Teal
            color2: '#00846C',
            blocks: [
                // --- Audio / Listening ---
                {
                    opcode: 'startRecording',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'start audio recording',
                },
                {
                    opcode: 'stopTranscribe',
                    blockType: Scratch.BlockType.REPORTER,
                    text: 'stop recording and transcribe (Language: [LANG])',
                    arguments: {
                        LANG: { 
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: 'en'
                        }
                    }
                },
                // --- LLM / Thinking ---
                {
                    opcode: 'askLLM',
                    blockType: Scratch.BlockType.REPORTER,
                    text: 'ask LLM with prompt [PROMPT]',
                    arguments: {
                        PROMPT: { 
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: 'Who am I?'
                        }
                    }
                },
                // --- LLM History and Persona ---
                {
                    opcode: 'setSystemMsg',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'set PiBot Persona to [MESSAGE]',
                    arguments: {
                        MESSAGE: { 
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: 'You are a friendly robot.'
                        }
                    }
                },
                {
                    opcode: 'clearHistory',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'clear conversation history'
                },
                {
                    opcode: 'getHistory',
                    blockType: Scratch.BlockType.REPORTER,
                    text: 'Get History (JSON)'
                },
                {
                    opcode: 'setHistory',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Set History (JSON String: [JSON_STRING])',
                    arguments: {
                        JSON_STRING: { 
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: '[{"role":"user","content":"Hello!"}]'
                        }
                    }
                },
                // --- TTS / Speaking ---
                {
                    opcode: 'speakText',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'speak [TEXT] with mode [MODE]',
                    arguments: {
                        TEXT: { 
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: 'Hello, I am PiBot.'
                        },
                        MODE: { 
                            type: Scratch.ArgumentType.STRING,
                            menu: 'tts_modes',
                            defaultValue: 'espeak'
                        }
                    }
                },
            ],
            menus: {
                tts_modes: {
                    acceptsReporters: true,
                    items: ['espeak', 'openai']
                }
            }
        };
    }

    // =========================================================================
    // --- UTILITY FUNCTION ---
    // =========================================================================

    /**
     * Führt eine asynchrone POST-Anfrage aus.
     * @param {string} endpoint - Der API-Endpunkt (z. B. 'ask_llm').
     * @param {object} payload - Die zu sendenden JSON-Daten.
     * @returns {Promise<any>} Die JSON-Antwort vom Server oder eine Fehlerzeichenkette.
     */
    async fetchPost(endpoint, payload, isMultipart = false) {
        // Die URL nutzt nun den Origin der Scratch-Seite und den API-Pfad /api/
        const url = `${this._serverOrigin}/api/${endpoint}`;
        
        try {
            const options = {
                method: 'POST',
                // Header nur für JSON hinzufügen, nicht für FormData
                headers: isMultipart ? {} : { 'Content-Type': 'application/json' },
                body: isMultipart ? payload : JSON.stringify(payload)
            };
            
            const response = await fetch(url, options);
            const data = await response.json();

            if (!response.ok) {
                console.error(`API Error at ${url}:`, data);
                return `ERROR: ${data.error || data.status || 'Unknown'}`;
            }

            return data;

        } catch (error) {
            console.error(`Network error at ${url}:`, error);
            return `NETWORK ERROR: Konnte API auf ${this._serverOrigin} nicht erreichen.`;
        }
    }
    
    // =========================================================================
    // --- BLOCK IMPLEMENTATIONS ---
    // =========================================================================

    // --- Audio / Listening ---

    startRecording() {
        return this.fetchPost('start_record', {});
    }

    stopTranscribe(args) {
        const formData = new FormData();
        formData.append('lang', args.LANG); 

        return new Promise(async (resolve) => {
            const data = await this.fetchPost('stop_transcribe', formData, true);
            resolve(data.text || data);
        });
    }

    // --- LLM / Thinking ---

    askLLM(args) {
        const payload = { prompt: args.PROMPT }; 
        
        return new Promise(async (resolve) => {
            const data = await this.fetchPost('ask_llm', payload);
            resolve(data.response || data);
        });
    }
    
    // --- LLM History and Persona ---

    setSystemMsg(args) {
        const payload = { system_message: args.MESSAGE }; 
        return this.fetchPost('llm_system_message', payload);
    }

    clearHistory() {
        return this.fetchPost('llm_history_clear', {});
    }

    getHistory() {
        return new Promise(async (resolve) => {
            try {
                const url = `${this._serverOrigin}/api/llm_history`;
                const response = await fetch(url);
                const data = await response.json();

                if (!response.ok) {
                    console.error("Error retrieving history:", data);
                    resolve(`ERROR: ${data.error || 'Unknown'}`);
                    return;
                }

                resolve(JSON.stringify(data.history));

            } catch (error) {
                console.error("Network error retrieving history:", error);
                resolve(`NETWORK ERROR: ${error.message}`);
            }
        });
    }

    setHistory(args) {
        return new Promise(async (resolve) => {
            let historyObject;
            try {
                historyObject = JSON.parse(args.JSON_STRING); 
            } catch (e) {
                console.error("Invalid JSON string for history:", e);
                resolve('ERROR: Invalid JSON String');
                return;
            }

            const payload = { history: historyObject };
            const data = await this.fetchPost('llm_history', payload);
            
            resolve(data.status || data);
        });
    }


    // --- TTS / Speaking ---

    speakText(args) {
        const payload = { 
            text: args.TEXT, 
            mode: args.MODE 
        };
        return this.fetchPost('tts_speak', payload);
    }
}

Scratch.extensions.register(new PiAiExtension());