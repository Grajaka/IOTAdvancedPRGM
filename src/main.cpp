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
const char* password = "**********.";
const char* serverUrl = "https://iotadvancedprgm.onrender.com/receive_sensor_data"; 

// --- Mail Configuration ---
#define emailSenderAccount    "iotsensors74@gmail.com"
#define emailSenderPassword   "**************"
#define smtpServer            "smtp.gmail.com"
#define smtpServerPort        465

// --- Mail Recipient ---
String inputMessage = "karojg24@gmail.com";

const float TEMP_THRESHOLD = 25.0;
const float CURRENT_THRESHOLD = 0.3;

// --- VARIABLES COMPARTIDAS ---
float currentTemp = 0.0;
float currentCurrent = 0.0;
bool emailSent = false;

// Mutex para proteger acceso a variables compartidas
SemaphoreHandle_t xMutex;

// Colas para comunicación entre tareas
QueueHandle_t emailQueue;

// Estructura para alertas de correo
struct EmailAlert {
  char sensor[20];
  float value;
  char unit[5];
  float threshold;
};

// --- 2. PINES Y CALIBRACIÓN ---
#define ONE_WIRE_BUS 4
#define CURRENT_SENSOR_PIN 17

// Calibración ajustada para SCT-013
const float CALIBRATION_FACTOR = 5.51;

// Umbral de ruido: valores menores se consideran 0
const float NOISE_THRESHOLD = 0.10;  // Ajusta según tu sensor

// Offset del ADC (se calibra en setup)
float adcOffset = 0.0; 

// --- 3. INSTANCIAS ---
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
EnergyMonitor emon1;

// --- DECLARACIÓN DE FUNCIONES ---
void smtpCallback(SMTP_Status status);
void sendAlertEmail(const char* sensor, float value, const char* unit, float threshold);
void sendDataToFlask(const char* sensor_name, float value, const char* unit);

// --- CALLBACK SMTP ---
void smtpCallback(SMTP_Status status) {
  Serial.println(status.info());
  if (status.success()) {
    Serial.println("✓ Email enviado exitosamente");
    Serial.println("----------------");
  }
}

// --- FUNCIÓN DE ENVÍO DE CORREO ---
void sendAlertEmail(const char* sensor, float value, const char* unit, float threshold) {
  Serial.println("\n=== [CORE 0] INICIANDO ENVIO DE CORREO ===");
  
  SMTPSession smtp;
  
  ESP_Mail_Session session;
  session.server.host_name = smtpServer;
  session.server.port = smtpServerPort;
  session.login.email = emailSenderAccount;
  session.login.password = emailSenderPassword;
  session.login.user_domain = "";
  
  session.time.ntp_server = F("pool.ntp.org,time.nist.gov");
  session.time.gmt_offset = -5;
  session.time.day_light_offset = 0;
  
  smtp.debug(1);
  smtp.callback(smtpCallback);
  
  SMTP_Message message;
  message.sender.name = F("ESP32 IoT Alert");
  message.sender.email = emailSenderAccount;
  message.addRecipient(F("Usuario"), inputMessage);
  
  String subj = "[ALERTA] Umbral de ";
  subj += sensor;
  subj += " superado!";
  message.subject = subj;
  
  String alertBody = "ALERTA DE SENSOR\n\n";
  alertBody += "Sensor: ";
  alertBody += String(sensor);
  alertBody += "\n";
  alertBody += "Umbral configurado: ";
  alertBody += String(threshold, 2);
  alertBody += " ";
  alertBody += String(unit);
  alertBody += "\n";
  alertBody += "Valor actual: ";
  alertBody += String(value, 2);
  alertBody += " ";
  alertBody += String(unit);
  alertBody += "\n\n";
  alertBody += "Timestamp: ";
  alertBody += String(millis() / 1000);
  alertBody += " segundos\n";
  alertBody += "\n--- ESP32 IoT System ---";

  message.text.content = alertBody.c_str();
  message.text.charSet = F("utf-8");
  message.text.transfer_encoding = Content_Transfer_Encoding::enc_7bit;
  message.priority = esp_mail_smtp_priority::esp_mail_smtp_priority_high;

  Serial.println("[CORE 0] Conectando al servidor SMTP...");
  if (!smtp.connect(&session)) {
    Serial.println("[CORE 0] ✗ Error al conectar con servidor SMTP");
    Serial.printf("Razón: %s\n", smtp.errorReason().c_str());
    return;
  }
  
  Serial.println("[CORE 0] Enviando correo...");
  if (!MailClient.sendMail(&smtp, &message)) {
    Serial.println("[CORE 0] ✗ Error al enviar correo");
    Serial.printf("Razón: %s\n", smtp.errorReason().c_str());
  } else {
    Serial.println("[CORE 0] ✓ Correo enviado correctamente!");
  }
  
  smtp.closeSession();
  Serial.println("=== [CORE 0] FIN ENVIO DE CORREO ===\n");
}

