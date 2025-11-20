import threading

from cv_process import ipc
from cv_process.ipc import create_rocam_ipc_server, BoundingBox
from utils import *
import subprocess
import os
import atexit
import signal
import sys

sys.modules["ipc"] = ipc
logger = logging.getLogger(__name__)


class CVPipeline:
    def __init__(self, detection_callback):
        self._detection_callback = detection_callback
        self._ipc_server = create_rocam_ipc_server()

        self._p = subprocess.Popen(
            ["python3", os.path.join(os.path.dirname(__file__), "cv_process", "main.py")],
            cwd=os.path.join(os.path.dirname(__file__), "cv_process"),
        )

        cleanup = lambda: self._p.kill()
        def cleanup_signals(signum, frame):
            cleanup()
            sys.exit(128 + signum)

        atexit.register(cleanup)
        signal.signal(signal.SIGINT, cleanup_signals)
        signal.signal(signal.SIGTERM, cleanup_signals)

        logger.info("Waiting for CV process to start.....")
        self._conn = self._ipc_server.accept()

        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._restart_process_loop, daemon=True).start()

        logger.info("CV process initialized")

    def _restart_process_loop(self):
        while True:
            self._p.wait()
            self._p = subprocess.Popen(
                ["python3", os.path.join(os.path.dirname(__file__), "cv_process", "main.py")],
                cwd=os.path.join(os.path.dirname(__file__), "cv_process"),
            )

    def _recv_loop(self):
        while True:
            try:
                data = self._conn.recv()
                if isinstance(data, BoundingBox):
                    self._detection_callback(data)
            except EOFError:
                # client disconnected
                self._conn = self._ipc_server.accept()
                logger.info("CV process reconnected")
