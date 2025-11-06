// 1. INCLUIR LIBRERÍAS
#include <OneWire.h>
#include <DallasTemperature.h>
#include "EmonLib.h"

// 2. DEFINIR PINES Y CONFIGURACIONES
// Pin para el sensor de temperatura DS18B20
#define ONE_WIRE_BUS 4

// Pin para el sensor de corriente SCT-013 (debe ser un pin ADC)
#define CURRENT_SENSOR_PIN 34

// 3. CREAR INSTANCIAS (OBJETOS)
// Configuración para el bus OneWire
OneWire oneWire(ONE_WIRE_BUS);
// Pasar la referencia de oneWire al sensor Dallas
DallasTemperature sensors(&oneWire);

// Crear una instancia de EnergyMonitor
EnergyMonitor emon1;

void setup() {
  // Iniciar la comunicación serial para ver los resultados en el monitor
  Serial.begin(115200);
  Serial.println("Iniciando sistema de monitoreo IoT...");

  // Iniciar el sensor de temperatura
  sensors.begin();

  // Configurar el sensor de corriente.
  // El pin y el valor de calibración son los argumentos.
  // CALIBRACIÓN: (Ratio del transformador) / (Resistencia de carga)
  // Para un SCT-013-000 (100A/50mA -> ratio 2000:1) y una resistencia de 33Ω:
  // 2000 / 33 = 60.6
  // Este es un valor inicial, puede que necesites ajustarlo con un multímetro real.
  emon1.current(CURRENT_SENSOR_PIN, 60.6);
}

void loop() {
  Serial.print("hello");
  // --- LECTURA DE TEMPERATURA ---
  // Pedir la temperatura a los sensores
  sensors.requestTemperatures();
  // Obtener la temperatura en grados Celsius del primer sensor en el bus
  float tempC = sensors.getTempCByIndex(0);

  // --- LECTURA DE CORRIENTE ---
  // Calcular la corriente RMS. El 1480 es el número de muestras que tomará.
  // Un valor más alto es más preciso pero más lento.
  double Irms = emon1.calcIrms(1480);

  // --- MOSTRAR DATOS EN EL MONITOR SERIAL ---
  Serial.print("Temperatura: ");
  Serial.print(tempC);
  Serial.print(" °C");

  Serial.print("  |  Corriente: ");
  Serial.print(Irms);
  Serial.println(" A");

  // Esperar 2 segundos antes de la siguiente lectura
  delay(2000);
}
