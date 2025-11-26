#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "EmonLib.h"
#include "ESP_Mail_Client.h"

// --- 1. CONFIGURACIÓN DE RED Y SERVIDOR ---
const char* ssid = "POCO X7 Pro";
const char* password = "12345678.";
const char* serverUrl = "https://iotadvancedprgm.onrender.com/receive_sensor_data"; 

// ---Mail Configuration ---
#define emailSenderAccount    "iotsensors74@gmail.com"
#define emailSenderPassword   "wpop vmhq ddlz qhnd"  // App Password for Gmail
#define smtpServer            "smtp.gmail.com"
#define smtpServerPort        465
#define emailSubject          "[ALERT] ESP32 Temperature"

// --- Mail Recipient ---
String inputMessage = "karojg24@gmail.com";
String enableEmailChecked = "checked";
String inputMessage2 = "true";

const float TEMP_THRESHOLD = 25.0;
const float CURRENT_THRESHOLD = 0.3;

bool emailSent = false;

const char* PARAM_INPUT_1 = "email_input";
const char* PARAM_INPUT_2 = "enable_email_input";
const char* PARAM_INPUT_3 = "threshold_input";

SMTPSession smtp;

// --- DECLARACIÓN DE FUNCIONES (Forward Declaration) ---
void smtpCallback(SMTP_Status status);
void sendAlertEmail(const char* sensor, float value, const char* unit, float threshold);

// --- IMPLEMENTACIÓN DE smtpCallback (ANTES de sendAlertEmail) ---
void smtpCallback(SMTP_Status status) {
  Serial.println(status.info());
  if (status.success()) {
    Serial.println("Email sent successfully");
    Serial.println("----------------");
  }
}

// --- FUNCIÓN DE ENVÍO DE ALERTA ---
void sendAlertEmail(const char* sensor, float value, const char* unit, float threshold) {
  // 1. Configurar datos de la SESIÓN (Servidor y Login)
  ESP_Mail_Session session;
  session.server.host_name = smtpServer;
  session.server.port = smtpServerPort;
  session.login.email = emailSenderAccount;
  session.login.password = emailSenderPassword;
  session.login.user_domain = "";
  
  // 2. Crear el mensaje
  SMTP_Message message;
  message.sender.name = "ESP32 IoT Alert";
  message.sender.email = emailSenderAccount;
  
  String subj = "[ALERTA] Umbral de ";
  subj += sensor;
  subj += " superado!";
  message.subject = subj;
  
  String alertBody = "¡ALERTA!\n";
  alertBody += "El sensor '";
  alertBody += String(sensor);
  alertBody += "' ha superado el umbral.\n";
  alertBody += "UMBRAL: ";
  alertBody += String(threshold, 2);
  alertBody += " ";
  alertBody += String(unit);
  alertBody += "\n";
  alertBody += "VALOR ACTUAL: ";
  alertBody += String(value, 2);
  alertBody += " ";
  alertBody += String(unit);
  alertBody += "\n";
  alertBody += "Timestamp: ";
  alertBody += String(millis());

  message.text.content = alertBody.c_str();
  message.text.charSet = "utf-8";
  message.text.transfer_encoding = Content_Transfer_Encoding::enc_7bit;
  message.priority = esp_mail_smtp_priority::esp_mail_smtp_priority_high;
  message.addRecipient("", inputMessage.c_str());
  smtp.callback(smtpCallback);

  // 3. Enviar correo
  Serial.println("Intentando enviar correo de alerta...");
  if (!MailClient.sendMail(&smtp, &message)) {
    Serial.println("Error grave al enviar correo. Revisar log.");
    Serial.println(smtp.errorReason());
    smtp.closeSession();
  }
}

// --- 2. DEFINIR PINES Y CALIBRACIÓN ---
#define ONE_WIRE_BUS 4
#define CURRENT_SENSOR_PIN 17 //change 19

const float CALIBRATION_FACTOR = 5.51; 

// --- 3. INSTANCIAS ---
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
EnergyMonitor emon1;

// --- 4. VARIABLES DE TIEMPO ---
unsigned long previousMillis = 0;
const long interval = 2000;

// --- 5. FUNCIÓN DE ENVÍO GENÉRICA ---
void sendDataToFlask(const char* sensor_name, float value, const char* unit) {
  if(WiFi.status() == WL_CONNECTED){
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<200> doc;
    doc["sensor"] = sensor_name;
    doc["value"] = value;
    doc["unit"] = unit;
    
    String requestBody;
    serializeJson(doc, requestBody);

    int httpResponseCode = http.POST(requestBody);

    Serial.printf("Enviando %s (%.2f %s). Respuesta HTTP: %d\n", sensor_name, value, unit, httpResponseCode);
    
    if (httpResponseCode >= 400) {
      Serial.println("Cuerpo de la respuesta: ");
      Serial.println(http.getString());
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
  
  analogReadResolution(12); 
  sensors.begin();
  emon1.current(CURRENT_SENSOR_PIN, CALIBRATION_FACTOR); 
  
  Serial.print("Conectando WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Conectado. IP: ");
  Serial.print(WiFi.localIP().toString());
}

// --- 7. LOOP PRINCIPAL ---
void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    sensors.requestTemperatures();
    float tempC = sensors.getTempCByIndex(0);
    
    double Irms = emon1.calcIrms(1480);
    if (Irms < 0.05) Irms = 0.0; 

    bool isTempAlert = (tempC != -127.00) && (tempC > TEMP_THRESHOLD);
    bool isCurrentAlert = (Irms > CURRENT_THRESHOLD);

    if (isTempAlert || isCurrentAlert) {
        if (!emailSent) {
            if (isTempAlert) {
                sendAlertEmail("Temperature_01", tempC, "C", TEMP_THRESHOLD);
            } else if (isCurrentAlert) {
                sendAlertEmail("Current_01", Irms, "A", CURRENT_THRESHOLD);
            }
            emailSent = true;
        }
    } else {
        emailSent = false;
    }
    
    if(tempC != -127.00) { 
        sendDataToFlask("Temperature_01", tempC, "C");
    }

    sendDataToFlask("Current_01", Irms, "A");
  }
}