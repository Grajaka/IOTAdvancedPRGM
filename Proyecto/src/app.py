import os
from flask import Flask, render_template, jsonify, request
from flask_pymongo import PyMongo
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# ============================
#  LOAD ENVIRONMENT
# ============================

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

mongo_uri = os.environ.get("MONGO_URI")
if not mongo_uri:
    mongo_uri = "mongodb+srv://kjaramillo1_db_user:nL8dP3yzNhJXpRhC@cluster0.7wetitv.mongodb.net/IOTAdvanced?appName=Cluster0"

grafana_embed_url = os.environ.get('GRAFANA_EMBED_URL','http://localhost:3000/public-dashboards/65fe92bf244e40dbb7d0e1efd4e4142b?orgId=1&kiosk')
                                   
app = Flask(__name__)
app.config["MONGO_URI"] = mongo_uri
CORS(app)

try:
    mongo = PyMongo(app)
    SensorsReaders_collection = mongo.db.SensorsReaders
    SensorsReaders_collection.find_one()
except Exception as e:
    print("Error connecting to MongoDB:", e)
    SensorsReaders_collection = None

# ============================
#   TIME PARSER FOR GRAFANA
# ============================

def parse_grafana_time(value):
    """
    Converts Grafana timestamps:
    - ISO8601 → datetime
    - now     → utcnow()
    - now-6h  → utcnow() - 6h
    """

    if not value:
        return None

    
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except:
        pass

    now = datetime.now(timezone.utc)

    if value == "now":
        return now

    # now-6h, now-12h, etc.
    if value.startswith("now-") and value.endswith("h"):
        try:
            hours = int(value.replace("now-", "").replace("h", ""))
            return now - timedelta(hours=hours)
        except:
            pass

    return None
# ============================
#        Sensor Data Receiver
# ============================
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



# ============================
# BASIC ROUTES
# ============================

@app.route('/', methods=['GET', 'POST'])
def root():
    return jsonify({"message": "OK"}), 200

@app.route('/search', methods=['GET', 'POST'])
def search():
    try:
        sensores = SensorsReaders_collection.distinct("sensor")
        return jsonify(sensores), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================
#        QUERY (MAIN)
# ============================

@app.route('/query', methods=['POST'])
def query():
    if SensorsReaders_collection is None:
        return jsonify([]), 200

    req = request.get_json(silent=True)

    if not req:
        print("WARN: empty request")
        return jsonify([]), 200

    print("REQ:", req)

    # Get and parse range
    range_raw = req.get("range", {})
    start_raw = range_raw.get("from")
    end_raw = range_raw.get("to")

    start_dt = parse_grafana_time(start_raw)
    end_dt = parse_grafana_time(end_raw)

    print(f"Parsed range → {start_dt}  to  {end_dt}")

    final_response = []

    targets = req.get("targets", [])

    for t in targets:
        name = t.get("target")
        if not name:
            continue

        query_filter = {"sensor": name}

        # Add timestamp filter if parsed OK
        if start_dt and end_dt:
            query_filter["timestamp"] = {"$gte": start_dt, "$lte": end_dt}

        cursor = SensorsReaders_collection.find(query_filter).sort("timestamp", 1).limit(5000)

        datapoints = []

        for d in cursor:
            value = d.get("value") or d.get("valor")
            ts = d.get("timestamp")

            if value is None or ts is None:
                continue

            datapoints.append([
                float(value),
                int(ts.timestamp() * 1000)
            ])

        print(f"{name} → {len(datapoints)} datapoints")

        final_response.append({
            "target": name,
            "datapoints": datapoints
        })

    return jsonify(final_response), 200


# ============================
# ANNOTATIONS (required by Grafana)
# ============================

@app.route('/annotations', methods=['GET', 'POST'])
def annotations():
    return jsonify([]), 200

# ============================
# DEBUG HELPERS
# ============================

@app.route('/debug/last')
def debug_last():
    docs = list(SensorsReaders_collection.find().sort("timestamp", -1).limit(20))
    for d in docs:
        d["_id"] = str(d["_id"])
        d["timestamp"] = d["timestamp"].isoformat()
    return jsonify(docs)

# ============================
# Grafana Infinity Query
# =========================
@app.route('/infinity_query', methods=['GET'])
def infinity_query():
    """
    Ruta para el plugin Grafana Infinity. Devuelve data plana [time, value, sensor].
    El nuevo campo 'sensor' permite al plugin Infinity crear múltiples series.
    """
    
    if SensorsReaders_collection is None:
       
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 503

    try:
     
        data_cursor = SensorsReaders_collection.find().sort("timestamp", -1).limit(1000)
        
        infinity_data = []
        for document in data_cursor:
            value = document.get("value")
            timestamp_dt = document.get("timestamp")
            sensor_name = document.get("sensor", "Unknown")

            if value is not None and timestamp_dt is not None:
                try:
                    numeric_value = float(value)
                    
                    if isinstance(timestamp_dt, datetime):
                        # Convertir a formato ISO 8601 (string) para que Infinity lo entienda como tiempo
                        # La 'Z' al final indica UTC, que es el formato estándar
                        timestamp_iso = timestamp_dt.isoformat().replace('+00:00', 'Z')
                        
                        # Formato JSON plano que Infinity espera
                        infinity_data.append({
                            "time": timestamp_iso, 
                            "value": numeric_value,
                            "sensor": sensor_name 
                        })
                        
                except (ValueError, TypeError) as e:
                    print(f"Advertencia: Error de conversión en documento: {e}")
            
        
        return jsonify(infinity_data), 200

    except Exception as e:
        print(f"Error en infinity_query: {e}")
        return jsonify([]), 500

# ============================
# Grafana Dashboard Embed
# =========================

@app.route('/dashboard')
def dashboard():
    """Displays the embedded Grafana dashboard."""
    return render_template('dashboard.html',grafana_embed_url=grafana_embed_url)


# ============================
# MAIN
# ============================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
