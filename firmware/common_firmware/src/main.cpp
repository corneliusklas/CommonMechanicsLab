
/*
  ESP32 Servo Steuerung über Weboberfläche und Websocket

  Dieser Sketch realisiert eine drahtlose Steuerung von RC-Servos usw. über WLAN.
  Der ESP32 fungiert dabei sowohl als Access Point als auch als WLAN-Client
  und stellt eine einfache Weboberfläche zur Verfügung.

  Hauptfunktionen:
  - Steuerung von 9 Servos über Slider in der Weboberfläche
  - 3 LEDS über Slider in der Weboberfläche
  - Umschaltbar auf Poti-Steuerung (ein Poti kontrolliert alle Servos + LEDs)
  - Einstellbarer Low-Pass-Filter für sanfte Bewegungen
  - Auslesen und Anzeigen von:
    * 4 Potentiometern (analog)
    * 3 Touch-Pins (kapazitiv)
    * 1 Schalter (mit internem Pull-Up)
  - Soundausgabe über einen Piezo-Buzzer mit konfigurierbarer Tonfolge:
    * Eingabeformat über Web: "frequenz,lautstärke,dauer;..."
    * Beispiel: "1000,80,200;800,60,300;"
    * Nicht-blockierende Wiedergabe im loop()
  - Schalter löst (bei aktivierter Poti-Steuerung) automatisches Abspielen    einer vorgegebenen Tonfolge aus
  - Speicherung von WLAN-Zugangsdaten im EEPROM
  - Verbindung zu bekanntem WLAN + fallback Access Point
  - Anzeige von WLAN-Status, IP-Adresse und ESP-ID
  - WebSocket-Kommunikation für sofortige Reaktion auf Nutzerinteraktionen
  - MDNS-Unterstützung: Zugriff über http://esp-xxxx.local möglich

  - Bei potiControl=true Verknüpfung der Eingabe mit LEDs und Servos
    - 3 potis mit 3 servos
    - 2 touch mit 2 servos
    - 1 touch mit 3 leds
    - schalter mit sound (x)


  Hinweise:
  - PWM-Ausgabe für Buzzer erfolgt für espressif systems version 3.x via 
    ledcAttach(buzzerPin, 1000, BUZZER_RES); // // Ton-Setup mit neuer API, Start mit 1 kHz, 8 Bit
    ledcWrite(buzzerPin, vol);  // Lautstärke (Duty Cycle)
    ledcChangeFrequency(buzzerPin, freq, BUZZER_RES);    
  -Wir verwenden in der PlatformIO die espressif systems version 2.x dort ist es anders

 ToDo:
 - schieberegler stimmen nicht wenn "alle servos 90" gedrückt wird und wenn sie extern betätigt werden
 
*/


#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESP32Servo.h>
#include <Preferences.h>
#include <ESPmDNS.h>
#include "esp_system.h"

void loadOrGenerateMAC(uint8_t *mac);

const int servoPins[] = {23, 22, 21, 19, 18, 5}; //, 17, 16, 4};
const int potiPins[] = {36, 39, 34, 35};
const int schalterPins[] = {25};
const int touchPins[] = {32, 33, 27};
const int ledPins[] = {14, 12, 13};
const int buzzerPin = 26;
const int LED_ONBOARD = 2;   // blaue Onboard LED
uint8_t currentMAC[6];   // globale Variable

//eigenes Namespace für die Poti-Option
const char* PREF_NS_CTRL = "ctrl";

#define BUZZER_RES 8
#define BUZZER_DUTY 128 // 50% bei 8 Bit
#define BUZZER_CHANNEL 7

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

String espName = ""; // --- NEU: Globaler Name ---

String chipID = "";
String currentSSID = "";
String currentPASS = "";
bool wifiConnected = false;
IPAddress wifiIP;

unsigned long nextToneTime = 0;
int toneIndex = 0;

//void generateChipID() {
//Das folgende klappt nicht da bei clone die MAC manchmal gleich ist  
//  uint64_t mac = ESP.getEfuseMac();
//  chipID = String((uint32_t)(mac >> 32), HEX) + String((uint32_t)(mac & 0xFFFFFFFF), HEX);
//  chipID.toUpperCase();
//}

// --- NEU: Base64 Encoder für MAC ---
String macToBase64(uint8_t *mac) {
  const char* b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  uint64_t value = 0;
  for (int i = 0; i < 6; i++) {
    value = (value << 8) | mac[i];
  }
  String out = "";
  for (int i = 0; i < 8; i++) {
    int idx = (value >> (42 - i * 6)) & 0x3F;
    out += b64[idx];
  }
  return out;
}

