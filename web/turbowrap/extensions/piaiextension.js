// piaiextension.js
// -------------------------------------------------------------------------------------------------
// PiBot AI Extension für TurboWarp/Scratch 3.0
//
// ZIEL: Ermöglicht die Kommunikation zwischen Scratch und einem lokalen Python/Flask-Server (PiBot).
//
// FUNKTIONALITÄT:
// 1. LLM-Kommunikation: 'ask LLM' sendet Prompt an den Server und gibt NUR die Textantwort zurück.
// 2. TTS-Steuerung: 'speak' sendet Text, Modus (openai, espeak, gtts) und Sprache (lang) an den Server.
// 3. Audioaufnahme: Startet/Stoppt die Aufnahme und transkribiert diese.
// 4. Status/Konfiguration: Blöcke zur Steuerung der Systemnachricht, des LLM-Verlaufs und der Emotionen.
//
// NETZWERK-KONFIGURATION:
// - Die Variable 'DEFAULT_SERVER_ORIGIN' nutzt 'window.location.origin', um die IP-Adresse und 
//   den Port der aktuell geladenen Seite zu übernehmen. Dies gewährleistet eine stabile Verbindung
//   unabhängig davon, ob der Zugriff über 127.0.0.1:5000 oder 192.168.50.1 erfolgt.
// -------------------------------------------------------------------------------------------------

