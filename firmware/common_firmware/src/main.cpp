
/*
  ESP32 Servo Steuerung über Weboberfläche und Websocket

  Dieser Sketch realisiert eine drahtlose Steuerung von RC-Servos usw. über WLAN.
  Der ESP32 fungiert dabei als auch als WLAN-Client im raspi-Netzwerk oder falls nicht erreichbar als Access Point
  und stellt eine einfache Weboberfläche zur Verfügung.

 Erstes uploaden (speicher leer):
 - zufälliger Name wird generiert und gespeichert
 - zufällige lokale MAC wird generiert und gespeichert

 Basis funktionen:
  - Speicherung von WLAN-Zugangsdaten im EEPROM
  - Verbindung zu bekanntem WLAN + fallback Access Point
  - Anzeige von WLAN-Status, IP-Adresse und ESP-ID
  - WebSocket-Kommunikation für sofortige Reaktion auf Nutzerinteraktionen
  - MDNS-Unterstützung: Zugriff über http://esp-xxxx.local möglich
  - ota updates über WLAN
  - webseite zum ändern des hostnamens
  - webseite zum einstellen von WLAN Zugangsdaten


Hauptfunktionen:
  - Steuerung über weboberfläche und websocket:
   * Steuerung von 9 Servos über Slider
   * 3 LEDS über Slider
   * Einstellbarer Low-Pass-Filter für sanfte Bewegungen
  - Auslesen und Anzeigen über weboberfläche und websocket:
    * 4 Potentiometern (analog)
    * 3 Touch-Pins (kapazitiv)
    * 1 Schalter (mit internem Pull-Up)



 ToDo:
 - bei schnellen websocket commands hängt sich der esp auf
  - seite namen ändern hinzufügen

 
*/


#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESP32Servo.h>
#include <Preferences.h>
#include <ESPmDNS.h>
#include "esp_system.h"
#include <ArduinoOTA.h>
#include <ArduinoJson.h>

void loadOrGenerateMAC(uint8_t *mac);

const int servoPins[] = {23, 22, 21, 19, 18, 5}; //, 17, 16, 4};
const int potiPins[] = {36, 39, 34, 35};
const int schalterPins[] = {25};
const int touchPins[] = {32, 33, 27};
const int ledPins[] = {14, 12, 13};
const int LED_ONBOARD = 2;   // blaue Onboard LED
uint8_t currentMAC[6];   // globale Variable


#define NUM_SERVOS (sizeof(servoPins) / sizeof(servoPins[0]))
#define NUM_POTIS (sizeof(potiPins) / sizeof(potiPins[0]))
#define NUM_SCHALTER (sizeof(schalterPins) / sizeof(schalterPins[0]))
#define NUM_TOUCH (sizeof(touchPins) / sizeof(touchPins[0]))
#define NUM_LEDS (sizeof(ledPins) / sizeof(ledPins[0]))

Servo servos[NUM_SERVOS];
int servoTargets[NUM_SERVOS];
float currentAngles[NUM_SERVOS];
int potiValues[NUM_POTIS];
int schalterValues[NUM_SCHALTER];
int touchValues[NUM_TOUCH];
bool ledStates[NUM_LEDS] = {false};
String soundSequence = "";
bool playSound = false;

//Default = false
bool potiControl = false;
float filter = 0.9;

// deferred persistence flags (avoid slow NVS writes inside WS callbacks)
bool persistPotiPending = false;
unsigned long persistPotiAt = 0;

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");
Preferences preferences;

String espName = ""; 

String chipID = "";

// startup wifi credentials
const String DEFAULT_SSID = "robot";
const String DEFAULT_PASSWORD = "goodlife";
bool wifiConnected = false;
IPAddress wifiIP;