// --- NEU: Name laden oder erzeugen ---
void loadOrGenerateName() {
  preferences.begin("id", false);
  espName = preferences.getString("name", "");
  if (espName == "") {
    // MAC lesen
    uint8_t mac[6];
    loadOrGenerateMAC(mac);
    espName = macToBase64(mac);
    preferences.putString("name", espName);
    Serial.println("Neuer Name erzeugt: " + espName);
  } else {
    Serial.println("Geladener Name: " + espName);
  }
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
    Serial.println("Geladene eigene MAC: " + stored);
  } else {
    // Neue zufällige lokale MAC erzeugen
    mac[0] = 0x02;  // lokal, unicast
    for (int i = 1; i < 6; i++) mac[i] = random(0, 256);

    char buf[18];
    sprintf(buf, "%02X:%02X:%02X:%02X:%02X:%02X",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    preferences.putString("mac", buf);
    Serial.println("Neue zufällige MAC gespeichert: " + String(buf));
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
  preferences.begin("wifi", false);
  preferences.putString("ssid", ssid);
  preferences.putString("pass", pass);
  preferences.end();
}

bool loadWiFiCredentials(String &ssid, String &pass) {
  preferences.begin("wifi", true);
  ssid = preferences.getString("ssid", "");
  pass = preferences.getString("pass", "");
  preferences.end();
  return ssid.length() > 0;
}

void tryConnectToWiFi() {
  if (!loadWiFiCredentials(currentSSID, currentPASS)) return;
  WiFi.begin(currentSSID.c_str(), currentPASS.c_str());
  Serial.print("Verbinde mit WLAN: ");
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
    Serial.println("Verbunden! IP: " + wifiIP.toString());
    digitalWrite(LED_ONBOARD, HIGH);   // LED an bei WLAN

  } else {
    Serial.println("Verbindung fehlgeschlagen.");
    digitalWrite(LED_ONBOARD, LOW);    // LED aus
  }
}

void setupDualWiFi() {

  uint8_t mac[6];
  loadOrGenerateMAC(mac); // NEU
  loadOrGenerateName();  // NEU

  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(espName.c_str());
  Serial.println("Access Point gestartet: " + WiFi.softAPIP().toString());
  Serial.println("SSID: " + espName);

  tryConnectToWiFi();

  if (wifiConnected) {
    if (MDNS.begin(espName.c_str())) {
      Serial.println("mDNS aktiv unter: http://" + espName + ".local");
    } else {
      Serial.println("mDNS konnte nicht gestartet werden");
    }
  }
}

void updateToneSequence() {
  if (!playSound || millis() < nextToneTime) return;

  if (toneIndex >= soundSequence.length()) {
    //ledcWrite(buzzerPin, 0);
    ledcWrite(BUZZER_CHANNEL,0);
    playSound = false;
    toneIndex = 0;
    return;
  }

  int sep1 = soundSequence.indexOf(',', toneIndex);
  int sep2 = soundSequence.indexOf(',', sep1 + 1);
  int sep3 = soundSequence.indexOf(';', sep2 + 1);

  if (sep1 == -1 || sep2 == -1) {
    ledcWrite(BUZZER_CHANNEL, 0);  // Not-Aus
    playSound = false;
    return;
  }

  int freq = soundSequence.substring(toneIndex, sep1).toInt();
  int vol = soundSequence.substring(sep1 + 1, sep2).toInt();
  int dur = soundSequence.substring(sep2 + 1, sep3 == -1 ? soundSequence.length() : sep3).toInt();

  if (freq > 0) {
    ledcChangeFrequency(BUZZER_CHANNEL, freq, BUZZER_RES);
    ledcWrite(BUZZER_CHANNEL, map(vol, 0, 100, 0, 255)); // Duty Cycle
  } else {
    ledcWrite(BUZZER_CHANNEL, 0); // Pause
  }

  nextToneTime = millis() + dur;
  toneIndex = (sep3 == -1) ? soundSequence.length() : sep3 + 1;
}

