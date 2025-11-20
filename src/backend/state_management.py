import logging

from cv import CVPipeline
from cv_process.ipc import BoundingBox
from gimbal import GimbalSerial
from preview import MjpegFrameReceiver
import base64
import time
from dataclasses import dataclass

from tracking import Tracking

logger = logging.getLogger(__name__)

@dataclass
class InternalBoundingBox:
    bbox: BoundingBox
    received_time: float

class BoundingBoxCollection:
    _internal_bboxes: list[InternalBoundingBox]

    def __init__(self):
        self._internal_bboxes = []

    def received_bbox(self, bbox: BoundingBox):
        now = time.time()

        if self._internal_bboxes:
            last_bbox = self._internal_bboxes[-1].bbox
            if bbox.pts_s == last_bbox.pts_s:
                if bbox.conf > last_bbox.conf:
                    self._internal_bboxes[-1].bbox = bbox
            else:
                self._internal_bboxes.append(InternalBoundingBox(bbox=bbox, received_time=now))
        else:
            self._internal_bboxes.append(InternalBoundingBox(bbox=bbox, received_time=now))

        if len(self._internal_bboxes) > 10:
            self._internal_bboxes.pop(0)

    def get_bbox(self, timestamp: float | None) -> BoundingBox | None:
        if not self._internal_bboxes:
            return None

        if timestamp is None:
            return self._internal_bboxes[-1].bbox

        # Find the most recent bbox with received_time <= timestamp
        for internal_bbox in reversed(self._internal_bboxes):
            if internal_bbox.received_time <= timestamp:
                if timestamp - internal_bbox.received_time >= 1/30:
                    return None
                return internal_bbox.bbox

        return None

class StateManagement:
    def __init__(self):
        self._armed = False

        self._gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.1)
        self._gimbal.move_deg(0,0)
        self._tracking = Tracking(gimbal=self._gimbal, width=1080, height=1920, k_p=0.003)

        self._preview_receiver = MjpegFrameReceiver()
        self._cv_pipeline = CVPipeline(lambda v: self._on_detection(v))
        self._bboxes = BoundingBoxCollection()

    def _on_detection(self, bbox: BoundingBox):
        self._bboxes.received_bbox(bbox)

        if self._armed:
            self._tracking.on_detection(bbox.center())

    def arm(self):
        self._armed = True
        # self._cv_pipeline.armed = True

    def disarm(self):
        self._armed = False
        # self._cv_pipeline.armed = False

    def status(self):
        latest_preview_frame, latest_preview_frame_time = self._preview_receiver.get_latest_frame()
        bbox = None
        if latest_preview_frame is not None:
            latest_preview_frame = base64.b64encode(latest_preview_frame).decode("ascii")
            # preview is delayed by 3 frames
            bbox = self._bboxes.get_bbox(latest_preview_frame_time - 3 / 60)

        try:
            tilt, pan = self._gimbal.measure_deg()
            return {"armed": self._armed, "tilt": tilt, "pan": pan, "preview": latest_preview_frame, "bbox": bbox}
        except Exception as e:
            logger.error(f"Error reading status: {e}")
            return {"armed": self._armed, "tilt": None, "pan": None, "preview": latest_preview_frame, "bbox": bbox}

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
