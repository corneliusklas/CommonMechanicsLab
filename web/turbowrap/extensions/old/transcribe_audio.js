class WhisperTranscribeExtension {
    constructor(runtime) {
        this.runtime = runtime;
        // Passe die URL deines Flask-Servers an
        this.serverUrl = "http://192.168.4.1:5001/api/transcribe"; 
        this.mediaRecorder = null;
        this.audioChunks = [];
    }

    getInfo() {
        return {
            id: 'whisperTranscribe',
            name: '🎙️ Whisper Speech-to-Text',
            color1: '#007acc',
            color2: '#005f99',
            blocks: [
                {
                    opcode: 'startRecording',
                    blockType: Scratch.BlockType.COMMAND,
                    text: '🎤 Aufnahme starten'
                },
                {
                    opcode: 'stopAndTranscribe',
                    blockType: Scratch.BlockType.REPORTER,
                    text: '🧠 Aufnahme stoppen und transkribieren (Sprache: [LANG])',
                    arguments: {
                        LANG: {
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: '' // Leerer String bedeutet Auto-Erkennung durch Whisper
                        }
                    }
                }
            ]
        };
    }

    async startRecording() {
        try {
            // Stream mit Audio-Constraint anfordern
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioChunks = [];
            
            // Verwende WebM/Opus, da es gut mit Browsern und Whisper funktioniert
            const mimeType = 'audio/webm; codecs=opus';
            const options = MediaRecorder.isTypeSupported(mimeType) ? { mimeType } : {};

            this.mediaRecorder = new MediaRecorder(stream, options);
            this.mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) {
                    this.audioChunks.push(e.data);
                }
            };
            this.mediaRecorder.start();
            console.log("🎙️ Aufnahme gestartet mit Typ:", this.mediaRecorder.mimeType);
        } catch (err) {
            console.error("Fehler beim Starten der Aufnahme:", err);
            // Nutze Scratch.vm.runtime.requestHalt() oder sende eine Meldung an das Projekt
            alert("Kein Mikrofonzugriff erlaubt oder Fehler beim Start!");
        }
    }

    async stopAndTranscribe(args) {
        return new Promise((resolve) => {
            if (!this.mediaRecorder) {
                console.warn("Keine laufende Aufnahme.");
                resolve(""); // Gibt leeren String an Scratch zurück
                return;
            }

            // Speichert den Stream für späteres Stoppen der Tracks
            const streamToStop = this.mediaRecorder.stream;

            this.mediaRecorder.onstop = async () => {
                // Alle Tracks stoppen, um das Mikrofon zu deaktivieren
                if (streamToStop) {
                    streamToStop.getTracks().forEach(track => track.stop());
                }

                if (this.audioChunks.length === 0) {
                    console.warn("Keine Audiodaten aufgenommen.");
                    resolve("");
                    return;
                }

                // Erstellt Blob basierend auf dem tatsächlich verwendeten MIME-Type
                const blob = new Blob(this.audioChunks, { type: this.mediaRecorder.mimeType });
                const formData = new FormData();
                formData.append('audio', blob, 'recording.' + (this.mediaRecorder.mimeType.includes('webm') ? 'webm' : 'bin'));

                // Füge optionalen Sprachparameter hinzu
                const lang = args.LANG.trim();
                if (lang) {
                    formData.append('lang', lang);
                    console.log(`Verwende Spracheinstellung: ${lang}`);
                }

                try {
                    const response = await fetch(this.serverUrl, {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const text = await response.text();
                        console.error(`Fehler vom Transkriptions-Server (${response.status}): ${text}`);
                        resolve(""); // Fehler -> Leerer String
                        return;
                    }

                    const result = await response.json();
                    resolve(result.text || "");
                } catch (err) {
                    console.error("Transkriptionsfehler (Netzwerk/Server nicht erreichbar):", err);
                    resolve(""); // Fehler -> Leerer String
                }
            };

            // Stoppt die Aufnahme und triggert den 'onstop'-Handler
            this.mediaRecorder.stop();
            console.log("🛑 Aufnahme gestoppt, sende an Whisper...");
        });
    }
}

// Registrieren der Extension in TurboWarp/Scratch
Scratch.extensions.register(new WhisperTranscribeExtension());