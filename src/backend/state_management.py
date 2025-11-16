import logging
from gimbal import GimbalSerial
from tracking import Tracking
from cv import CVPipeline

logger = logging.getLogger(__name__)

class StateManagement:
    def __init__(self):
        self._armed = False

        self._gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.1)
        self._gimbal.move_deg(0,0)
        self._tracking = Tracking(self._gimbal, 720, 1280, 0.003)
        self._cv_pipeline = CVPipeline(
            "/dev/video0",
            1280,
            720,
            60,
            "models/pega_11n_map95.engine",
            0.5,
            lambda v: self._on_detection(v),
        )

    def _on_detection(self, center):
        if self._armed:
            self._tracking.on_detection(center)

    def arm(self):
        self._armed = True
        self._cv_pipeline.armed = True

    def disarm(self):
        self._armed = False
        self._cv_pipeline.armed = False

    def status(self):
        try:
            tilt, pan = self._gimbal.measure_deg()
            return {"armed": self._armed, "tilt": tilt, "pan": pan}
        except Exception as e:
            logger.error(f"Error reading status: {e}")
            return {"armed": self._armed, "tilt": None, "pan": None}

    def manual_move(self, direction: str):
        if self._armed:
            return
        try:
            current_tilt, current_pan = self._gimbal.measure_deg()
            delta = 10.0  # degrees per command

            if direction == "up":
                new_tilt = max(0.0, min(90.0, current_tilt + delta))
                new_pan = current_pan
            elif direction == "down":
                new_tilt = max(0.0, min(90.0, current_tilt - delta))
                new_pan = current_pan
            elif direction == "left":
                new_tilt = current_tilt
                new_pan = max(-45.0, min(45.0, current_pan - delta))
            elif direction == "right":
                new_tilt = current_tilt
                new_pan = max(-45.0, min(45.0, current_pan + delta))
            else:
                logger.warning(f"Unknown direction: {direction}")
                return

            self._gimbal.move_deg(new_tilt, new_pan)
        except Exception as e:
            logger.error(f"Error in manual_move: {e}")

    def manual_move_to(self, tilt: float, pan: float):
        if self._armed:
            return
        try:
            new_tilt = max(0.0, min(90.0, tilt))
            new_pan = max(-45.0, min(45.0, pan))
            self._gimbal.move_deg(new_tilt, new_pan)
        except Exception as e:
            logger.error(f"Error in manual_move_to: {e}")

    def start(self):
        self._cv_pipeline.start()