// --- NEU: Name laden oder erzeugen ---
void loadOrGenerateName() {
  preferences.begin("id", false);
  espName = preferences.getString("hostname", "");
  if (espName == "") {
    // Neuen Namen erzeugen: "esp-" + zufälliger name aus list1 + zufälliger name aus list2 + 2* zufälliges zeichen aus list3
    // Liste 1: Präfixe (erste Wortteile)

    const char* list1[] = {
      "Robo", "Mech", "Nano", "Byte", "Beta", "Tron", "Code", "Volt",
      "Gear", "Chip", "Hex", "Pix", "Neo", "Bit", "Dyno", "Electro",
      "Flux", "Atom", "Core", "Auto", "Luna", "Nova", "Bolt", "Data",
      "Spark", "Glim", "Blink", "Buzz", "Kilo", "Mini", "Pico", "Giga",
      "Tera", "Astro", "Juno", "Velo"
    };

    // Liste 2: Suffixe (zweite Wortteile)
    const char* list2[] = {
      "Lab", "Kit", "Hub", "Pix", "Bit", "Loop", "Bot", "Cube",
      "Droid", "Node", "Tick", "Dash", "Spark", "Mod", "Brain", "Bug",
      "Box", "Link", "Fun", "Nest", "Tron", "Orb", "Core", "Max",
      "Plus", "Star", "Beam", "Logic", "Wave", "Bolt", "Flow", "Net",
      "Grid", "Mind", "Edge", "Zone"
    };
    const char list3[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

    espName = "esp-" + String(list1[random(0, 8)]) + String(list2[random(0, 8)]) + String(list3[random(0, 36)]) + String(list3[random(0, 36)]);
    preferences.putString("hostname", espName);
    Serial.println("New name");
  } else {
    Serial.println("Name loaded");
  }
  Serial.println("Name: " + espName);
  preferences.end();
}

#include "esp_wifi.h"

void loadOrGenerateMAC(uint8_t *mac) {
  preferences.begin("id", false);

  // Schon vorhandene MAC laden
  String stored = preferences.getString("mac", "");
  if (stored != "") {
    // Umwandeln von String "AA:BB:CC:DD:EE:FF" zurück ins Array
    int values[6];
    if (sscanf(stored.c_str(), "%x:%x:%x:%x:%x:%x",
               &values[0], &values[1], &values[2],
               &values[3], &values[4], &values[5]) == 6) {
      for (int i = 0; i < 6; i++) mac[i] = (uint8_t) values[i];
    }
    Serial.println("Loaded MAC: " + stored);
  } else {
    // Neue zufällige lokale MAC erzeugen
    mac[0] = 0x02;  // lokal, unicast
    for (int i = 1; i < 6; i++) mac[i] = random(0, 256);

    char buf[18];
    sprintf(buf, "%02X:%02X:%02X:%02X:%02X:%02X",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    preferences.putString("mac", buf);
    Serial.println("new random MAC: " + String(buf));
  }

  preferences.end();

  // Anwenden
  esp_wifi_set_mac(WIFI_IF_STA, mac);
  memcpy(currentMAC, mac, 6);
}

String macToString(uint8_t *mac) {
  char buf[18];
  sprintf(buf, "%02X:%02X:%02X:%02X:%02X:%02X",
          mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(buf);
}

void saveWiFiCredentials(const String &ssid, const String &pass) {
  preferences.begin("wlan", false);
  preferences.putString("ssid", ssid);
  preferences.putString("pass", pass);
  preferences.end();
}

bool loadWiFiCredentials(String &ssid, String &pass) {
  preferences.begin("wlan", true);
  ssid = preferences.getString("ssid", "");
  pass = preferences.getString("pass", "");
  preferences.end();

  if (ssid == "") {
    Serial.println("No WLAN credentials stored.");
    // speichere Standard SSID und Passwort
    saveWiFiCredentials(DEFAULT_SSID, DEFAULT_PASSWORD);
    ssid = DEFAULT_SSID; 
    pass = DEFAULT_PASSWORD;
  }
  return ssid != "";
}

void tryConnectToWiFi() {
  String currentSSID;
  String currentPASS;
  loadWiFiCredentials(currentSSID, currentPASS);

  WiFi.begin(currentSSID.c_str(), currentPASS.c_str());
  Serial.print("Connecting to WLAN: ");
  Serial.println(currentSSID);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    wifiIP = WiFi.localIP();
    Serial.println("Connected! IP: " + wifiIP.toString());
    digitalWrite(LED_ONBOARD, HIGH);   // LED an bei WLAN

  } else {
    Serial.println("Connection failed.");
    digitalWrite(LED_ONBOARD, LOW);    // LED aus
  }
}

void setupDualWiFi() {

  uint8_t mac[6];
  loadOrGenerateMAC(mac); 
  loadOrGenerateName();

  tryConnectToWiFi();

  if (wifiConnected) {
    if (MDNS.begin(espName.c_str())) {
      Serial.println("mDNS active at: http://" + espName + ".local");
    } else {
      Serial.println("mDNS could not be started");
    }
  }
  else {
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(espName.c_str());
    Serial.println("Access Point started: " + WiFi.softAPIP().toString());
    Serial.println("SSID: " + espName);
    Serial.println("WLAN not connected, only AP active.");
  }
}



void handleSensoren(AsyncWebServerRequest *request){
    // 1. Statisches Dokument erstellen
    const size_t CAPACITY = JSON_OBJECT_SIZE(NUM_POTIS + NUM_TOUCH + NUM_SCHALTER);
    StaticJsonDocument<CAPACITY> doc;

    // 2. Daten eintragen
    for (int i = 0; i < NUM_POTIS; i++) {
        doc["poti" + String(i)] = potiValues[i];
    }
    for (int i = 0; i < NUM_TOUCH; i++) {
        doc["touch" + String(i)] = touchValues[i];
    }
    for (int i = 0; i < NUM_SCHALTER; i++) {
        doc["schalter" + String(i)] = schalterValues[i];
    }
    
    // 3. KORREKTUR: Serialisiere das Dokument ZUERST zu einem String
    String jsonOutput;
    // Wir nutzen serializeJson in die String-Variable
    serializeJson(doc, jsonOutput); 
    
    // 4. Sende den String, wie es die AsyncWebServer-Lib erwartet
    request->send(200, "application/json", jsonOutput); // <-- Jetzt wird der String übergeben
}
void setup() {
  randomSeed(esp_random());
  Serial.begin(115200);
  // Print reset reason and initial heap for debugging reboots
  esp_reset_reason_t rr = esp_reset_reason();
  Serial.printf("Reset reason: %d\n", (int)rr);
  Serial.printf("Free heap at boot: %u\n", ESP.getFreeHeap());
  
  //Onboard LED aus beim Start
  pinMode(LED_ONBOARD, OUTPUT);
  digitalWrite(LED_ONBOARD, LOW); 



  for (int i = 0; i < NUM_SERVOS; i++) {
    servos[i].attach(servoPins[i]);
    servoTargets[i] = 90;     
    currentAngles[i] = 90.0;  
    servos[i].write(servoTargets[i]);
  }

  for (int i = 0; i < NUM_SCHALTER; i++) {
    pinMode(schalterPins[i], INPUT_PULLUP);
  }

  for (int i = 0; i < NUM_LEDS; i++) {
    pinMode(ledPins[i], OUTPUT);
    digitalWrite(ledPins[i], LOW);
  }


  setupDualWiFi();
  
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>ESP32</title></head><body>";
  html += "<h1>ESP32 Steuerung</h1>";
  if (wifiConnected) {
    html += "<p><strong>IP:</strong> " + WiFi.localIP().toString() + "</p>";
  } else {
    html += "<p><strong>IP (AP):</strong> " + WiFi.softAPIP().toString() + "</p>";
  }
  html += "<p><strong>Name:</strong> " + espName + ".local</p>";
  html += "<p><strong>MAC:</strong> " + macToString(currentMAC) + "</p>";
  html += "<p><a href='/wlan'>WLAN-Einstellungen</a></p>";
  
  // 'checked' abhängig von potiControl einsetzen
  html += "<label><input type='checkbox' id='potiToggle' onchange='togglePoti(this.checked)' ";
  html += String(potiControl ? "checked" : "");
  html += "> Poti-Steuerung aktivieren</label><br>";
  
  html += "Filter: <input type='range' min='0' max='1' step='0.01' value='" + String(filter, 2) + "' id='filterSlider' oninput='sendFilter(this.value)'> ";
  html += "<span id='filterVal'>" + String(filter, 2) + "</span><br><br>";

  html += "<h2>Servo Steuerung</h2>";
  for (int i = 0; i < NUM_SERVOS; i++) {
    html += "<label>Servo " + String(i) + " (Pin " + String(servoPins[i]) + "):</label> ";
    html += "<input type='range' min='0' max='180' value='" + String(servoTargets[i]) +
            "' id='servo" + i + "' oninput='send(this)'>";
    html += "<span id='servoVal" + String(i) + "'>" + String(servoTargets[i]) + "&deg;</span><br>";
  }
  html += "<p></p>";
  html += "<button onclick='setAllServos90()'>All servos to 90°</button><br><br>";

  html += "<h2>LED Steuerung</h2>";
  for (int i = 0; i < NUM_LEDS; i++) {
    html += "<label>LED " + String(i) + " (Pin " + String(ledPins[i]) + "):</label> ";
    html += "<input type='range' min='0' max='1' value='" + String(ledStates[i] ? 1 : 0) +
            "' id='led" + i + "' oninput='sendLed(this)'><br>";
  }

  html += "<h2>Sensorwerte</h2><ul>";
  html += "<p><a href='/sensoren'>Sensorwerte</a></p>";
  
  html += "</ul>";

  html += "<script>";
  html += "const numServos = " + String(NUM_SERVOS) + ";";
  html += "var socket = new WebSocket('ws://' + location.host + '/ws');";
  html += R"rawliteral(
  function send(el) {
    let id = el.id.replace("servo", "");
    socket.send("servo:" + id + ":" + el.value);
  }
  function sendLed(el) {
    let id = el.id.replace("led", "");
    socket.send("led:" + id + ":" + el.value);
  }
  function togglePoti(state) {
    socket.send("poti:" + (state ? "on" : "off"));
  }
  function sendFilter(val) {
    socket.send("filter:" + val);
  }
  function setAllServos90() {
    if(socket && socket.readyState === WebSocket.OPEN) {
      for (let i = 0; i < numServos; i++) {
        socket.send(`servo:${i}:90`);
      }
    }
  }
  </script>
  )rawliteral";

  html += "</body></html>";
  request->send(200, "text/html", html);
});