void handleSensoren(AsyncWebServerRequest *request){
    String json = "{";
    
    // Potis
    for (int i = 0; i < NUM_POTIS; i++) {
        json += "\"poti" + String(i) + "\":" + String(potiValues[i]);
        if (i < NUM_POTIS-1 || NUM_TOUCH > 0 || NUM_SCHALTER > 0) json += ",";
    }

    // Touch
    for (int i = 0; i < NUM_TOUCH; i++) {
        json += "\"touch" + String(i) + "\":" + String(touchValues[i]);
        if (i < NUM_TOUCH-1 || NUM_SCHALTER > 0) json += ",";
    }

    // Schalter
    for (int i = 0; i < NUM_SCHALTER; i++) {
        json += "\"schalter" + String(i) + "\":" + String(schalterValues[i]);
        if (i < NUM_SCHALTER-1) json += ",";
    }

    json += "}";
    request->send(200, "application/json", json);
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

  //sound laden
  preferences.begin("sound", true);
  soundSequence = preferences.getString("sequence", "440,100,300;0,0,100;660,100,300;"); // beim ersten start leer, das soll nicht sein:
  preferences.end();

  //Poti-Status laden (Default beim ersten Start = false)
  preferences.begin(PREF_NS_CTRL, true);
  potiControl = preferences.getBool("poti", false);
  preferences.end();

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

ledcSetup(BUZZER_CHANNEL, 1000, BUZZER_RES);   // Kanal konfigurieren
ledcAttachPin(buzzerPin, BUZZER_CHANNEL);      // Pin mit Kanal verbinden
ledcWrite(BUZZER_CHANNEL, 0);                  // Startwert

  setupDualWiFi();
  
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>ESP32</title></head><body>";
  html += "<h1>ESP32 Steuerung</h1>";
  html += "<p><strong>IP:</strong> " + wifiIP.toString() + "</p>";
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
  html += "<button onclick='setAllServos90()'>Alle Servos auf 90°</button><br><br>";

  html += "<h2>LED Steuerung</h2>";
  for (int i = 0; i < NUM_LEDS; i++) {
    html += "<label>LED " + String(i) + " (Pin " + String(ledPins[i]) + "):</label> ";
    html += "<input type='range' min='0' max='1' value='" + String(ledStates[i] ? 1 : 0) +
            "' id='led" + i + "' oninput='sendLed(this)'><br>";
  }

  html += "<h2>Tonfolge</h2>";
  html += "<form action='/sound' method='get'>Tonfolge (freq,vol,dur;...): Beispiel 1100,80,200;1800,80,200;1800,80,200; <br>";
  html += "<input name='seq' size='60'><br><input type='submit' value='Abspielen'></form>";

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
    <h2>WLAN verbinden</h2>
    <form action="/join" method="get">
      SSID: <input name="ssid"><br>
      Passwort: <input name="pass" type="password"><br>
      <input type="submit" value="Verbinden">
    </form>
  )rawliteral");
});

server.on("/join", HTTP_GET, [](AsyncWebServerRequest *request) {
  if (request->hasParam("ssid") && request->hasParam("pass")) {
    String ssid = request->getParam("ssid")->value();
    String pass = request->getParam("pass")->value();
    saveWiFiCredentials(ssid, pass);
    request->send(200, "text/html", "<p>WLAN gespeichert. Starte neu...</p>");
    delay(1000);
    ESP.restart();
  } else {
    request->send(400, "text/plain", "Fehlende Parameter");
  }
});

server.on("/sound", HTTP_GET, [](AsyncWebServerRequest *request) {
  if (request->hasParam("seq")) {
    soundSequence = request->getParam("seq")->value();
    playSound = true;
    toneIndex = 0;

    //sequenz speichern
    preferences.begin("sound", false);
    preferences.putString("sequence", soundSequence);
    preferences.end();
    
    request->send(200, "text/html", "<p>Tonfolge wird abgespielt. <a href='/'>Zur&uuml;ck</a></p>");
  } else {
    request->send(400, "text/plain", "Fehlender Parameter");
  }
});

server.on("/sensoren", HTTP_GET, handleSensoren);

server.on("/test", HTTP_GET, [](AsyncWebServerRequest *request) {
  request->send(200, "text/plain", "Test OK");
});