// --- FUNCIÓN PARA CALIBRAR OFFSET DEL ADC ---
float calibrateADCOffset(int samples = 1000) {
  Serial.println("\n[CALIBRACIÓN] Midiendo offset del ADC...");
  Serial.println("[CALIBRACIÓN] Asegúrate de que NO haya corriente en el sensor");
  
  delay(2000);  // Esperar 2 segundos
  
  long sum = 0;
  for(int i = 0; i < samples; i++) {
    sum += analogRead(CURRENT_SENSOR_PIN);
    delayMicroseconds(100);
  }
  
  float offset = sum / (float)samples;
  Serial.printf("[CALIBRACIÓN] Offset calculado: %.2f (de 4095)\n", offset);
  Serial.printf("[CALIBRACIÓN] Voltaje offset: %.3fV\n", (offset / 4095.0) * 3.3);
  
  return offset;
}

// --- FUNCIÓN MEJORADA PARA LEER CORRIENTE ---
float readCurrent() {
  // Leer corriente RMS
  double Irms = emon1.calcIrms(1480);
  
  // Aplicar umbral de ruido
  if (Irms < NOISE_THRESHOLD) {
    return 0.0;
  }
  
  return Irms;
}
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

    Serial.printf("[CORE 1] Enviando %s (%.2f %s). HTTP: %d\n", sensor_name, value, unit, httpResponseCode);
    
    if (httpResponseCode >= 400) {
      Serial.println("[CORE 1] Error en respuesta: ");
      Serial.println(http.getString());
    }
    
    http.end();
  } else {
    Serial.println("[CORE 1] ERR: WiFi desconectado");
  }
}

// ============================================
// TAREA 1: ENVÍO DE CORREOS (NÚCLEO 0)
// ============================================
void emailTask(void * parameter) {
  Serial.println("[CORE 0] Tarea de Email iniciada");
  
  EmailAlert alert;
  
  for(;;) {
    // Esperar por alertas en la cola
    if(xQueueReceive(emailQueue, &alert, portMAX_DELAY)) {
      Serial.printf("[CORE 0] Alerta recibida: %s = %.2f %s\n", alert.sensor, alert.value, alert.unit);
      sendAlertEmail(alert.sensor, alert.value, alert.unit, alert.threshold);
      
      // Pequeña pausa después de enviar
      vTaskDelay(1000 / portTICK_PERIOD_MS);
    }
  }
}