server.on("/wlan", HTTP_GET, [](AsyncWebServerRequest *request) {
  request->send(200, "text/html", R"rawliteral(
    <h2>Connect WLAN</h2>
    <form action="/join" method="get">
      SSID: <input name="ssid"><br>
      Passwort: <input name="pass" type="password"><br>
      <input type="submit" value="Connect">
    </form>
  )rawliteral");
});

server.on("/join", HTTP_GET, [](AsyncWebServerRequest *request) {
  if (request->hasParam("ssid") && request->hasParam("pass")) {
    String ssid = request->getParam("ssid")->value();
    String pass = request->getParam("pass")->value();
    saveWiFiCredentials(ssid, pass);
    request->send(200, "text/html", "<p>WLAN saved. Restarting...</p>");
    delay(1000);
    ESP.restart();
  } else {
    request->send(400, "text/plain", "Missing parameters");
  }
});


server.on("/sensoren", HTTP_GET, handleSensoren);

server.on("/test", HTTP_GET, [](AsyncWebServerRequest *request) {
  request->send(200, "text/plain", "Test OK");
});

ws.onEvent([](AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) {

if (type == WS_EVT_CONNECT) {
    Serial.printf("WS Client #%u connected\n", client->id());
    
    // NEU: Sende den initialen Servo-Status an den neuen Client
    for (int i = 0; i < NUM_SERVOS; i++) {
        client->printf("servo:%d:%d", i, servoTargets[i]);
    }
    // Sende andere initial States (z.B. potiControl, filter, leds)
    client->printf("poti:%s", potiControl ? "on" : "off");
    client->printf("filter:%.2f", filter);
    
    return;
  }

  if (type != WS_EVT_DATA) return;

  AwsFrameInfo *info = (AwsFrameInfo *)arg;
  if (!(info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT)) return;

  // Protect against overly long frames that could fragment the heap
  const size_t MAX_MSG = 128; // conservative limit for control messages
  if (len == 0 || len > MAX_MSG) {
    Serial.printf("WS: drop too-long or empty msg (len=%u)\n", (unsigned)len);
    return;
  }

  // copy to a local NUL-terminated buffer and parse using C functions
  char buf[MAX_MSG + 1];
  memcpy(buf, data, len);
  buf[len] = '\0';

  // quick checks using strncmp / strcmp for common commands
  if (strcmp(buf, "poti:on") == 0) {
    if (!potiControl) {
      potiControl = true;
      // schedule persist in loop() after short debounce interval
      persistPotiPending = true;
      persistPotiAt = millis() + 1000; // persist after 1s
    }
    return;
  }


  if (strncmp(buf, "filter:", 7) == 0) {
    float f = 0.0f;
    if (sscanf(buf + 7, "%f", &f) == 1) {
      if (f >= 0.0f && f <= 1.0f) filter = f;
    }
    return;
  }

  if (strncmp(buf, "servo:", 6) == 0) {
    int idx = -1, val = 0;
    // parse "servo:%d:%d"
    if (sscanf(buf + 6, "%d:%d", &idx, &val) >= 1) {
      if (idx >= 0 && idx < NUM_SERVOS) {
        servoTargets[idx] = constrain(val, 0, 180);
      }
    }
    return;
  }

  if (strncmp(buf, "led:", 4) == 0) {
    int idx = -1, v = 0;
    if (sscanf(buf + 4, "%d:%d", &idx, &v) >= 1) {
      if (idx >= 0 && idx < NUM_LEDS) {
        ledStates[idx] = v > 0;
      }
    }
    return;
  }

});

