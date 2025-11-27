# Industrial Motor Monitoring System (IMMS)

![Badge - ESP32](https://img.shields.io/badge/Hardware-ESP32_Dual_Core-red)
![Badge - Flask](https://img.shields.io/badge/Backend-Flask-black)
![Badge - Docker](https://img.shields.io/badge/Container-Docker-blue)
![Badge - Grafana](https://img.shields.io/badge/Visualization-Grafana-orange)
![Badge - MongoDB](https://img.shields.io/badge/Database-MongoDB-green)
![Badge - Status](https://img.shields.io/badge/Status-Deployed-success)

> **Despliegue en Vivo:** https://iotadvancedprgm-2.onrender.com

---

## 馃摉 Descripci贸n General

Este proyecto implementa un ecosistema **AIoT (Artificial Intelligence of Things)** modular y escalable dise帽ado para el monitoreo en tiempo real de variables cr铆ticas (temperatura y corriente) en motores industriales.  
Reemplaza soluciones SCADA propietarias mediante una arquitectura *cloud-native* basada completamente en tecnolog铆as abiertas.

El flujo de datos abarca desde la adquisici贸n f铆sica mediante acondicionamiento de se帽ales en el borde (Edge) hasta el procesamiento, almacenamiento y visualizaci贸n en la nube usando **Docker, Flask, MongoDB y Grafana** desplegados en **Render**.

---

## 馃彈 Arquitectura del Sistema

La soluci贸n consta de tres capas principales:

- **Edge (Hardware/Firmware)**
- **Cloud (Backend/Base de Datos)**
- **Aplicaci贸n (Dashboard en Grafana)**

```mermaid
graph LR
    A[Motor Industrial] -->|Temp/Corriente| B(Sensores y Acondicionamiento)
    B -->|Se帽al Anal贸gica/Digital| C{ESP32 DevKit V1}
    C -->|Core 0: SMTP Alerts| D[Servidor de Correo]
    C -->|Core 1: HTTP POST JSON| E[Gateway en Render]
    E -->|API Flask| F[(MongoDB Atlas)]
    G[Dashboard Grafana] -->|Infinity Plugin| E
    F -.->|Persistencia| G
```

---

## 馃攲 Ingenier铆a de Hardware

### Circuito de Acondicionamiento para SCT-013

1. **Suelo Virtual (1.65V)**
   - Divisor resistivo (R1 = R2).
   - Amplificador operacional como seguidor (buffer).

2. **Filtrado y Conversi贸n**
   - Resistencia de carga de 33惟.
   - Capacitor de acople AC de 10碌F.

3. **Amplificaci贸n con Op-Amp**
   - Configuraci贸n no inversora con ganancia:  
     \
     \(G = 1 + rac{100k\Omega}{10k\Omega} pprox 11\)

### Sensor de Temperatura DS18B20

- Protocolo digital 1-Wire.
- Resistencia pull鈥憉p de 4.7k惟.
- Rango operativo: 鈭?5鈥癈 a 125鈥癈.

---

## 馃捇 Firmware (ESP32 + FreeRTOS)

| N煤cleo | Tarea | Descripci贸n |
|--------|--------|-------------|
| Core 0 | **emailTask** | Env铆o de alertas SMTP con SSL/TLS |
| Core 1 | **sensorAndFlaskTask** | Lectura ADC, RMS, l贸gica de umbral y HTTP POST |

Caracter铆sticas del firmware:

- Uso de **mutex** para variables compartidas.  
- **Queues** para comunicaci贸n entre tareas.  
- Factor de calibraci贸n ajustado emp铆ricamente: **5.51**.

---

## 鈽侊笍 Backend y Cloud

### API (Flask)
- Endpoint principal: `/receive_sensor_data` (POST).
- Compatible con el plugin **Infinity** de Grafana.

### Base de Datos: MongoDB Atlas
- Colecci贸n principal: `SensorsReaders`.

### Dashboard en Grafana
- Visualizaci贸n en tiempo real e hist贸ricos.
- Paneles con gauge, series temporales y estad铆sticas.

---

## 馃殌 Instalaci贸n y Despliegue

### 1. Entorno Local con Docker

```bash
git clone https://github.com/tu-usuario/iot-motor-monitor.git
cd iot-motor-monitor
docker-compose up --build
```

Servicios locales:

- API Flask 鈫?http://localhost:5001  
- Grafana 鈫?http://localhost:3000  
- Mongo Express 鈫?http://localhost:8081  

### 2. Configuraci贸n del Firmware (PlatformIO)

```cpp
const char* ssid = "TU_WIFI";
const char* password = "TU_PASSWORD";
const char* serverUrl = "https://tu-deploy-en-render.com/receive_sensor_data";
```

---

## 馃搳 Endpoints de la API

| M茅todo | Endpoint | Descripci贸n |
|--------|----------|-------------|
| **POST** | `/receive_sensor_data` | Recibe telemetr铆a de sensores |
| **GET** | `/infinity_query` | Datos planos JSON para Grafana |
| **GET** | `/dashboard` | Visualizaci贸n web integrada |

---

## 馃幆 Conclusiones

1. Arquitectura robusta y de bajo costo.  
2. Base s贸lida para mantenimiento predictivo mediante series temporales.  
3. Escalable gracias a contenedores y despliegue cloud鈥憂ative.

---

## Autor

**Ing. [Tu Nombre]**  
IoT Solutions Architect & Embedded Systems Developer