// ============================================
// TAREA 2: LECTURA Y ENVÍO A FLASK (NÚCLEO 1)
// ============================================
void sensorAndFlaskTask(void * parameter) {
  Serial.println("[CORE 1] Tarea de Sensores y Flask iniciada");
  
  unsigned long previousMillis = 0;
  const long interval = 2000;
  
  for(;;) {
    unsigned long currentMillis = millis();
    
    if (currentMillis - previousMillis >= interval) {
      previousMillis = currentMillis;
      
      // === LECTURA DE SENSORES ===
      sensors.requestTemperatures();
      float tempC = sensors.getTempCByIndex(0);
      
      // Usar función mejorada para leer corriente
      float Irms = readCurrent();
      
      // Debug: mostrar lectura cruda del ADC cada 10 lecturas
      static int debugCounter = 0;
      if(debugCounter++ % 10 == 0) {
        int rawADC = analogRead(CURRENT_SENSOR_PIN);
        Serial.printf("[DEBUG] ADC Raw: %d, Offset: %.0f, Corriente: %.3fA\n", 
                      rawADC, adcOffset, Irms);
      }
      
      // Actualizar variables compartidas de forma segura
      if(xSemaphoreTake(xMutex, portMAX_DELAY)) {
        currentTemp = tempC;
        currentCurrent = Irms;
        xSemaphoreGive(xMutex);
      }
      
      // === VERIFICAR ALERTAS ===
      bool isTempAlert = (tempC != -127.00) && (tempC > TEMP_THRESHOLD);
      bool isCurrentAlert = (Irms > CURRENT_THRESHOLD);
      
      if (isTempAlert || isCurrentAlert) {
        if (!emailSent) {
          EmailAlert alert;
          
          if (isTempAlert) {
            Serial.printf("\n[CORE 1] ⚠ ALERTA: Temperatura %.2f°C > %.2f°C\n", tempC, TEMP_THRESHOLD);
            strcpy(alert.sensor, "Temperature_01");
            alert.value = tempC;
            strcpy(alert.unit, "C");
            alert.threshold = TEMP_THRESHOLD;
          } else if (isCurrentAlert) {
            Serial.printf("\n[CORE 1] ⚠ ALERTA: Corriente %.2fA > %.2fA\n", Irms, CURRENT_THRESHOLD);
            strcpy(alert.sensor, "Current_01");
            alert.value = Irms;
            strcpy(alert.unit, "A");
            alert.threshold = CURRENT_THRESHOLD;
          }
          
          // Enviar alerta a la cola (para el núcleo 0)
          xQueueSend(emailQueue, &alert, portMAX_DELAY);
          emailSent = true;
        }
      } else {
        emailSent = false;
      }
      
      // === ENVÍO A FLASK ===
      if(tempC != -127.00) { 
        sendDataToFlask("Temperature_01", tempC, "C");
      }
      sendDataToFlask("Current_01", Irms, "A");
    }
    
    // Pequeña pausa para no saturar el núcleo
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n=== INICIANDO ESP32 DUAL CORE ===");
  
  // Crear mutex
  xMutex = xSemaphoreCreateMutex();
  
  // Crear cola para alertas de email (máximo 5 alertas en cola)
  emailQueue = xQueueCreate(5, sizeof(EmailAlert));
  
  // Conectar WiFi
  WiFi.begin(ssid, password);
  Serial.print("Conectando WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✓ WiFi Conectado!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  // Configurar sensores
  analogReadResolution(12); 
  analogSetAttenuation(ADC_11db);  // Rango completo 0-3.3V
  sensors.begin();
  
  // CALIBRAR OFFSET DEL ADC
  adcOffset = calibrateADCOffset(1000);
  
  emon1.current(CURRENT_SENSOR_PIN, CALIBRATION_FACTOR);
  
  Serial.println("✓ Sensores inicializados y calibrados");
  
  // === CREAR TAREAS EN NÚCLEOS ESPECÍFICOS ===
  
  // TAREA 1: Email en NÚCLEO 0 (PRO_CPU)
  xTaskCreatePinnedToCore(
    emailTask,           // Función de la tarea
    "EmailTask",         // Nombre
    10000,               // Stack size (aumentado para correos)
    NULL,                // Parámetros
    1,                   // Prioridad
    NULL,                // Handle
    0                    // Núcleo 0 (PRO_CPU)
  );
  
  // TAREA 2: Sensores y Flask en NÚCLEO 1 (APP_CPU)
  xTaskCreatePinnedToCore(
    sensorAndFlaskTask,  // Función de la tarea
    "SensorFlaskTask",   // Nombre
    8000,                // Stack size
    NULL,                // Parámetros
    1,                   // Prioridad
    NULL,                // Handle
    1                    // Núcleo 1 (APP_CPU)
  );
  
  Serial.println("✓ Tareas creadas en ambos núcleos");
  Serial.println("  - NÚCLEO 0: Envío de correos");
  Serial.println("  - NÚCLEO 1: Sensores y Flask");
  Serial.println("======================\n");
}

// ============================================
// LOOP (Ya no se usa, las tareas se encargan)
// ============================================
void loop() {
  // El loop principal ya no hace nada
  // Todo está manejado por las tareas FreeRTOS
  vTaskDelay(1000 / portTICK_PERIOD_MS);
}