server.on("/hostname", HTTP_GET, [](AsyncWebServerRequest *request) {
  if (request->hasParam("n")) {
    String newName = request->getParam("n")->value();

    // Prüfen: nur Base64 erlaubt
    const char* allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    bool valid = true;
    if (valid) {
      for (int i = 0; i < newName.length(); i++) {
        if (strchr(allowed, newName[i]) == NULL) {
          valid = false;
          break;
        }
      }
    }

    if (valid) {
      preferences.begin("id", false);
      preferences.putString("hostname", newName);
      preferences.end();
      request->send(200, "text/html",
                    "<p>Name gespeichert: " + newName + "<br>ESP startet neu...</p>");
      delay(1000);
      ESP.restart();
    } else {
      request->send(400, "text/html",
                    "<p>Ungültiger Name!<br>Only (A-Z, a-z, 0-9, +, /).</p>"
                    "<p><a href='/name'>Zurück</a></p>");
    }

  } else {
    String html = "<h2>Change ESP Name</h2>";
    html += "<p>Current Name: <b>" + espName + "</b></p>";
    html += "<form action='/name' method='get'>New Name (8 characters, Base64): ";
    html += "<input name='n' maxlength='8'><br>";
    html += "<input type='submit' value='Save'></form>";
    request->send(200, "text/html", html);
  }
});

  server.addHandler(&ws);

