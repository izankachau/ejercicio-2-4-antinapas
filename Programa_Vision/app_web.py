from flask import Flask, render_template, Response, jsonify, request
import cv2
import time
import json
import os

app = Flask(__name__)

# Directorio de datos
DATA_DIR = "logs"
LAYOUT_FILE = os.path.join(DATA_DIR, "current_layout.json")

if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

# Estado inicial
layout = {
    "zones": [],
    "objects": []
}

if os.path.exists(LAYOUT_FILE):
    with open(LAYOUT_FILE, "r") as f:
        layout = json.load(f)

events = [
    {"time": "12:15:02", "zone": "Volcado", "type": "RED", "msg": "Intrusión detectada - PARO LÍNEA"},
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    global layout
    # Intentar recargar el layout desde el archivo central si ha cambiado
    if os.path.exists(LAYOUT_FILE):
        with open(LAYOUT_FILE, "r") as f:
            layout = json.load(f)
            
    return jsonify({
        "system": "ACTIVE",
        "mode": "AUTOMATICO",
        "eagle_eye": "ONLINE",
        "last_events": events,
        "layout": layout
    })

@app.route('/api/layout', methods=['POST'])
def save_layout():
    global layout
    layout = request.json
    with open(LAYOUT_FILE, "w") as f:
        json.dump(layout, f)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
