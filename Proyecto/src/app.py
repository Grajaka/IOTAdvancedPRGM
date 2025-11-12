import os
from flask import Flask, render_template, jsonify, request
from flask_pymongo import PyMongo
from datetime import datetime
from dotenv import load_dotenv


# Definimos la ruta al archivo .env
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

load_dotenv(dotenv_path)


app = Flask(__name__)

mongo_uri = os.environ.get('MONGO_URI')

if not mongo_uri:
    print("Error: La variable de entorno MONGO_URI no está configurada.")


print(f"Intentando conectar a MongoDB...")
app.config["MONGO_URI"] = mongo_uri

try:
    mongo = PyMongo(app)
    
    SensorsReaders_collection = mongo.db.SensorsReaders 
    print("Conexión a MongoDB y colección 'SensorsReaders establecida.")

    SensorsReaders_collection.find_one()
    print("Prueba de lectura a la colección 'SensorsReaders' exitosa.")
except Exception as e:
    print(f"Error al conectar o interactuar con MongoDB: {e}")
    mongo = None
    SensorsReaders_collection = None

@app.route('/')
def ruta():
    return 'Mi primer hola mundo'


@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/add_probe_data')
def agregar_dato_prueba():
    """
    Ruta de prueba para MANDAR (insertar) un dato de ejemplo
    en la colección 'sensor1'.
    """
    if SensorsReaders_collection is not None:
        try:
            
            data_sensor = {"sensor": "temperature_probe", "value": 32, "unite": "C"}
            # Insertamos el dato en la colección 'sensor1'
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
    if SensorsReaders_collection is None:
        
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 503

    try:
        # Obtener los datos JSON
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se proporcionó un payload JSON"}), 400

        
        sensor_id = data.get('sensor_id')
        value = data.get('value')
        unit = data.get('unit', 'N/A') 

        if sensor_id is None or value is None:
            return jsonify({"error": "Faltan campos obligatorios: 'sensor_id' o 'value'"}), 400

        
        doc_to_insert = {
            "sensor": sensor_id,
            "valor": value,
            "unidad": unit,
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
    
@app.route('/dashboard')
def dashboard():
    """Muestra el dashboard de Grafana incrustado."""
    # Simplemente renderiza una plantilla HTML
    return render_template('dashboard.html')
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)