// CORS-Header senden, um die Browser-Verbindung zu erlauben FÜR ONLINE SCRATCH?. To Test!
//client->text("Access-Control-Allow-Origin: *");

server.begin();

// Nur ArduinoOTA starten, wenn WLAN (STA-Modus) erfolgreich verbunden ist!
    if (wifiConnected) { 
        // OPTIONAL ABER SEHR EMPFOHLEN: OTA-Callbacks für Fortschrittsanzeige hinzufügen!
        // (Diese fehlen in Ihrem Sketch und sind wichtig für die IDE-Ausgabe)
        ArduinoOTA
            .onStart([]() { Serial.println("OTA starting..."); })
            .onEnd([]() { Serial.println("\nOTA finished. Restarting..."); })
            .onProgress([](unsigned int progress, unsigned int total) { 
                Serial.printf("Progress: %u%%\r", (progress / (total / 100))); 
            })
            .onError([](ota_error_t error) { Serial.printf("Error[%u]: ", error); });

        ArduinoOTA.setHostname(espName.c_str());
        // ArduinoOTA.setPassword("Ihr_sicheres_OTA_Passwort"); // WICHTIG für Sicherheit!
        
        ArduinoOTA.begin(); // <-- Startet den mDNS/OTA-Dienst

        Serial.println("OTA service ready.");
    }

