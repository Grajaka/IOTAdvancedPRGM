import os
from flask import Flask, render_template, jsonify, request
from flask_pymongo import PyMongo
from flask_cors import CORS
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from bson.json_util import dumps 

# --- CONFIGURATION AND INITIALIZATION ---

# Define the path to the .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app)  # IMPORTANT: Enable CORS for Grafana

# MongoDB configuration
mongo_uri = os.environ.get('MONGO_URI')

if not mongo_uri:
    print("Error: The MONGO_URI environment variable is not configured.")
    
print(f"Attempting to connect to MongoDB...")
app.config["MONGO_URI"] = mongo_uri

try:
    mongo = PyMongo(app)
    SensorsReaders_collection = mongo.db.SensorsReaders 
    print("Connection to MongoDB and 'SensorsReaders' collection established.")
    SensorsReaders_collection.find_one()
    print("Read test to 'SensorsReaders' collection successful.")
except Exception as e:
    print(f"Error connecting or interacting with MongoDB: {e}")
    mongo = None
    SensorsReaders_collection = None

# --- GENERAL ENDPOINTS AND HEALTH CHECK ---

@app.route('/', methods=['GET', 'POST'])
def root_path():
    """The Grafana plugin calls this route to test the connection."""
    return jsonify({"message": "OK"}), 200

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Displays the embedded Grafana dashboard."""
    return render_template('dashboard.html')


# --- ENDPOINTS FOR GRAFANA SIMPLE JSON DATA SOURCE ---

@app.route('/search', methods=['POST'])
def search():
    """
    Grafana calls this route to get available metrics (Targets).
    Returns a list of unique available sensors.
    """
    try:
        if SensorsReaders_collection is None:
            return jsonify([]), 200
        
        # Get all unique sensor types
        unique_sensors = SensorsReaders_collection.distinct('sensor')
        
        # If no sensors exist, return a default list
        if not unique_sensors:
            unique_sensors = ["Current", "temperature_probe"]
        
        print(f"Available sensors for Grafana: {unique_sensors}")
        return jsonify(unique_sensors), 200
    
    except Exception as e:
        print(f"Error in /search: {e}")
        return jsonify(["Current", "temperature_probe"]), 200


@app.route('/query', methods=['POST'])
def query():
    """
    Grafana calls this route to get the actual data for the graph.
    """
    
    if SensorsReaders_collection is None:
        return jsonify([]), 200

    try:
        # Get the JSON request from Grafana
        req = request.get_json(force=True, silent=True)
        
        if req is None:
            print("Warning: Received empty or invalid JSON request")
            return jsonify([]), 200
            
        print(f"Request received from Grafana: {req}")
        
        # Extract the time range
        range_data = req.get('range', {})
        range_from = range_data.get('from')
        range_to = range_data.get('to')
        
        # Extract the targets (requested metrics)
        targets = req.get('targets', [])
        
        if not targets:
            print("No targets received from Grafana")
            return jsonify([]), 200
        
        final_response = []
        
        # Process each target
        for target_obj in targets:
            target_name = target_obj.get('target')
            
            if not target_name or target_obj.get('hide'):
                continue
            
            print(f"Processing target: {target_name}")
            
            # Build the MongoDB query
            query_filter = {"sensor": target_name}
            
            # If there's a time range, add it to the filter
            if range_from and range_to:
                try:
                    # Convert Grafana timestamps to datetime
                    from_dt = datetime.fromisoformat(range_from.replace('Z', '+00:00'))
                    to_dt = datetime.fromisoformat(range_to.replace('Z', '+00:00'))
                    
                    query_filter['timestamp'] = {
                        '$gte': from_dt,
                        '$lte': to_dt
                    }
                    print(f"Filtering by range: {from_dt} to {to_dt}")
                except Exception as e:
                    print(f"Error processing time range: {e}")
            
            # Get data from MongoDB
            data_cursor = SensorsReaders_collection.find(query_filter).sort("timestamp", 1).limit(5000)
            
            datapoints = []
            count = 0
            
            for document in data_cursor:
                count += 1
                # Support both 'value' and 'valor' (Spanish) for backward compatibility
                value = document.get("value") or document.get("valor")
                timestamp = document.get("timestamp")
                
                if value is not None and timestamp is not None:
                    try:
                        # Convert value to float
                        numeric_value = float(value)
                        
                        # Convert timestamp to milliseconds
                        timestamp_ms = int(timestamp.timestamp() * 1000)
                        
                        # Grafana format: [value, timestamp_ms]
                        datapoints.append([numeric_value, timestamp_ms])
                        
                    except (ValueError, TypeError) as e:
                        print(f"Error converting value: {value}, error: {e}")
                    except AttributeError as e:
                        print(f"Error with timestamp: {timestamp}, error: {e}")
            
            print(f"Found {count} documents for '{target_name}', {len(datapoints)} valid datapoints")
            
            # Add the result to the response
            final_response.append({
                "target": target_name,
                "datapoints": datapoints
            })
        
        print(f"Final response: {len(final_response)} series, total datapoints: {sum(len(s['datapoints']) for s in final_response)}")
        return jsonify(final_response), 200

    except Exception as e:
        print(f"Error processing Grafana query: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 200


# --- DATA INSERTION ENDPOINTS ---

@app.route('/add_probe_data')
def add_probe_data():
    """
    Test route to insert sample data into the collection.
    """
    if SensorsReaders_collection is not None:
        try:
            sensor_data = {
                "sensor": "temperature_probe", 
                "value": 32.5, 
                "unit": "C", 
                # take current Colombia time and convert to UTC (timezone-aware)
                "timestamp": datetime.now(ZoneInfo("America/Bogota")).astimezone(timezone.utc)
            }
            result = SensorsReaders_collection.insert_one(sensor_data)
            return jsonify({
                "message": "Sensor data loaded successfully to 'SensorsReaders'",
                "id": str(result.inserted_id)
            })
        except Exception as e:
            return jsonify({"error": f"Error inserting into database: {e}"}), 500
    else:
        return jsonify({"error": "Connection to database is not established."}), 500

@app.route('/add_current_data')
def add_current_data():
    """
    Test route to insert current sensor data.
    """
    if SensorsReaders_collection is not None:
        try:
            sensor_data = {
                "sensor": "Current", 
                "value": 1.7, 
                "unit": "A", 
                # take current Colombia time and convert to UTC (timezone-aware)
                "timestamp": datetime.now(ZoneInfo("America/Bogota")).astimezone(timezone.utc)
            }
            result = SensorsReaders_collection.insert_one(sensor_data)
            return jsonify({
                "message": "Sensor data loaded successfully to 'SensorsReaders'",
                "id": str(result.inserted_id)
            })
        except Exception as e:
            return jsonify({"error": f"Error inserting into database: {e}"}), 500
    else:
        return jsonify({"error": "Connection to database is not established."}), 500
    
@app.route('/receive_sensor_data', methods=['POST'])
def receive_sensor_data():
    """
    Route to receive data from an external sensor and save it.
    """
    if SensorsReaders_collection is None:
        return jsonify({"error": "Database connection is not established."}), 503

    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400
        
        sensor_type = data.get('sensor_type') or data.get('sensor')
        value = data.get('value')
        unit = data.get('unit', 'N/A') 

        if sensor_type is None or value is None:
            return jsonify({"error": "Missing required fields: 'sensor_type'/'sensor' or 'value'"}), 400

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
             return jsonify({"error": "The 'value' field must be a convertible number (float or int)."}), 400
        
        doc_to_insert = {
            "sensor": sensor_type,
            "value": numeric_value,
            "unit": unit,
            # use Colombia local time converted to timezone-aware UTC for MongoDB
            "timestamp": datetime.now(ZoneInfo("America/Bogota")).astimezone(timezone.utc)
        }
        
        result = SensorsReaders_collection.insert_one(doc_to_insert)

        # prepare a JSON-serializable copy for the response
        response_doc = dict(doc_to_insert)
        response_doc['timestamp'] = response_doc['timestamp'].isoformat()
        
        return jsonify({
            "status": "success",
            "message": "Sensor data received and saved successfully.",
            "mongo_id": str(result.inserted_id),
            "data_received": response_doc
        }), 201
    except Exception as e:
        print(f"Error processing sensor data: {e}")
        return jsonify({"status": "error", "message": f"Internal server error: {e}"}), 500

# New debug endpoint
@app.route('/debug/last_records')
def debug_last_records():
    """
    Debug endpoint to view the last records.
    """
    if SensorsReaders_collection is None:
        return jsonify({"error": "No database connection"}), 503
    
    try:
        records = list(SensorsReaders_collection.find().sort("timestamp", -1).limit(10))
        
        # Convert ObjectId and datetime to string for JSON
        for record in records:
            record['_id'] = str(record['_id'])
            if 'timestamp' in record:
                record['timestamp'] = record['timestamp'].isoformat()
        
        return jsonify({
            "count": len(records),
            "records": records
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/debug/sensors')
def debug_sensors():
    """
    Debug endpoint to see all unique sensor names.
    """
    if SensorsReaders_collection is None:
        return jsonify({"error": "No database connection"}), 503
    
    try:
        unique_sensors = SensorsReaders_collection.distinct('sensor')
        
        # Get count for each sensor
        sensor_info = []
        for sensor in unique_sensors:
            count = SensorsReaders_collection.count_documents({'sensor': sensor})
            latest = SensorsReaders_collection.find_one(
                {'sensor': sensor},
                sort=[('timestamp', -1)]
            )
            
            info = {
                'sensor': sensor,
                'count': count,
                'latest_value': latest.get('value') or latest.get('valor') if latest else None,
                'latest_timestamp': latest['timestamp'].isoformat() if latest and 'timestamp' in latest else None
            }
            sensor_info.append(info)
        
        return jsonify({
            "total_sensors": len(unique_sensors),
            "sensors": sensor_info
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

#------Infinity seeries -----------

@app.route('/infinity_query', methods=['POST', 'GET'])
def infinity_query():
    """
    Ruta para el plugin Grafana Infinity. Devuelve data plana [timestamp, value]
    """
    
    if SensorsReaders_collection is None:
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 503

    try:
        # Consulta de datos (la misma que usaste antes)
        data_cursor = SensorsReaders_collection.find().sort("timestamp", -1).limit(1000)
        
        infinity_data = []
        for document in data_cursor:
            value = document.get("value")
            timestamp_dt = document.get("timestamp")

            if value is not None and timestamp_dt is not None:
                try:
                    numeric_value = float(value)
                    
                    if isinstance(timestamp_dt, datetime):
                        # Convertimos a formato ISO 8601 (string) para que Infinity lo entienda fácilmente
                        timestamp_iso = timestamp_dt.isoformat()
                        
                        # Creamos el objeto plano que Infinity espera
                        infinity_data.append({
                            "time": timestamp_iso, 
                            "value": numeric_value
                        })
                        
                except (ValueError, TypeError) as e:
                    print(f"Advertencia: Error de conversión en documento. {e}")
            
        # Infinity espera un array de objetos planos: [{"time": "...", "value": 1.0}, ...]
        return jsonify(infinity_data)

    except Exception as e:
        print(f"Error en infinity_query: {e}")
        return jsonify({"status": "error", "message": f"Error interno del servidor: {e}"}), 500
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)