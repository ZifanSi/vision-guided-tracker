# pip install flask flask-cors
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading, queue, time, logging

# ========================= hardware =========================
class FakeHardwareAdapter:
    """
    @pega
    """
    AZ_MIN, AZ_MAX = -180.0, 180.0
    EL_MIN, EL_MAX =  -45.0,  90.0

    def __init__(self) -> None:
        self._az = 0.0
        self._el = 0.0
        self._lock = threading.Lock()

    def _clamp(self, az: float, el: float) -> tuple[float, float]:
        az = max(self.AZ_MIN, min(self.AZ_MAX, az))
        el = max(self.EL_MIN, min(self.EL_MAX, el))
        return az, el

    def move_to(self, az: float, el: float) -> None:
        with self._lock:
            az, el = self._clamp(az, el)
            # TODO:
            self._az, self._el = az, el
        # time.sleep(0.005)

    def nudge(self, direction: Literal["up","down","left","right"], step_deg: float) -> None:
        with self._lock:
            az, el = self._az, self._el
            if direction == "left":  az -= step_deg
            elif direction == "right": az += step_deg
            elif direction == "up":    el += step_deg
            elif direction == "down":  el -= step_deg
            self._az, self._el = self._clamp(az, el)

    def angles(self) -> tuple[float, float]:
        with self._lock:
            return self._az, self._el

# ========================= state =========================
@dataclass
class State:
    mode: Literal["manual","auto"] = "manual"
    last_error: Optional[str] = None

@dataclass(frozen=True)
class Command:
    kind: Literal["SET_MODE","MOVE"]
    payload: Dict[str, object] = field(default_factory=dict)

class Controller(threading.Thread):
    def __init__(self, hw: FakeHardwareAdapter, st: State, q: "queue.Queue[Command]") -> None:
        super().__init__(daemon=True)
        self.hw, self.state, self.q = hw, st, q

    def run(self) -> None:
        while True:
            cmd = self.q.get()
            try:
                if cmd.kind == "SET_MODE":
                    mode = cmd.payload.get("mode")
                    if mode not in ("manual", "auto"):
                        raise ValueError("mode must be 'manual' or 'auto'")
                    self.state.mode = mode  # type: ignore[attr-defined]

                elif cmd.kind == "MOVE":
                    if self.state.mode != "manual":
                        raise RuntimeError("movement is only allowed in MANUAL mode")
                    direction = cmd.payload.get("direction")
                    if direction not in ("up","down","left","right"):
                        raise ValueError("direction must be up/down/left/right")
                    step = float(cmd.payload.get("step", 0.5))
                    if step <= 0:
                        raise ValueError("step must be positive")
                    self.hw.nudge(direction, step)  # type: ignore[arg-type]

                self.state.last_error = None
            except Exception as e:
                self.state.last_error = str(e)
            finally:
                self.q.task_done()

# ========================= Flask =========================
app = Flask(__name__)
CORS(app)  # deve
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HW = FakeHardwareAdapter()
STATE = State()
Q: "queue.Queue[Command]" = queue.Queue(maxsize=256)
Controller(HW, STATE, Q).start()

def ok(**extra):
    az, el = HW.angles()
    body = {"ok": True, "mode": STATE.mode, "angle": {"az": az, "el": el}}
    if STATE.last_error:
        body["last_error"] = STATE.last_error
    body.update(extra)
    return jsonify(body), 200

def bad_request(msg: str):
    return jsonify({"ok": False, "error": msg}), 400

@app.get("/api/status")
def status():
    return ok()

@app.post("/api/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    if mode not in ("manual", "auto"):
        return bad_request("mode must be 'manual' or 'auto'")
    Q.put(Command("SET_MODE", {"mode": mode}))
    return ok()

@app.post("/api/move")
def move():
    data = request.get_json(silent=True) or {}
    direction = data.get("direction")
    if direction not in ("up","down","left","right"):
        return bad_request("direction must be up/down/left/right")
    step = data.get("step", 0.5)
    try:
        step = float(step)
    except Exception:
        return bad_request("step must be a number")
    if step <= 0:
        return bad_request("step must be positive")
    Q.put(Command("MOVE", {"direction": direction, "step": step}))
    return ok(requested={"direction": direction, "step": step})

@app.post("/api/move/<direction>")
def move_quick(direction: str):
    if direction not in ("up","down","left","right"):
        return bad_request("direction must be up/down/left/right")
    step = float(request.args.get("step", "0.5"))
    Q.put(Command("MOVE", {"direction": direction, "step": step}))
    return ok(requested={"direction": direction, "step": step})

@app.errorhandler(404)
def _404(_):
    return jsonify({"ok": False, "error": "not found"}), 404

@app.errorhandler(405)
def _405(_):
    return jsonify({"ok": False, "error": "method not allowed"}), 405

if __name__ == "__main__":
    # dev
    app.run(host="127.0.0.1", port=5000, debug=True)
