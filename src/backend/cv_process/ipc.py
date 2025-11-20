from multiprocessing.connection import Client, Listener
from dataclasses import dataclass

# coordinates are normalized (0.0 to 1.0)
@dataclass
class BoundingBox:
    pts_s: float
    conf: float
    left: float
    top: float
    width: float
    height: float

    def center(self) -> tuple[float, float]:
        cx = self.left + self.width / 2.0
        cy = self.top + self.height / 2.0
        return (cx, cy)

def create_rocam_ipc_server():
    return Listener(('localhost', 5000))

def create_rocam_ipc_client():
    return Client(('localhost', 5000))