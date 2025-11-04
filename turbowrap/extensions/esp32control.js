class ESP32_WS {
    constructor(runtime) {
        this.runtime = runtime;
        this.ws = null;
        this.sensorValues = {};
        this.lastMessage = "";
    }

    getInfo() {
        return {
            id: 'esp32ws',
            name: 'ESP32 Steuerung',
            blocks: [
                {
                    opcode: 'connectWebSocket',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Verbinde mit ESP32 IP: [IP]',
                    arguments: {
                        IP: {
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: '192.168.4.1'
                        }
                    }
                },
                {
                    opcode: 'ledSet',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Setze LED [NUM] auf [STATE]',
                    arguments: {
                        NUM: {
                            type: Scratch.ArgumentType.MENU,
                            menu: 'ledMenu'
                        },
                        STATE: {
                            type: Scratch.ArgumentType.MENU,
                            menu: 'onOffMenu'
                        }
                    }
                },
                {
                    opcode: 'setServoFilter',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Setze Servo-Filter auf [FILTER]',
                    arguments: {
                        FILTER: {
                            type: Scratch.ArgumentType.NUMBER,
                            defaultValue: 0.9
                        }
                    }
                },
                {
                    opcode: 'servoSet',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Setze Servo [NUM] auf [ANGLE] Grad',
                    arguments: {
                        NUM: {
                            type: Scratch.ArgumentType.MENU,
                            menu: 'servoMenu'
                        },
                        ANGLE: {
                            type: Scratch.ArgumentType.NUMBER,
                            defaultValue: 90
                        }
                    }
                },
                {
                    opcode: 'setAllServos90',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Alle Servos auf 90 Grad setzen'
                },
                {
                    opcode: 'playSoundSequence',
                    blockType: Scratch.BlockType.COMMAND,
                    text: 'Spiele Tonfolge(freq,vol,dur;...)[SEQUENCE]',
                    arguments: {
                        SEQUENCE: {
                            type: Scratch.ArgumentType.STRING,
                            defaultValue: '1000,100,200;1200,80,200;800,50,300;'
                        }
                    }
                },
                {
                    opcode: 'getSensorValue',
                    blockType: Scratch.BlockType.REPORTER,
                    text: 'Wert von [SENSOR]',
                    arguments: {
                        SENSOR: {
                            type: Scratch.ArgumentType.MENU,
                            menu: 'sensorMenu'
                        }
                    }
                },
                {
                    opcode: 'getRawData',
                    blockType: Scratch.BlockType.REPORTER,
                    text: 'Zeige rohe Daten'
                }
            ],
            menus: {
                ledMenu: {
                    acceptReporters: true,
                    items: [
                        { text: 'D14', value: '0' },
                        { text: 'D12', value: '1' },
                        { text: 'D13', value: '2' }
                    ]
                },
                onOffMenu: {
                    acceptReporters: true,
                    items: [
                        { text: 'an', value: '1' },
                        { text: 'aus', value: '0' }
                    ]
                },
                servoMenu: {
                    acceptReporters: true,
                    items: [
                        { text: 'D23', value: '0' },
                        { text: 'D22', value: '1' },
                        { text: 'D21', value: '2' },
                        { text: 'D19', value: '3' },
                        { text: 'D18', value: '4' },
                        { text: 'D5', value: '5' }
                    ]
                },
                sensorMenu: {
                    acceptReporters: true,
                    items: [
                        { text: 'Poti D36', value: 'poti0' },
                        { text: 'Poti D39', value: 'poti1' },
                        { text: 'Poti D34', value: 'poti2' },
                        { text: 'Poti D35', value: 'poti3' },
                        { text: 'Touch D32', value: 'touch0' },
                        { text: 'Touch D33', value: 'touch1' },
                        { text: 'Touch D37', value: 'touch2' },
                        { text: 'Schalter D25', value: 'schalter0' }
                    ]
                }
            }
        };
    }

    connectWebSocket(args) {
        const ip = args.IP;
        this.ws = new WebSocket("ws://" + ip + "/ws");
        this.ws.onopen = () => console.log("Verbunden mit ESP32:", ip);
        this.ws.onmessage = (event) => this.handleMessage(event.data);
        this.ws.onerror = (err) => console.error("WebSocket Fehler:", err);
    }
    
    ledSet(args) {
        const num = args.NUM;
        const state = args.STATE;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(`led:${num}:${state}`);
        }
    }

    setServoFilter(args) {
        const filterValue = args.FILTER;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(`filter:${filterValue}`);
        }
    }

    servoSet(args) {
        const num = args.NUM;
        const angle = args.ANGLE;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(`servo:${num}:${angle}`);
        }
    }

    setAllServos90() {
      const NUM_SERVOS = 6; 
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        for (let i = 0; i < NUM_SERVOS; i++) {
          this.ws.send(`servo:${i}:90`);
        }
      }
    }

    playSoundSequence(args) {
        const sequence = args.SEQUENCE;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(`sound:${sequence}`);
        }
    }

    getSensorValue(args) {
        const sensor = args.SENSOR;
        return this.sensorValues[sensor] || 0;
    }

    handleMessage(data) {
        try {
            const sensorData = JSON.parse(data);
            this.sensorValues = sensorData;
            this.lastMessage = data;
        } catch (e) {
            this.lastMessage = "Fehler: " + data;
        }
    }

    getRawData() {
        return this.lastMessage;
    }
}

Scratch.extensions.register(new ESP32_WS());