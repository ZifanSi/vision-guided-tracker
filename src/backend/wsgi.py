import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

flask_logger = logging.getLogger('werkzeug')
flask_logger.setLevel(logging.WARN)

logger.info("Starting backend.....")

from flask import Flask, jsonify, request
from flask_cors import CORS
from state_management import StateManagement

state_management = StateManagement()
app = Flask(__name__)
CORS(app)

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


state_management.start()