Serial.println("Ready");
Serial.print("IP address: ");
Serial.println(WiFi.localIP());
Serial.println("Hostname: " + espName);
}

void loop() {
  ArduinoOTA.handle();
  ws.cleanupClients();

  // Periodic heap logging to help diagnose reboots
  //static unsigned long lastHeapLog = 0;
  //if (millis() - lastHeapLog > 5000) {
  //  lastHeapLog = millis();
  //  Serial.printf("heap=%u, minHeap=%u\n", ESP.getFreeHeap(), ESP.getMinFreeHeap());
  //}


  for (int i = 0; i < NUM_POTIS; i++) {
    potiValues[i] = analogRead(potiPins[i]);
  }
  for (int i = 0; i < NUM_TOUCH; i++) {
    touchValues[i] = touchRead(touchPins[i]);
  }
  for (int i = 0; i < NUM_SCHALTER; i++) {
    schalterValues[i] = digitalRead(schalterPins[i]);
  }
  
// NEUE LOGIK (STABIL MIT ARDUINOJSON)
// Sende alle [interval] Millisekunden
static unsigned long lastSendTime = 0;
const long interval = 100; // Wir lassen es bei 100ms für den Test

if (millis() - lastSendTime > interval) {
    lastSendTime = millis();
    
    // 1. Statische Zuweisung (empfohlen für festes Layout)
    // Wir schätzen die notwendige Speichermenge. 
    // Der JSON-String ist relativ klein (ca. 10 Werte, 100 Zeichen).
    const size_t CAPACITY = JSON_OBJECT_SIZE(NUM_POTIS + NUM_TOUCH + NUM_SCHALTER);
    StaticJsonDocument<CAPACITY> doc;

    // 2. Daten eintragen
    for (int i = 0; i < NUM_POTIS; i++) {
        doc["poti" + String(i)] = potiValues[i];
    }
    for (int i = 0; i < NUM_TOUCH; i++) {
        doc["touch" + String(i)] = touchValues[i];
    }
    for (int i = 0; i < NUM_SCHALTER; i++) {
        doc["schalter" + String(i)] = schalterValues[i];
    }

    // 3. JSON an den WebSocket senden
    // Die Funktion serializeJson speichert den String in einem Puffer 
    // und sendet ihn direkt über den WebSocket.
    
    // Senden des JSON als String an alle verbundenen Clients
    char output[256]; // Puffer für den finalen JSON-String
    size_t len = serializeJson(doc, output, sizeof(output));
    
    if (len > 0) {
        ws.textAll(output);
    }
}


  for (int i = 0; i < NUM_SERVOS; i++) {
    currentAngles[i] = filter * currentAngles[i] + (1.0 - filter) * servoTargets[i];
    servos[i].write((int)currentAngles[i]);
  }

  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(ledPins[i], ledStates[i]);
  }


  delay(10);
}
