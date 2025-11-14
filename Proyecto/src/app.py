import os
from flask import Flask, render_template, jsonify, request
from flask_pymongo import PyMongo
from datetime import datetime
from dotenv import load_dotenv


# --- CONFIGURACIÓN E INICIALIZACIÓN ---

# Definimos la ruta al archivo .env
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)

# Configuración de MongoDB
mongo_uri = os.environ.get('MONGO_URI')

if not mongo_uri:
    # Se recomienda usar un logger o stderr para errores, pero print funciona
    print("Error: La variable de entorno MONGO_URI no está configurada.")
    
print(f"Intentando conectar a MongoDB...")
# Asignar la URI de conexión a la configuración de PyMongo
app.config["MONGO_URI"] = mongo_uri

try:
    mongo = PyMongo(app)
    
    SensorsReaders_collection = mongo.db.SensorsReaders 
    print("Conexión a MongoDB y colección 'SensorsReaders establecida.")

    # Prueba de conexión
    SensorsReaders_collection.find_one()
    print("Prueba de lectura a la colección 'SensorsReaders' exitosa.")
except Exception as e:
    print(f"Error al conectar o interactuar con MongoDB: {e}")
    mongo = None
    SensorsReaders_collection = None

# --- ENDPOINTS GENERALES Y HEALTH CHECK ---

# RUTA PARA EL HEALTH CHECK Y LA CONEXIÓN (Grafana la usa para probar la fuente)
@app.route('/', methods=['GET', 'POST'])
def root_path():
    """El plugin de Grafana llama a esta ruta para probar la conexión."""
    return 'OK', 200

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Muestra el dashboard de Grafana incrustado."""
    return render_template('dashboard.html')


# --- ENDPOINTS PARA GRAFANA SIMPLE JSON DATA SOURCE ---

@app.route('/search', methods=['POST'])
def search():
    """
    1. Grafana llama a esta ruta para obtener las métricas disponibles (Targets).
    """
    # Devolvemos el nombre de la serie que Grafana usará para la consulta
    return jsonify(["sensor1_temperatures"]), 200


@app.route('/query', methods=['POST'])
def query():
    """
    Ruta principal de consulta. Grafana envía el rango de tiempo y las métricas solicitadas.
    """
    
    if SensorsReaders_collection is None:
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 503

    try:
        # **1. Obtener la solicitud JSON de Grafana**
        req = request.get_json()
        
        # **2. Extraer los Targets solicitados**
        # Si no hay targets, devolvemos una lista vacía.
        targets = req.get('targets', [])
        
        # Lista final para almacenar todas las series de tiempo
        final_response = []

        # En este ejemplo, iteramos sobre los targets, pero como solo tenemos uno:
        # Tomamos el nombre del target de la primera consulta (si existe)
        target_name = targets[0]['target'] if targets and 'target' in targets[0] else "sensor1_temperatures"


        # 3. Obtener los datos de MongoDB (Mantenemos la lógica de obtener los últimos 1000)
        data_cursor = SensorsReaders_collection.find().sort("timestamp", -1).limit(1000)
        
        # 4. Formateamos los datos
        datapoints = []
        for document in data_cursor:
            value = document.get("value")

            if value is not None:
                try:
                    numeric_value = float(value)
                    timestamp_ms = int(document["timestamp"].timestamp() * 1000)
                    datapoints.append([numeric_value, timestamp_ms])
                except (ValueError, TypeError):
                    continue # Ignorar valores no numéricos

        # 5. Creamos la respuesta final etiquetada
        final_response.append({
            # Usamos el nombre del Target que Grafana nos envió
            "target": target_name, 
            "datapoints": datapoints
        })

        return jsonify(final_response)

    except Exception as e:
        print(f"Error al procesar la consulta de Grafana: {e}")
        return jsonify({"status": "error", "message": f"Error interno del servidor: {e}"}), 500



# --- ENDPOINTS DE INSERCIÓN DE DATOS ---

@app.route('/add_probe_data')
def agregar_dato_prueba():
    """
    Ruta de prueba para insertar un dato de ejemplo en la colección.
    """
    if SensorsReaders_collection is not None:
        try:
            # Aseguramos que el 'valor' sea numérico para la gráfica
            data_sensor = {"sensor": "temperature_probe", "value": 32.5, "unit": "C", "timestamp": datetime.now()}
            result = SensorsReaders_collection.insert_one(data_sensor)
            return jsonify({
                "mensaje": "Data sensor load succesfully 'SensorsReaders'",
                "id": str(result.inserted_id)
            })
        except Exception as e:
            return jsonify({"error": f"Error inserting into database: {e}"}), 500
    else:
        return jsonify({"error": "Connection to database is not established."}), 500
    
@app.route('/receive_sensor_data', methods=['POST'])
def receive_sensor_data():
    """
    Ruta para recibir datos de un sensor externo y guardarlos.
    """
    if SensorsReaders_collection is None:
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 503

    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se proporcionó un payload JSON"}), 400
        
        sensor_type = data.get('sensor_type')
        value = data.get('value')
        unit = data.get('unit', 'N/A') 

        if sensor_id is None or value is None:
            return jsonify({"error": "Faltan campos obligatorios: 'sensor_id' o 'value'"}), 400

        # CRÍTICO: Intentar convertir el valor a flotante.
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
             return jsonify({"error": "El campo 'value' debe ser un número convertible (float o int)."}), 400
        
        doc_to_insert = {
            "sensor": sensor_type,
            "value": numeric_value, # Usamos el valor numérico
            "unit": unit,
            "timestamp": datetime.now() 
        }
        
        result = SensorsReaders_collection.insert_one(doc_to_insert)

        return jsonify({
            "status": "success",
            "message": "Data sensor received and saved succesfully.",
            "id_mongo": str(result.inserted_id),
            "data_received": doc_to_insert
        }), 201
    except Exception as e:
        print(f"Error processing data sensor: {e}")
        return jsonify({"status": "error", "message": f"Server internal error: {e}"}), 500
    
if __name__ == '__main__':
    # Flask escucha en 0.0.0.0 y puerto 5001 para ser accesible por Docker
    app.run(host='0.0.0.0', port=5001, debug=True)