ws.onEvent([](AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) {
  if (type == WS_EVT_CONNECT) {
    Serial.println("WebSocket verbunden → Poti aus");
    // ALT: potiControl = false; //nicht mehr beim verbinden ausschalten
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
  if (strcmp(buf, "poti:off") == 0) {
    if (potiControl) {
      potiControl = false;
      persistPotiPending = true;
      persistPotiAt = millis() + 1000;
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

  if (strncmp(buf, "sound:", 6) == 0) {
    // limit sound command length
    size_t payload_len = len - 6;
    const size_t MAX_SOUND = 256;
    if (payload_len == 0) return;
    if (payload_len > MAX_SOUND) {
      Serial.println("WS: sound payload too long, drop");
      return;
    }
    // assign to soundSequence (may allocate) but payload is bounded
    soundSequence = String(buf + 6);
    playSound = true;
    toneIndex = 0;
    Serial.println("Sound-Befehl erhalten.");
    return;
  }
});

server.on("/name", HTTP_GET, [](AsyncWebServerRequest *request) {
  if (request->hasParam("n")) {
    String newName = request->getParam("n")->value();

    // Prüfen: genau 8 Zeichen und nur Base64 erlaubt
    const char* allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    bool valid = (newName.length() == 8);
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
      preferences.putString("name", newName);
      preferences.end();
      request->send(200, "text/html",
                    "<p>Name gespeichert: " + newName + "<br>ESP startet neu...</p>");
      delay(1000);
      ESP.restart();
    } else {
      request->send(400, "text/html",
                    "<p>Ungültiger Name!<br>Nur 8 Zeichen erlaubt (A-Z, a-z, 0-9, +, /).</p>"
                    "<p><a href='/name'>Zurück</a></p>");
    }

  } else {
    String html = "<h2>ESP Name ändern</h2>";
    html += "<p>Aktueller Name: <b>" + espName + "</b></p>";
    html += "<form action='/name' method='get'>Neuer Name (8 Zeichen, Base64): ";
    html += "<input name='n' maxlength='8'><br>";
    html += "<input type='submit' value='Speichern'></form>";
    request->send(200, "text/html", html);
  }
});

  server.addHandler(&ws);

// CORS-Header senden, um die Browser-Verbindung zu erlauben FÜR ONLINE SCRATCH?. To Test!
//client->text("Access-Control-Allow-Origin: *");

server.begin();

}

void loop() {
  ws.cleanupClients();

  // Periodic heap logging to help diagnose reboots
  static unsigned long lastHeapLog = 0;
  if (millis() - lastHeapLog > 5000) {
    lastHeapLog = millis();
    Serial.printf("heap=%u, minHeap=%u\n", ESP.getFreeHeap(), ESP.getMinFreeHeap());
  }

  // Persist potiControl if requested (debounced to avoid frequent NVS writes)
  if (persistPotiPending && millis() >= persistPotiAt) {
    persistPotiPending = false;
    preferences.begin(PREF_NS_CTRL, false);
    preferences.putBool("poti", potiControl);
    preferences.end();
    Serial.println("Persisted potiControl");
  }

  for (int i = 0; i < NUM_POTIS; i++) {
    potiValues[i] = analogRead(potiPins[i]);
  }
  for (int i = 0; i < NUM_TOUCH; i++) {
    touchValues[i] = touchRead(touchPins[i]);
  }
  for (int i = 0; i < NUM_SCHALTER; i++) {
    schalterValues[i] = digitalRead(schalterPins[i]);
  }
  
  // Sensorwerte über WebSocket an den Client senden
  // Sende alle 30 Millisekunden
  static unsigned long lastSendTime = 0;
    const long interval = 50;
    if (millis() - lastSendTime > interval) {
        lastSendTime = millis();
        String json = "{";
        
        // Potis
        for (int i = 0; i < NUM_POTIS; i++) {
            json += "\"poti" + String(i) + "\":" + String(potiValues[i]);
            if (i < NUM_POTIS - 1 || NUM_TOUCH > 0 || NUM_SCHALTER > 0) json += ",";
        }

        // Touch
        for (int i = 0; i < NUM_TOUCH; i++) {
            json += "\"touch" + String(i) + "\":" + String(touchValues[i]);
            if (i < NUM_TOUCH - 1 || NUM_SCHALTER > 0) json += ",";
        }

        // Schalter
        for (int i = 0; i < NUM_SCHALTER; i++) {
            json += "\"schalter" + String(i) + "\":" + String(schalterValues[i]);
            if (i < NUM_SCHALTER - 1) json += ",";
        }

        json += "}";
        
        ws.textAll(json);
    }

  if (potiControl) {
      // Potis 0–3 → Servos 0–3
      for (int i = 0; i < 4 && i < NUM_POTIS && i < NUM_SERVOS; i++) {
        int mapped = map(potiValues[i], 0, 4095, 0, 180);
        servoTargets[i] = mapped;
      }
    
      // Touch → Servos 4 und 5
      int threshold = 40;
    
      // Touch 0 → Servo 4
      if (NUM_TOUCH > 0 && NUM_SERVOS > 4) {
        servoTargets[4] = (touchValues[0] > threshold) ? 0 : 90;
      }
    
      // Touch 1 → Servo 5
      if (NUM_TOUCH > 1 && NUM_SERVOS > 5) {
        servoTargets[5] = (touchValues[1] > threshold) ? 90 : 0;
      }
    
      // Touch 2 → LED 0
      if (NUM_TOUCH > 2 && NUM_LEDS > 0) {
        ledStates[0] = (touchValues[2] > threshold);
        ledStates[1]=ledStates[0];
        ledStates[2]=ledStates[0];
      }
    
      // Restliche Servos kopieren Servo 0 (falls mehr als 6 vorhanden)
      for (int i = 6; i < NUM_SERVOS; i++) {
        servoTargets[i] = servoTargets[0];
      }
    
      // Wenn Schalter gedrückt → Sound abspielen
      if (schalterValues[0] == LOW && !playSound) {
        
        //soundSequence = "1000,100,200;1200,80,200;800,50,300;";
        //astronomia soundSequence = "146.83, 79, 112; 0.0, 0, 188; 146.83, 79, 112; 0.0, 0, 38; 220.0, 79, 112; 0.0, 0, 38; 196.0, 79, 112; 0.0, 0, 188; 174.61, 79, 112; 0.0, 0, 188; 164.81, 79, 112; 0.0, 0, 188; 164.81, 79, 112; 0.0, 0, 38; 174.61, 79, 112; 0.0, 0, 38; 196.0, 79, 112; 0.0, 0, 188; 174.61, 79, 112; 0.0, 0, 38; 164.81, 79, 112; 0.0, 0, 38; 146.83, 79, 112; 0.0, 0, 188; 146.83, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 146.83, 79, 112; 0.0, 0, 188; 146.83, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 146.83, 79, 112; 0.0, 0, 188; 146.83, 79, 112; 0.0, 0, 38; 220.0, 79, 112; 0.0, 0, 38; 196.0, 79, 112; 0.0, 0, 188; 174.61, 79, 112; 0.0, 0, 188; 164.81, 79, 112; 0.0, 0, 188; 164.81, 79, 112; 0.0, 0, 38; 174.61, 79, 112; 0.0, 0, 38; 196.0, 79, 112; 0.0, 0, 188; 174.61, 79, 112; 0.0, 0, 38; 164.81, 79, 112; 0.0, 0, 38; 146.83, 79, 112; 0.0, 0, 188; 146.83, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 146.83, 79, 112; 0.0, 0, 188; 146.83, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 329.63, 79, 112; 0.0, 0, 38; 349.23, 79, 112; 0.0, 0, 38; 174.61, 79, 112; 0.0, 0, 38; 174.61, 79, 56; 0.0, 0, 94; 174.61, 79, 112; 0.0, 0, 38; 174.61, 79, 56; 0.0, 0, 94; 220.0, 79, 112; 0.0, 0, 38; 220.0, 79, 56; 0.0, 0, 94; 220.0, 79, 131; 0.0, 0, 19; 220.0, 79, 56; 0.0, 0, 94; 196.0, 79, 112; 0.0, 0, 38; 196.0, 79, 56; 0.0, 0, 94; 196.0, 79, 112; 0.0, 0, 38; 196.0, 79, 56; 0.0, 0, 94; 261.63, 79, 112; 0.0, 0, 38; 261.63, 79, 56; 0.0, 0, 94; 261.63, 79, 112; 0.0, 0, 38; 261.63, 79, 56; 0.0, 0, 94; 293.66, 79, 112; 0.0, 0, 38; 293.66, 79, 56; 0.0, 0, 94; 293.66, 79, 112; 0.0, 0, 38; 293.66, 79, 56; 0.0, 0, 94; 293.66, 79, 112; 0.0, 0, 38; 293.66, 79, 56; 0.0, 0, 94; 293.66, 79, 112; 0.0, 0, 38; 293.66, 79, 56; 0.0, 0, 94; 293.66, 79, 112; 0.0, 0, 38; 293.66, 79, 56; 0.0, 0, 94; 293.66, 79, 112; 0.0, 0, 38; 293.66, 79, 56; 0.0, 0, 94; 196.0, 79, 112; 0.0, 0, 38; 174.61, 79, 112; 0.0, 0, 38; 164.81, 79, 112; 0.0, 0, 38; 130.81, 79, 112;";
        playSound = true;
        toneIndex = 0;
      }
    }

  for (int i = 0; i < NUM_SERVOS; i++) {
    currentAngles[i] = filter * currentAngles[i] + (1.0 - filter) * servoTargets[i];
    servos[i].write((int)currentAngles[i]);
  }

  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(ledPins[i], ledStates[i]);
  }

  updateToneSequence();

  delay(10);
}
