import logging

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)
logger.info("Starting backend.....")

from gimbal import GimbalSerial
from tracking import Tracking
from utils import *
from cv import CVPipeline
import time

# from api import app
# from flask_cors import CORS

set_display_env()

gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5)
tracking = Tracking(gimbal, 720, 1280, 0.003)
cv_pipeline = CVPipeline("/dev/video0", 1280, 720, 60, "./pega_11n_map95.engine", lambda v: tracking.on_detection(v))

cv_pipeline.start()

try:
    while cv_pipeline.running:
        time.sleep(0.2)
except KeyboardInterrupt:
    exit(0)
finally:
    exit(0)

# app = Flask(__name__)  # 你已有
# CORS(app, resources={r"/api/*": {"origins": "*"}})  # 开发期先放开；上线可收紧
#
# # Run with: python server.py
# app.run(host="0.0.0.0", port=5000, debug=True,threaded=True)