(function(Scratch) {
    'use strict';

    // Bestimme die Basis-URL für den lokalen Server (z.B. http://192.168.50.1 oder http://127.0.0.1:5000)
    const DEFAULT_SERVER_ORIGIN = window.location.origin;

    class PiAiExtension {
        constructor(runtime) {
            this.runtime = runtime;
            this._serverOrigin = DEFAULT_SERVER_ORIGIN;
            console.log(`PiAiExtension initialized. Server target: ${this._serverOrigin}`);
        }

        getInfo() {
            return {
                id: 'piai',
                name: 'PiBot AI',
                color1: '#00707c',
                color2: '#005f6b',
                blocks: [
                    {
                        opcode: 'askLLM',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'ask LLM [PROMPT]',
                        arguments: {
                            PROMPT: {
                                type: Scratch.ArgumentType.STRING,
                                defaultValue: 'What is your name?'
                            }
                        }
                    },
                    '---',
                    // --- TTS / AUDIO ---
                    {
                        opcode: 'speak',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'speak [TEXT] using [MODE] in language [LANG]',
                        arguments: {
                            TEXT: {
                                type: Scratch.ArgumentType.STRING,
                                defaultValue: 'Hallo, ich bin PiBot.'
                            },
                            MODE: {
                                type: Scratch.ArgumentType.STRING,
                                menu: 'TTS_MODE',
                                defaultValue: 'gtts'
                            },
                            LANG: {
                                type: Scratch.ArgumentType.STRING,
                                menu: 'LANGUAGES',
                                defaultValue: 'de'
                            }
                        }
                    },
                    {
                        opcode: 'startRecord',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'start recording audio',
                    },
                    {
                        opcode: 'stopTranscribe',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'stop recording and transcribe audio in [LANG]',
                        arguments: {
                            LANG: {
                                type: Scratch.ArgumentType.STRING,
                                menu: 'LANGUAGES',
                                defaultValue: 'de'
                            }
                        }
                    },
                    {
                        opcode: 'isTalking',
                        blockType: Scratch.BlockType.BOOLEAN, 
                        text: 'is PiBot talking?',
                    },
                    '---',
                    // --- LLM CONFIG / HISTORY ---
                    {
                        opcode: 'setSystemMessage',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'set system message [MESSAGE]',
                        arguments: {
                            MESSAGE: {
                                type: Scratch.ArgumentType.STRING,
                                defaultValue: 'You are a helpful robot.'
                            }
                        }
                    },

                    {
                        opcode: 'clearHistory',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'clear conversation history',
                    },
                    {
                        opcode: 'getHistory',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'get history',
                    },
                    {
                        opcode: 'setHistory',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'set history to [HISTORY_JSON]',
                        arguments: {
                            HISTORY_JSON: {
                                type: Scratch.ArgumentType.STRING,
                                defaultValue: '[]' // Standardmäßig leeres JSON-Array
                            }
                        }
                    },
                    

                    {
                        opcode: 'getLastEmotion',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'get last recognized emotion',
                    },
                    {
                        opcode: 'setAllowedEmotions',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'allow LLM to use emotions: [EMOTION_LIST]',
                        arguments: {
                            EMOTION_LIST: {
                                type: Scratch.ArgumentType.STRING,
                                defaultValue: 'happy, sad, neutral' 
                            }
                        }
                    },
                    {
                        opcode: 'getAllowedEmotions',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'get allowed emotion list',
                    },

                ],
                menus: {
                    TTS_MODE: {
                        acceptReporters: true,
                        items: ['openai', 'gtts', 'espeak']
                    },
                    LANGUAGES: { 
                        acceptReporters: true,
                        items: ['de', 'en', 'fr', 'es']
                    }
                }
            };
        }

        // =========================================================================
        // --- UTILITY FETCH FUNCTIONS ---
        // =========================================================================

        async fetchPost(endpoint, payload = {}) {
            // Fügt /api/ an den Origin (z.B. http://192.168.50.1/api/...)
            const url = `${this._serverOrigin}/api/${endpoint}`;
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (!response.ok) {
                    console.error(`API Error at ${url}:`, data);
                    return { error: data.error || data.status || 'Unknown Error' };
                }
                return data;
            } catch (error) {
                console.error(`Network error at ${url}:`, error);
                return { error: 'NETWORK ERROR' };
            }
        }

        async fetchGet(endpoint) {
            const url = `${this._serverOrigin}/api/${endpoint}`;
            try {
                const response = await fetch(url);
                const data = await response.json();
                if (!response.ok) {
                    console.error(`API Error at ${url}:`, data);
                    return { error: data.error || data.status || 'Unknown Error' };
                }
                return data;
            } catch (error) {
                console.error(`Network error at ${url}:`, error);
                return { error: 'NETWORK ERROR' };
            }
        }

        // =========================================================================
        // --- BLOCK IMPLEMENTATIONS ---
        // =========================================================================

        // --- LLM ---

        askLLM(args) {
            const prompt = Scratch.Cast.toString(args.PROMPT);
            return new Promise(async (resolve) => {
                const data = await this.fetchPost('ask_llm', { prompt: prompt });
                
                if (data.error) {
                    resolve(`ERROR: ${data.error}`);
                    return;
                }

                // WICHTIG: Kein automatischer this.speak() Aufruf. Gibt NUR die Textantwort zurück.
                resolve(data.response || '');
            });
        }

        setSystemMessage(args) {
            const message = Scratch.Cast.toString(args.MESSAGE);
            return this.fetchPost('llm_system_message', { system_message: message });
        }

        clearHistory() {
            return this.fetchPost('llm_history_clear');
        }

        getHistory() {
            return new Promise(async (resolve) => {
                // Ruft den Endpunkt /api/llm_history als GET-Anfrage auf
                const data = await this.fetchGet('llm_history'); 
                
                if (data.error) {
                    resolve(`ERROR: ${data.error}`);
                    return;
                }
                
                // Der Server gibt { "history": [...] } zurück
                resolve(JSON.stringify(data.history || []));
            });
        }

        setHistory(args) {
            const historyJson = Scratch.Cast.toString(args.HISTORY_JSON);
            let historyArray;

            try {
                historyArray = JSON.parse(historyJson);
                if (!Array.isArray(historyArray)) {
                    throw new Error("Input is not a valid JSON array.");
                }
            } catch (e) {
                console.error("Invalid JSON format for history:", e);
                return `ERROR: Invalid JSON history format: ${e.message}`;
            }

            // Ruft den Endpunkt /api/llm_history als POST-Anfrage auf
            // Sendet { "history": [...] }
            return this.fetchPost('llm_history', { history: historyArray });
        }
        

        // --- TTS ---

        speak(args) {
            const text = Scratch.Cast.toString(args.TEXT);
            const mode = Scratch.Cast.toString(args.MODE);
            const lang = Scratch.Cast.toString(args.LANG);
            
            const payload = { 
                text: text, 
                mode: mode, 
                lang: lang 
            };
            
            // Wenn der Modus 'openai' ist, muss der Server eine Standardstimme zuordnen,
            // da die Stimme nicht mehr im Block ausgewählt wird. Wir senden einen Default-Wert mit.
            if (mode === 'openai') {
                 payload.voice = 'fable'; 
            }
            
            return this.fetchPost('tts_speak', payload);
        }

        startRecord() {
            return this.fetchPost('start_record');
        }

        stopTranscribe(args) {
            const lang = Scratch.Cast.toString(args.LANG);
            return new Promise(async (resolve) => {
                const data = await this.fetchPost('stop_transcribe', { lang: lang });
                resolve(data.text || `ERROR: ${data.error || 'Transcription failed.'}`);
            });
        }

        // --- BLÖCKE FÜR EMOTION/STATUS ---

        getLastEmotion() {
            return new Promise(async (resolve) => {
                const data = await this.fetchGet('get_emotion');
                resolve(data.emotion || 'neutral');
            });
        }
        
        isTalking() {
            return new Promise(async (resolve) => {
                const data = await this.fetchGet('is_talking');
                resolve(!!data.is_talking); 
            });
        }

        setAllowedEmotions(args) {
            const emotionString = Scratch.Cast.toString(args.EMOTION_LIST).trim();
            if (!emotionString) {
                console.warn("Emotion list is empty. Skipping update.");
                return Promise.resolve();
            }
            
            const emotionsArray = emotionString.split(',').map(e => e.trim()).filter(e => e.length > 0);
            
            const payload = { emotions: emotionsArray };
            return this.fetchPost('set_allowed_emotions', payload);
        }

        getAllowedEmotions() {
            return new Promise(async (resolve) => {
                const data = await this.fetchGet('get_allowed_emotions');
                if (data.emotions && Array.isArray(data.emotions)) {
                    resolve(data.emotions.join(', ')); 
                } else {
                    resolve('Error or empty list');
                }
            });
        }

    }

    Scratch.extensions.register(new PiAiExtension());
})(Scratch);