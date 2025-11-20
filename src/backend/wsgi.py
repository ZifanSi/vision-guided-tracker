import logging

from utils import ip4_addresses

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

flask_logger = logging.getLogger('werkzeug')
flask_logger.setLevel(logging.WARN)

logger.info("Starting backend.....")

import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from state_management import StateManagement

state_management = StateManagement()
app = Flask(__name__)
CORS(app)
FRONTEND_DIR = "../frontend"

if not os.path.isdir(FRONTEND_DIR):
    logger.warning(f"FRONTEND_DIR does not exist.")

@app.post("/api/status")
def get_status():
    return jsonify(state_management.status())

@app.post("/api/manual_move")
def manual_move():
    data = request.get_json()
    direction = data.get("direction")
    state_management.manual_move(direction)
    return jsonify({})

@app.post("/api/manual_move_to")
def manual_move_to():
    data = request.get_json()
    tilt = data.get("tilt")
    pan = data.get("pan")
    state_management.manual_move_to(tilt, pan)
    return jsonify({})

@app.post("/api/arm")
def arm():
    state_management.arm()
    return jsonify({})

@app.post("/api/disarm")
def disarm():
    state_management.disarm()
    return jsonify({})

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    try:
        return send_from_directory(FRONTEND_DIR, path)
    except Exception:
        return send_from_directory(FRONTEND_DIR, "index.html")

logger.info(f"ipv4 addresses: {ip4_addresses()}")