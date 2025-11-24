#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "EmonLib.h"

// --- 1. CONFIGURACIÓN DE RED Y SERVIDOR ---
const char* ssid = "POCO X7 Pro";
const char* password = "12345678.";
const char* serverUrl = "https://iotadvancedprgm.onrender.com/receive_sensor_data"; 

// --- 2. DEFINIR PINES Y CALIBRACIÓN ---
#define ONE_WIRE_BUS 4         // DS18B20 (Temperatura)
#define CURRENT_SENSOR_PIN 19  // SCT-013 (Corriente)

// Calibración para tu circuito amplificador (60.6 / 11 de Ganancia)
const float CALIBRATION_FACTOR = 5.51; 

// --- 3. INSTANCIAS ---
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
EnergyMonitor emon1;

// --- 4. VARIABLES DE TIEMPO ---
unsigned long previousMillis = 0;
const long interval = 2000; // Intervalo de envío (2 segundos)

// --- 5. FUNCIÓN DE ENVÍO GENÉRICA ---
void sendDataToFlask(const char* sensor_name, float value, const char* unit) {
  if(WiFi.status() == WL_CONNECTED){
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    // Crear JSON en el formato que Flask espera: {"sensor": "...", "value": "..."}
    StaticJsonDocument<200> doc;
    doc["sensor"] = sensor_name;
    doc["value"] = value;
    doc["unit"] = unit;
    
    String requestBody;
    serializeJson(doc, requestBody);

    // Enviar POST
    int httpResponseCode = http.POST(requestBody);

    Serial.printf("Enviando %s (%.2f %s). Respuesta HTTP: %d\n", sensor_name, value, unit, httpResponseCode);
    
  
    if (httpResponseCode >= 400) {
      Serial.println("Cuerpo de la respuesta: " + http.getString());
    }
    
    http.end();
  } else {
    Serial.println("ERR: WiFi desconectado, no se puede enviar data.");
  }
}

// --- 6. SETUP ---
void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  
  // Configuración de Hardware
  analogReadResolution(12); 
  sensors.begin();
  emon1.current(CURRENT_SENSOR_PIN, CALIBRATION_FACTOR); 
  
  // Conexión WiFi
  Serial.print("Conectando WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Conectado. IP: " + WiFi.localIP().toString());
}

// --- 7. LOOP PRINCIPAL ---
void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    // 1. Lectura Temperatura
    sensors.requestTemperatures();
    float tempC = sensors.getTempCByIndex(0);
    
    // 2. Lectura Corriente
    double Irms = emon1.calcIrms(1480);
    if (Irms < 0.05) Irms = 0.0; // Filtro de ruido

    // 3. Envío de TEMPERATURA
    if(tempC != -127.00) { // Solo si la lectura es válida
        sendDataToFlask("motor_temp_01", tempC, "C");
    }

    // 4. Envío de CORRIENTE
    sendDataToFlask("motor_current_01", Irms, "A");
  }
}